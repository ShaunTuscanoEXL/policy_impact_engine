"""Live Rule Repository service — orchestrates repo creation, snapshot
reads, merge proposal generation, and merge application.

This is the only place where LiveRuleRepository / LiveRuleVersion /
LiveRuleEntry are mutated. Routes call into here; never touch the ORM
directly from the API layer.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.codegen import parse_python, render_python
from app.models.brd import BrdDocument
from app.models.live_repo import (
    LiveRuleEntry,
    LiveRuleRepository,
    LiveRuleVersion,
)
from app.models.merge import (
    MergeItemSeverity,
    MergeProposal,
    MergeProposalItem,
    MergeProposalStatus,
    MergeSuggestedAction,
)
from app.models.rule import Rule, RuleSet, Subsystem
from app.services.canonical_key import (
    make_canonical_key,
    make_semantic_signature,
)
from app.services.merge_engine import diff_rule_sets
from app.services.rule_classifier import classify as classify_subsystem


# ── Rule serialization ───────────────────────────────────────────────────

def serialize_rule(rule: Rule) -> dict[str, Any]:
    """Convert a Rule ORM row to the plain-dict form used by the merge
    engine, the codegen, and the version snapshot."""
    return {
        "id": str(rule.id),
        "rule_id": rule.rule_id,
        "rule_name": rule.rule_name,
        "description": rule.description,
        "rule_type": rule.rule_type.value if rule.rule_type else None,
        "subsystem": rule.subsystem.value if rule.subsystem else Subsystem.UNCLASSIFIED.value,
        "canonical_key": rule.canonical_key,
        "semantic_signature": rule.semantic_signature,
        "conditions": rule.conditions if isinstance(rule.conditions, list) else [],
        "actions": rule.actions if isinstance(rule.actions, list) else [],
        "priority": rule.priority,
        "confidence": rule.confidence,
        "source_section": rule.source_section,
    }


# ── Backfill / normalization ─────────────────────────────────────────────

async def ensure_rule_classified(db: AsyncSession, rule: Rule) -> Rule:
    """Populate subsystem, canonical_key, semantic_signature on a Rule
    if any are missing. Idempotent — safe to call repeatedly."""
    changed = False
    if not rule.subsystem or rule.subsystem == Subsystem.UNCLASSIFIED:
        rule.subsystem = classify_subsystem(
            rule.conditions if isinstance(rule.conditions, list) else [],
            rule.actions if isinstance(rule.actions, list) else [],
            rule.rule_type,
        )
        changed = True
    if not rule.canonical_key:
        rule.canonical_key = make_canonical_key(
            rule.subsystem,
            rule.conditions if isinstance(rule.conditions, list) else [],
            rule.actions if isinstance(rule.actions, list) else [],
        )
        changed = True
    if not rule.semantic_signature:
        rule.semantic_signature = make_semantic_signature(
            rule.conditions if isinstance(rule.conditions, list) else [],
            rule.actions if isinstance(rule.actions, list) else [],
        )
        changed = True
    if changed:
        await db.flush()
    return rule


async def backfill_rule_set(db: AsyncSession, rule_set_id: uuid.UUID) -> int:
    """Classify every rule in a rule set. Returns the count of rules
    touched."""
    result = await db.execute(select(Rule).where(Rule.rule_set_id == rule_set_id))
    rules = list(result.scalars())
    for r in rules:
        await ensure_rule_classified(db, r)
    return len(rules)


async def backfill_all_rules(db: AsyncSession) -> int:
    """Classify every Rule in the database that doesn't yet have a
    canonical_key. Idempotent. Returns count touched.

    Run at startup or via an admin endpoint after this slice rolls out
    so that historical rules pick up subsystem + canonical_key.
    """
    result = await db.execute(select(Rule).where(Rule.canonical_key.is_(None)))
    rules = list(result.scalars())
    for r in rules:
        await ensure_rule_classified(db, r)
    if rules:
        await db.commit()
    return len(rules)


# ── Default repository helpers (Slice 1) ─────────────────────────────────

async def find_default_repository(
    db: AsyncSession, *, product: str, jurisdiction: str
) -> LiveRuleRepository | None:
    """Return the live repo for a (product, jurisdiction) pair if one exists."""
    result = await db.execute(
        select(LiveRuleRepository)
        .options(selectinload(LiveRuleRepository.versions))
        .where(
            LiveRuleRepository.product == product,
            LiveRuleRepository.jurisdiction == jurisdiction,
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_default_repository(
    db: AsyncSession,
    *,
    product: str = "PERSONAL",
    jurisdiction: str = "US",
    name_hint: str | None = None,
) -> LiveRuleRepository:
    existing = await find_default_repository(db, product=product, jurisdiction=jurisdiction)
    if existing is not None:
        return existing
    return await create_repository(
        db,
        name=name_hint or f"{product} ({jurisdiction})",
        product=product,
        jurisdiction=jurisdiction,
        description="Auto-created default repository (Slice 1)",
    )


# ── Repository CRUD ──────────────────────────────────────────────────────

async def create_repository(
    db: AsyncSession,
    *,
    name: str,
    product: str,
    jurisdiction: str,
    description: str | None = None,
) -> LiveRuleRepository:
    repo = LiveRuleRepository(
        name=name, product=product, jurisdiction=jurisdiction,
        description=description, current_version=0,
    )
    db.add(repo)
    await db.flush()
    # Seed an empty version 0 so HEAD is always queryable
    v0 = LiveRuleVersion(
        repository_id=repo.id,
        version_number=0,
        summary="Empty initial version.",
        rule_snapshot=[],
    )
    db.add(v0)
    await db.flush()
    repo.current_version = 0
    await db.commit()
    await db.refresh(repo)
    return repo


async def list_repositories(db: AsyncSession) -> list[LiveRuleRepository]:
    result = await db.execute(select(LiveRuleRepository).order_by(LiveRuleRepository.created_at))
    return list(result.scalars())


async def get_repository(db: AsyncSession, repo_id) -> LiveRuleRepository | None:
    if isinstance(repo_id, str):
        try:
            repo_id = uuid.UUID(repo_id)
        except ValueError:
            return None
    result = await db.execute(
        select(LiveRuleRepository)
        .options(selectinload(LiveRuleRepository.versions))
        .where(LiveRuleRepository.id == repo_id)
    )
    return result.scalar_one_or_none()


async def get_version(
    db: AsyncSession, repo_id: uuid.UUID, version_number: int
) -> LiveRuleVersion | None:
    result = await db.execute(
        select(LiveRuleVersion).where(
            LiveRuleVersion.repository_id == repo_id,
            LiveRuleVersion.version_number == version_number,
        )
    )
    return result.scalar_one_or_none()


async def get_head_version(
    db: AsyncSession, repo_id: uuid.UUID
) -> LiveRuleVersion | None:
    repo = await db.get(LiveRuleRepository, repo_id)
    if repo is None:
        return None
    return await get_version(db, repo_id, repo.current_version)


# ── Production promotion ────────────────────────────────────────────────

async def promote_version_to_production(
    db: AsyncSession,
    *,
    repository_id: uuid.UUID,
    version_number: int,
    promoted_by: str | None = None,
) -> tuple[LiveRuleRepository, LiveRuleVersion]:
    """Mark a specific version as production-live for the repository.

    The version stays where it is (no data movement) — we just flip a
    pointer + timestamp on the repo. Idempotent: promoting the already-
    production version updates only the timestamp + actor.
    """
    repo = await db.get(LiveRuleRepository, repository_id)
    if repo is None:
        raise ValueError(f"Repository {repository_id} not found")
    version = await get_version(db, repo.id, version_number)
    if version is None:
        raise ValueError(
            f"Version {version_number} not found in repo {repository_id}"
        )
    if version_number == 0:
        raise ValueError("Cannot promote v0 (empty seed) to production.")

    repo.production_version_id = version.id
    repo.production_promoted_at = datetime.utcnow()
    repo.production_promoted_by = promoted_by or "system"
    repo.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(repo)
    return repo, version


async def auto_promote_first_version(
    db: AsyncSession, repo: LiveRuleRepository, new_version: LiveRuleVersion
) -> None:
    """Called from inside an in-flight transaction (NO commit). When a
    repository's FIRST real version (v >= 1) lands and nothing has been
    promoted yet, promote it automatically. This preserves the natural
    "the only version is the live one" expectation while still requiring
    explicit promotion for v2, v3, … candidates.
    """
    if repo.production_version_id is not None:
        return
    if new_version.version_number < 1:
        return
    repo.production_version_id = new_version.id
    repo.production_promoted_at = datetime.utcnow()
    repo.production_promoted_by = new_version.created_by or "auto-baseline"


async def backfill_production_versions(db: AsyncSession) -> int:
    """Idempotent startup helper: any repo with current_version >= 1 but
    no production_version_id gets backfilled to point at its highest
    version. Returns the number of repos updated."""
    result = await db.execute(
        select(LiveRuleRepository).where(
            LiveRuleRepository.production_version_id.is_(None),
            LiveRuleRepository.current_version >= 1,
        )
    )
    updated = 0
    for repo in result.scalars():
        head = await get_version(db, repo.id, repo.current_version)
        if head is None:
            continue
        repo.production_version_id = head.id
        repo.production_promoted_at = datetime.utcnow()
        repo.production_promoted_by = "auto-backfill"
        updated += 1
    if updated:
        await db.commit()
    return updated


# ── Codegen ──────────────────────────────────────────────────────────────

async def import_python_as_version(
    db: AsyncSession,
    *,
    repository_id: uuid.UUID,
    source: str,
    decided_by: str | None = None,
    summary_override: str | None = None,
) -> tuple[LiveRuleVersion, list[str], int]:
    """Slice 3: parse a Python rules module and persist its rules as a
    new LiveRuleVersion of the repository.

    The parsed rules are NOT routed through the merge engine — Python
    upload is a trusted-source flow per the architecture decision. The
    incoming module is treated as the new HEAD verbatim (after
    normalizing canonical_key + subsystem on each rule).

    Returns ``(new_version, warnings, rules_imported_count)``.
    Raises :class:`ValueError` on parse failure or unknown repository.
    """
    repo = await db.get(LiveRuleRepository, repository_id)
    if repo is None:
        raise ValueError(f"Repository {repository_id} not found")

    try:
        parse_result = parse_python(source)
    except SyntaxError as e:
        raise ValueError(f"Python source has syntax error: {e}") from e

    if not parse_result.rules:
        raise ValueError(
            "No @rule-decorated functions found. Make sure the source matches "
            "the codegen format."
        )

    head = await get_head_version(db, repo.id)
    new_version_number = repo.current_version + 1

    # Materialize each parsed rule into a snapshot dict, computing
    # canonical_key + semantic_signature so the next merge can pair
    # it correctly.
    snapshot: list[dict] = []
    for pr in parse_result.rules:
        from app.services.canonical_key import (
            make_canonical_key,
            make_semantic_signature,
        )
        ck = make_canonical_key(pr.subsystem, pr.conditions, pr.actions)
        sig = make_semantic_signature(pr.conditions, pr.actions)
        snapshot.append({
            "id": pr.rule_id,
            "rule_id": pr.rule_id,
            "rule_name": pr.rule_name,
            "description": pr.description,
            "subsystem": pr.subsystem,
            "priority": pr.priority,
            "source_section": pr.source_section,
            "canonical_key": ck,
            "semantic_signature": sig,
            "conditions": pr.conditions,
            "actions": pr.actions,
        })

    summary = summary_override or (
        f"Python import: {len(snapshot)} rule(s)"
        + (f", {len(parse_result.warnings)} warning(s)" if parse_result.warnings else "")
    )
    new_version = LiveRuleVersion(
        repository_id=repo.id,
        version_number=new_version_number,
        parent_version_id=head.id if head else None,
        source_brd_id=None,
        merge_proposal_id=None,
        summary=summary,
        rule_snapshot=snapshot,
        created_by=decided_by or "python-import",
    )
    db.add(new_version)
    await db.flush()
    new_version.python_export = render_python(repo, new_version)

    repo.current_version = new_version_number
    repo.updated_at = datetime.utcnow()
    # First-version auto-promote: a freshly imported v1 with no prior
    # production state should show up as live without a separate click.
    await auto_promote_first_version(db, repo, new_version)

    await db.commit()
    await db.refresh(new_version)
    warning_messages = [f"{w.rule_name or '?'}: {w.message}" for w in parse_result.warnings]
    return new_version, warning_messages, len(snapshot)


async def export_python(
    db: AsyncSession, repo_id: uuid.UUID, version_number: int | None = None
) -> str | None:
    repo = await db.get(LiveRuleRepository, repo_id)
    if repo is None:
        return None
    vn = repo.current_version if version_number is None else version_number
    version = await get_version(db, repo_id, vn)
    if version is None:
        return None
    if version.python_export:
        return version.python_export
    # Generate on the fly if not cached (e.g. for v0 or pre-cache backfills)
    return render_python(repo, version)


# ── Merge proposals ──────────────────────────────────────────────────────

async def latest_rule_set_for_brd(
    db: AsyncSession, brd_id: uuid.UUID
) -> RuleSet | None:
    """Return the most-recently-created rule_set for a BRD."""
    result = await db.execute(
        select(RuleSet)
        .options(selectinload(RuleSet.rules))
        .where(RuleSet.brd_document_id == brd_id)
        .order_by(RuleSet.created_at.desc(), RuleSet.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def propose_from_brd(
    db: AsyncSession,
    *,
    brd_id: uuid.UUID,
    repository_id: uuid.UUID | None = None,
    product: str = "PERSONAL",
    jurisdiction: str = "US",
    auto_apply_when_empty: bool = True,
    decided_by: str | None = None,
    retirement_signals: list[dict] | None = None,
) -> tuple[MergeProposal | None, LiveRuleVersion | None]:
    """One-shot helper for the slice 1 "BRD upload -> merge proposal" flow.

    Resolves (or creates) the default repository for the (product,
    jurisdiction) pair, finds the latest rule_set produced for the BRD,
    and builds a merge proposal.

    If ``auto_apply_when_empty`` is True and the repo currently has no
    rules (current_version == 0 and snapshot empty), the proposal is
    immediately applied to baseline the repo as v1. Returns
    ``(proposal, applied_version_or_none)``.
    """
    rule_set = await latest_rule_set_for_brd(db, brd_id)
    if rule_set is None:
        raise ValueError(f"No rule_set found for BRD {brd_id}")

    if repository_id is None:
        repo = await get_or_create_default_repository(
            db, product=product, jurisdiction=jurisdiction,
        )
    else:
        repo = await db.get(LiveRuleRepository, repository_id)
        if repo is None:
            raise ValueError(f"Repository {repository_id} not found")

    proposal = await build_merge_proposal(
        db,
        repository_id=repo.id,
        source_rule_set_id=rule_set.id,
        retirement_signals=retirement_signals,
    )

    # Auto-apply when the repo is empty (baselining). All items will be
    # NEW_RULE / INFO so apply is guaranteed to succeed.
    head = await get_head_version(db, repo.id)
    head_is_empty = head is None or not (head.rule_snapshot or [])
    if auto_apply_when_empty and head_is_empty:
        new_version, _blockers = await apply_merge_proposal(
            db, proposal_id=proposal.id, decided_by=decided_by or "auto-baseline",
        )
        return proposal, new_version

    return proposal, None


async def build_merge_proposal(
    db: AsyncSession,
    *,
    repository_id: uuid.UUID,
    source_rule_set_id: uuid.UUID,
    retirement_signals: list[dict] | None = None,
) -> MergeProposal:
    """Create a MergeProposal by diffing a candidate rule_set against the
    HEAD of a live repository.

    ``retirement_signals`` is the LLM's explicit list of rules the BRD
    is retiring (matched by canonical_key). Empty/None means no Layer-1
    retirements; the merge engine still runs Layer-2 inference at the
    pairing level.
    """
    repo = await db.get(LiveRuleRepository, repository_id)
    if repo is None:
        raise ValueError(f"Live repository {repository_id} not found")

    rs_result = await db.execute(
        select(RuleSet)
        .options(selectinload(RuleSet.rules))
        .where(RuleSet.id == source_rule_set_id)
    )
    rule_set = rs_result.scalar_one_or_none()
    if rule_set is None:
        raise ValueError(f"Rule set {source_rule_set_id} not found")

    # Ensure all incoming rules are normalized (classified + canonical_key)
    for r in rule_set.rules:
        await ensure_rule_classified(db, r)

    head = await get_head_version(db, repository_id)
    live_rules: list[dict] = list(head.rule_snapshot or []) if head else []
    incoming_rules = [serialize_rule(r) for r in rule_set.rules]

    item_specs = diff_rule_sets(
        incoming_rules, live_rules,
        retirement_signals=retirement_signals,
    )

    proposal = MergeProposal(
        repository_id=repository_id,
        base_version=repo.current_version,
        source_brd_id=rule_set.brd_document_id,
        source_rule_set_id=rule_set.id,
        status=MergeProposalStatus.PENDING,
        summary=_summarize_specs(item_specs),
    )
    db.add(proposal)
    await db.flush()

    def _maybe_uuid(v):
        """Snapshot rules from the Python-import path use the original
        rule_id (a non-UUID string) as their id. Don't try to FK those
        back into the rules table — store None so the item still
        carries the canonical_key / diff for HITL display."""
        if not v:
            return None
        try:
            return uuid.UUID(str(v))
        except (TypeError, ValueError):
            return None

    for spec in item_specs:
        db.add(MergeProposalItem(
            proposal_id=proposal.id,
            category=spec.category,
            severity=spec.severity,
            suggested_action=spec.suggested_action,
            incoming_rule_id=_maybe_uuid(spec.incoming_rule_id),
            live_rule_id=_maybe_uuid(spec.live_rule_id),
            canonical_key=spec.canonical_key,
            diff=spec.diff,
            rationale=spec.rationale,
            confidence=spec.confidence,
        ))

    await db.commit()

    # Re-fetch with items eagerly loaded so the API layer can serialize
    # without tripping async lazy loading.
    refreshed = await db.execute(
        select(MergeProposal)
        .options(selectinload(MergeProposal.items))
        .where(MergeProposal.id == proposal.id)
    )
    return refreshed.scalar_one()


async def get_merge_proposal(
    db: AsyncSession, proposal_id: uuid.UUID
) -> MergeProposal | None:
    result = await db.execute(
        select(MergeProposal)
        .options(selectinload(MergeProposal.items))
        .where(MergeProposal.id == proposal_id)
    )
    return result.scalar_one_or_none()


async def update_proposal_item(
    db: AsyncSession,
    *,
    item_id: uuid.UUID,
    user_action: MergeSuggestedAction | None = None,
    user_edits: dict | None = None,
    notes: str | None = None,
) -> MergeProposalItem | None:
    item = await db.get(MergeProposalItem, item_id)
    if item is None:
        return None
    if user_action is not None:
        item.user_action = user_action
    if user_edits is not None:
        item.user_edits = user_edits
    if notes is not None:
        item.notes = notes
    await db.commit()
    await db.refresh(item)
    return item


# ── Apply (promote merge to a new version) ───────────────────────────────

def _effective_action(item: MergeProposalItem) -> MergeSuggestedAction:
    """The action the engine should execute: user_action overrides
    suggested_action."""
    return item.user_action or item.suggested_action


def _has_unresolved_hard_conflicts(items: list[MergeProposalItem]) -> list[MergeProposalItem]:
    blockers: list[MergeProposalItem] = []
    for it in items:
        if it.severity == MergeItemSeverity.HARD:
            eff = _effective_action(it)
            if eff in (MergeSuggestedAction.NEEDS_HUMAN, MergeSuggestedAction.EDIT_NEEDED):
                blockers.append(it)
    return blockers


async def apply_merge_proposal(
    db: AsyncSession,
    *,
    proposal_id: uuid.UUID,
    decided_by: str | None = None,
) -> tuple[LiveRuleVersion | None, list[MergeProposalItem]]:
    """Apply an approved MergeProposal: produce a new LiveRuleVersion,
    rebuild LiveRuleEntry table, return the new version.

    Returns (None, blockers) if hard conflicts are unresolved.
    """
    proposal_result = await db.execute(
        select(MergeProposal)
        .options(selectinload(MergeProposal.items))
        .where(MergeProposal.id == proposal_id)
    )
    proposal = proposal_result.scalar_one_or_none()
    if proposal is None:
        raise ValueError(f"Merge proposal {proposal_id} not found")
    if proposal.status == MergeProposalStatus.APPLIED:
        raise ValueError("Merge proposal already applied")

    blockers = _has_unresolved_hard_conflicts(proposal.items)
    if blockers:
        return None, blockers

    repo = await db.get(LiveRuleRepository, proposal.repository_id)
    if repo is None:
        raise ValueError("Repository missing")

    head = await get_head_version(db, repo.id)
    base_snapshot: list[dict] = list(head.rule_snapshot or []) if head else []
    base_by_id = {str(r.get("id")): r for r in base_snapshot}

    # Load incoming rules from the source rule set, indexed by id
    rs_result = await db.execute(
        select(RuleSet)
        .options(selectinload(RuleSet.rules))
        .where(RuleSet.id == proposal.source_rule_set_id)
    )
    rule_set = rs_result.scalar_one()
    incoming_by_id = {str(r.id): serialize_rule(r) for r in rule_set.rules}

    # Track active rules by canonical_key. Start from base, mutate per item.
    next_snapshot: dict[str, dict] = {}
    for r in base_snapshot:
        ck = r.get("canonical_key") or f"_id::{r.get('id')}"
        next_snapshot[ck] = r

    for item in proposal.items:
        action = _effective_action(item)
        incoming = incoming_by_id.get(str(item.incoming_rule_id)) if item.incoming_rule_id else None
        live_id = str(item.live_rule_id) if item.live_rule_id else None
        live = base_by_id.get(live_id) if live_id else None
        ck = item.canonical_key or (incoming or {}).get("canonical_key") or (live or {}).get("canonical_key")

        if action in (MergeSuggestedAction.DROP, MergeSuggestedAction.REJECT):
            continue  # nothing to do; live stays
        if action == MergeSuggestedAction.RETIRE and ck:
            next_snapshot.pop(ck, None)
            continue
        if action in (MergeSuggestedAction.ACCEPT, MergeSuggestedAction.SUPERSEDE,
                      MergeSuggestedAction.SUPERSEDE_GROUP):
            if incoming:
                # If the user provided edits, overlay them on the incoming dict
                if item.user_edits:
                    incoming = {**incoming, **item.user_edits}
                next_snapshot[ck or f"_id::{incoming.get('id')}"] = incoming
            continue
        if action == MergeSuggestedAction.KEEP_BOTH and incoming:
            # Park under a unique key so both survive
            unique_key = f"{ck}#dup-{item.id}" if ck else f"_id::{incoming.get('id')}"
            next_snapshot[unique_key] = incoming
            continue
        # NEEDS_HUMAN / EDIT_NEEDED on a SOFT item → treat as no-op
        # (decided_by took the warning) — soft items don't block apply.

    new_version_number = repo.current_version + 1
    final_snapshot = list(next_snapshot.values())

    # Persist the new version (python_export is rendered + cached after creation
    # so we have repo + version objects in scope).
    new_version = LiveRuleVersion(
        repository_id=repo.id,
        version_number=new_version_number,
        parent_version_id=head.id if head else None,
        source_brd_id=proposal.source_brd_id,
        merge_proposal_id=proposal.id,
        summary=_summarize_apply(proposal.items, final_snapshot),
        rule_snapshot=final_snapshot,
        created_by=decided_by,
    )
    db.add(new_version)
    await db.flush()

    new_version.python_export = render_python(repo, new_version)

    # Rebuild HEAD entries
    await db.execute(
        LiveRuleEntry.__table__.delete().where(
            LiveRuleEntry.repository_id == repo.id
        )
    )
    for r in final_snapshot:
        rid = r.get("id")
        ck = r.get("canonical_key")
        if not rid or not ck:
            continue
        try:
            rule_uuid = uuid.UUID(str(rid))
        except (TypeError, ValueError):
            continue
        db.add(LiveRuleEntry(
            repository_id=repo.id,
            rule_id=rule_uuid,
            canonical_key=ck,
            is_active=True,
            added_in_version=new_version_number,  # simplification for slice 0
            last_modified_in_version=new_version_number,
        ))

    repo.current_version = new_version_number
    repo.updated_at = datetime.utcnow()
    # First-version auto-promote: new repos becoming v1 should land as
    # production without a manual promote step (preserves prior UX).
    # v2+ candidates require explicit promotion.
    await auto_promote_first_version(db, repo, new_version)
    proposal.status = MergeProposalStatus.APPLIED
    proposal.decided_by = decided_by
    proposal.decided_at = datetime.utcnow()

    await db.commit()
    await db.refresh(new_version)
    return new_version, []


# ── Summary helpers ──────────────────────────────────────────────────────

def _summarize_specs(specs) -> str:
    counts: dict[str, int] = {}
    for s in specs:
        counts[s.category.value] = counts.get(s.category.value, 0) + 1
    parts = [f"{n} {k}" for k, n in sorted(counts.items())]
    return f"{len(specs)} change(s): " + ", ".join(parts) if specs else "No changes"


def _summarize_apply(items: list[MergeProposalItem], final_snapshot: list[dict]) -> str:
    counts: dict[str, int] = {}
    for it in items:
        eff = (it.user_action or it.suggested_action).value
        counts[eff] = counts.get(eff, 0) + 1
    parts = [f"{n} {k}" for k, n in sorted(counts.items())]
    return f"Applied {len(items)} item(s) → {len(final_snapshot)} active rules. " + ", ".join(parts)
