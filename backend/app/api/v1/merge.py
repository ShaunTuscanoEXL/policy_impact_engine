"""Merge Proposal endpoints — create proposal from a candidate rule_set,
inspect items, set per-item user_action, apply approved proposal."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.merge import (
    MergeItemSeverity,
    MergeProposalStatus,
    MergeSuggestedAction,
)
from app.schemas.merge import (
    CreateMergeProposalRequest,
    MergeApplyRequest,
    MergeApplyResponse,
    MergeBatchUpdateRequest,
    MergeBatchUpdateResponse,
    MergeItemResponse,
    MergeItemUpdateRequest,
    MergeProposalResponse,
    MergeRulePayload,
)
from app.models.merge import MergeItemCategory
from app.services import live_repo_service as svc

router = APIRouter(prefix="/merge-proposal", tags=["Merge Proposals"])


def _rule_to_payload(rule) -> MergeRulePayload | None:
    """Project a DB Rule into the inline MergeRulePayload — every
    field a reviewer needs to see in the workbench (full conditions,
    full actions with target+value, name, description, …)."""
    if rule is None:
        return None
    return MergeRulePayload(
        rule_id=getattr(rule, "rule_id", None),
        rule_name=getattr(rule, "rule_name", None),
        description=getattr(rule, "description", None),
        rule_type=(
            rule.rule_type.value
            if hasattr(rule, "rule_type") and hasattr(rule.rule_type, "value")
            else (str(rule.rule_type) if getattr(rule, "rule_type", None) else None)
        ),
        subsystem=(
            rule.subsystem.value
            if hasattr(rule, "subsystem") and hasattr(rule.subsystem, "value")
            else (str(rule.subsystem) if getattr(rule, "subsystem", None) else None)
        ),
        canonical_key=getattr(rule, "canonical_key", None),
        conditions=rule.conditions if isinstance(getattr(rule, "conditions", None), list) else [],
        actions=rule.actions if isinstance(getattr(rule, "actions", None), list) else [],
        priority=getattr(rule, "priority", None),
        confidence=getattr(rule, "confidence", None),
        source_section=getattr(rule, "source_section", None),
    )


def _snapshot_rule_to_payload(snap_dict: dict | None) -> MergeRulePayload | None:
    """Same projection but from a snapshot dict (live version's
    rule_snapshot entries) — those don't go through the ORM."""
    if not snap_dict or not isinstance(snap_dict, dict):
        return None
    return MergeRulePayload(
        rule_id=snap_dict.get("rule_id"),
        rule_name=snap_dict.get("rule_name"),
        description=snap_dict.get("description"),
        rule_type=snap_dict.get("rule_type"),
        subsystem=snap_dict.get("subsystem"),
        canonical_key=snap_dict.get("canonical_key"),
        conditions=snap_dict.get("conditions") or [],
        actions=snap_dict.get("actions") or [],
        priority=snap_dict.get("priority"),
        confidence=snap_dict.get("confidence"),
        source_section=snap_dict.get("source_section"),
    )


def _item_to_response(
    item,
    *,
    incoming_rule=None,
    live_rule_snapshot: dict | None = None,
) -> MergeItemResponse:
    return MergeItemResponse(
        id=str(item.id),
        category=item.category.value,
        severity=item.severity.value,
        canonical_key=item.canonical_key,
        incoming_rule_id=str(item.incoming_rule_id) if item.incoming_rule_id else None,
        live_rule_id=str(item.live_rule_id) if item.live_rule_id else None,
        diff=item.diff,
        suggested_action=item.suggested_action.value,
        user_action=item.user_action.value if item.user_action else None,
        user_edits=item.user_edits,
        notes=item.notes,
        rationale=item.rationale,
        confidence=item.confidence,
        incoming_rule=_rule_to_payload(incoming_rule),
        live_rule=_snapshot_rule_to_payload(live_rule_snapshot),
    )


async def _populate_full_rules(
    proposal, db: AsyncSession
) -> tuple[dict, dict]:
    """Look up the full Rule rows for every item's incoming_rule_id and
    join the live snapshot for each item's live_rule_id. Returns two
    dicts so the per-item serializer can do O(1) lookups instead of
    issuing an N×2 query storm."""
    from sqlalchemy import select as _s
    from app.models.rule import Rule
    from app.models.live_repo import LiveRuleVersion

    incoming_ids = {
        i.incoming_rule_id for i in proposal.items if i.incoming_rule_id
    }
    incoming_map: dict = {}
    if incoming_ids:
        rows = await db.execute(_s(Rule).where(Rule.id.in_(incoming_ids)))
        for r in rows.scalars():
            incoming_map[str(r.id)] = r

    # Build a lookup of live snapshot rules keyed by their snapshot id.
    # We pull the HEAD version's snapshot since merge proposals always
    # diff against HEAD at proposal-create time.
    snapshot_map: dict = {}
    head_q = await db.execute(
        _s(LiveRuleVersion)
        .where(LiveRuleVersion.repository_id == proposal.repository_id)
        .order_by(LiveRuleVersion.version_number.desc())
        .limit(1)
    )
    head = head_q.scalar_one_or_none()
    if head and head.rule_snapshot:
        for snap in head.rule_snapshot:
            if isinstance(snap, dict) and snap.get("id"):
                snapshot_map[str(snap["id"])] = snap

    return incoming_map, snapshot_map


async def _proposal_to_response_async(proposal, db: AsyncSession) -> MergeProposalResponse:
    incoming_map, snapshot_map = await _populate_full_rules(proposal, db)
    items = [
        _item_to_response(
            i,
            incoming_rule=incoming_map.get(str(i.incoming_rule_id)) if i.incoming_rule_id else None,
            live_rule_snapshot=snapshot_map.get(str(i.live_rule_id)) if i.live_rule_id else None,
        )
        for i in proposal.items
    ]
    return _proposal_to_response_with_items(proposal, items)


def _proposal_to_response_with_items(proposal, items: list[MergeItemResponse]) -> MergeProposalResponse:

    counts_cat: dict[str, int] = {}
    counts_sev: dict[str, int] = {}
    blockers: list[str] = []

    for it in proposal.items:
        counts_cat[it.category.value] = counts_cat.get(it.category.value, 0) + 1
        counts_sev[it.severity.value] = counts_sev.get(it.severity.value, 0) + 1
        eff = (it.user_action or it.suggested_action)
        if it.severity == MergeItemSeverity.HARD and eff in (
            MergeSuggestedAction.NEEDS_HUMAN, MergeSuggestedAction.EDIT_NEEDED
        ):
            blockers.append(str(it.id))

    return MergeProposalResponse(
        id=str(proposal.id),
        repository_id=str(proposal.repository_id),
        base_version=proposal.base_version,
        source_brd_id=str(proposal.source_brd_id),
        source_rule_set_id=str(proposal.source_rule_set_id),
        status=proposal.status.value,
        summary=proposal.summary,
        decided_by=proposal.decided_by,
        decided_at=proposal.decided_at.isoformat() if proposal.decided_at else None,
        decision_rationale=getattr(proposal, "decision_rationale", None),
        created_at=proposal.created_at.isoformat(),
        items=items,
        counts_by_category=counts_cat,
        counts_by_severity=counts_sev,
        blockers=blockers,
    )


@router.post("", response_model=MergeProposalResponse, status_code=201)
async def create_proposal(
    payload: CreateMergeProposalRequest, db: AsyncSession = Depends(get_db)
):
    try:
        proposal = await svc.build_merge_proposal(
            db,
            repository_id=uuid.UUID(payload.repository_id),
            source_rule_set_id=uuid.UUID(payload.source_rule_set_id),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _proposal_to_response_async(proposal, db)


@router.get("/{proposal_id}", response_model=MergeProposalResponse)
async def get_proposal(proposal_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    proposal = await svc.get_merge_proposal(db, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Merge proposal not found")
    return await _proposal_to_response_async(proposal, db)


@router.post("/{proposal_id}/regenerate", response_model=MergeProposalResponse)
async def regenerate_proposal(
    proposal_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Re-run the merge engine for an existing PENDING proposal.

    Useful when the underlying rule_set has changed since the proposal
    was first issued (e.g., the tier-rule fan-out added new rules) and
    the workbench is now showing stale items. Replaces the proposal's
    items with a fresh diff while keeping the proposal id, repo, BRD,
    and rule_set links intact so the URL / context stays valid.

    No-op on APPLIED / REJECTED / APPROVED proposals.
    """
    proposal = await svc.regenerate_proposal_items(db, proposal_id=proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Merge proposal not found")
    return await _proposal_to_response_async(proposal, db)


@router.patch("/{proposal_id}/items/{item_id}", response_model=MergeItemResponse)
async def update_item(
    proposal_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: MergeItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    user_action: MergeSuggestedAction | None = None
    if payload.user_action:
        try:
            user_action = MergeSuggestedAction(payload.user_action.upper())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid user_action: {payload.user_action}",
            )
    item = await svc.update_proposal_item(
        db,
        item_id=item_id,
        user_action=user_action,
        user_edits=payload.user_edits,
        notes=payload.notes,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Merge item not found")
    if item.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="Item does not belong to this proposal")
    return _item_to_response(item)


@router.post("/{proposal_id}/batch-update", response_model=MergeBatchUpdateResponse)
async def batch_update_items(
    proposal_id: uuid.UUID,
    payload: MergeBatchUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Slice 6 — apply a single user_action to every item matching the
    severity / category filter. Skips items that already have a
    user_action unless `overwrite_existing=True`."""
    try:
        action = MergeSuggestedAction(payload.user_action.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user_action: {payload.user_action}",
        )
    severity = None
    if payload.severity:
        try:
            severity = MergeItemSeverity(payload.severity.upper())
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid severity: {payload.severity}",
            )
    category = None
    if payload.category:
        try:
            category = MergeItemCategory(payload.category.upper())
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid category: {payload.category}",
            )
    try:
        updated, skipped_existing, skipped_unmatched = await svc.batch_update_proposal_items(
            db,
            proposal_id=proposal_id,
            user_action=action,
            severity=severity,
            category=category,
            overwrite_existing=payload.overwrite_existing,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return MergeBatchUpdateResponse(
        updated=updated,
        skipped_existing=skipped_existing,
        skipped_unmatched=skipped_unmatched,
        user_action=action.value,
    )


@router.post("/{proposal_id}/apply", response_model=MergeApplyResponse)
async def apply_proposal(
    proposal_id: uuid.UUID,
    payload: MergeApplyRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        new_version, blockers = await svc.apply_merge_proposal(
            db,
            proposal_id=proposal_id,
            decided_by=payload.decided_by,
            rationale=payload.rationale,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if new_version is None:
        return MergeApplyResponse(
            applied=False,
            blockers=[str(b.id) for b in blockers],
            summary=(
                f"Cannot apply: {len(blockers)} hard conflict(s) still need a "
                f"reviewer decision."
            ),
        )

    return MergeApplyResponse(
        applied=True,
        new_version_number=new_version.version_number,
        new_version_id=str(new_version.id),
        blockers=[],
        summary=new_version.summary,
    )
