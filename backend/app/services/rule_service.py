import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from app.models.rule import RuleSet, Rule, RuleSetStatus 
from app.models.merge import MergeProposalItem
from app.models.live_repo import LiveRuleEntry

logger = logging.getLogger(__name__)


async def on_rule_set_modified(
    db: AsyncSession,
    rule_set_id: uuid.UUID | str,
    *,
    skip_proposal_regen: bool = False,
) -> None:
    """Central hook called whenever a rule_set's contents change (rule
    added/edited/deleted, status flipped, re-classified, etc.).

    It does three things downstream artifacts depend on:

      1. Bumps `rule_set.last_modified_at` so test suites and other
         consumers can detect staleness.
      2. Re-runs the canonical_key + subsystem + semantic_signature
         classification on every rule in the set so the merge engine's
         pairing/diff stays consistent.
      3. Regenerates any PENDING merge proposals that point at this
         rule_set so the workbench shows the *current* rule contents,
         not the snapshot taken at proposal-creation time.

    Idempotent and safe to call multiple times. Failures in any one
    step are logged and don't block the others."""
    if isinstance(rule_set_id, str):
        try:
            rule_set_id = uuid.UUID(rule_set_id)
        except ValueError:
            return

    # 1. Bump the modified timestamp + 2. Re-classify rules
    rs_q = await db.execute(
        select(RuleSet)
        .options(selectinload(RuleSet.rules))
        .where(RuleSet.id == rule_set_id)
    )
    rs = rs_q.scalar_one_or_none()
    if rs is None:
        return
    rs.last_modified_at = datetime.utcnow()
    try:
        from app.services.live_repo_service import ensure_rule_classified
        for r in rs.rules:
            await ensure_rule_classified(db, r, force=True)
    except Exception as e:  # noqa: BLE001
        logger.warning("Re-classify after rule_set modify failed: %s", e)
    await db.commit()

    # 3. Regenerate any PENDING proposals for this rule_set
    if not skip_proposal_regen:
        try:
            from app.models.merge import MergeProposal, MergeProposalStatus
            from app.services.live_repo_service import regenerate_proposal_items
            pending_q = await db.execute(
                select(MergeProposal).where(
                    MergeProposal.source_rule_set_id == rule_set_id,
                    MergeProposal.status == MergeProposalStatus.PENDING,
                )
            )
            for p in pending_q.scalars():
                await regenerate_proposal_items(db, proposal_id=p.id)
        except Exception as e:  # noqa: BLE001
            logger.warning("Proposal regen after rule_set modify failed: %s", e)


async def list_rule_sets(db: AsyncSession) -> list[RuleSet]:
    result = await db.execute(
        select(RuleSet).options(selectinload(RuleSet.rules)).order_by(RuleSet.created_at.desc())
    )
    return list(result.scalars().all())


async def get_rule_set(rule_set_id: str, db: AsyncSession) -> RuleSet | None:
    try:
        parsed_id = uuid.UUID(rule_set_id)
    except ValueError:
        return None
    result = await db.execute(
        select(RuleSet)
        .where(RuleSet.id == parsed_id)
        .options(selectinload(RuleSet.rules))
    )
    return result.scalar_one_or_none()


async def approve_rule_set(
    rule_set_id: str,
    db: AsyncSession,
    *,
    approved_by: str | None = None,
    approval_notes: str | None = None,
) -> RuleSet | None:
    rs = await get_rule_set(rule_set_id, db)
    if not rs:
        return None
    rs.status = RuleSetStatus.APPROVED
    rs.approved_by = (approved_by.strip() if approved_by else None) or "reviewer"
    rs.approved_at = datetime.utcnow()
    rs.approval_notes = (approval_notes.strip() if approval_notes else None) or None
    await db.commit()

    # Audit event for the per-BRD timeline.
    try:
        from app.services.audit_service import record_event
        from app.models.audit_event import AuditAction, AuditEntityType
        await record_event(
            db,
            action=AuditAction.RULE_SET_APPROVED,
            entity_type=AuditEntityType.RULE_SET,
            entity_id=rs.id,
            actor=rs.approved_by,
            rationale=rs.approval_notes,
            brd_id=rs.brd_document_id,
            metadata={
                "rule_set_id": str(rs.id),
                "version": rs.version,
                "rule_count": len(rs.rules),
            },
        )
    except Exception as e:
        logger.warning("Audit event for rule_set approval failed: %s", e)

    await on_rule_set_modified(db, rs.id)
    await db.refresh(rs)
    return rs


async def create_rule_set_version(rule_set_id: str, db: AsyncSession) -> RuleSet | None:
    """Clone current rule set into a new version."""
    original = await get_rule_set(rule_set_id, db)
    if not original:
        return None
    new_rs = RuleSet(
        brd_document_id=original.brd_document_id,
        version=original.version + 1,
        name=original.name,
        description=original.description,
        status=RuleSetStatus.DRAFT,
    )
    db.add(new_rs)
    await db.flush()
    # Clone all rules
    for rule in original.rules:
        new_rule = Rule(
            rule_set_id=new_rs.id,
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            description=rule.description,
            rule_type=rule.rule_type,
            conditions=rule.conditions,
            actions=rule.actions,
            priority=rule.priority,
            confidence=rule.confidence,
            compiled_expression=rule.compiled_expression,
            source_section=rule.source_section,
        )
        db.add(new_rule)
    await db.commit()
    await db.refresh(new_rs)
    return await get_rule_set(str(new_rs.id), db)


async def update_rule(rule_id: str, updates: dict, db: AsyncSession) -> Rule | None:
    try:
        parsed_id = uuid.UUID(rule_id)
    except ValueError:
        return None
    result = await db.execute(select(Rule).where(Rule.id == parsed_id))
    rule = result.scalar_one_or_none()
    if not rule:
        return None
    for key, value in updates.items():
        if value is not None and hasattr(rule, key):
            setattr(rule, key, value)
    await db.commit()
    # Edited rule needs re-classification + the rule_set's proposal
    # needs to reflect the new contents.
    await on_rule_set_modified(db, rule.rule_set_id)
    await db.refresh(rule)
    return rule


async def delete_rule(rule_id: str, db: AsyncSession) -> bool:
    try:
        parsed_id = uuid.UUID(rule_id)
    except ValueError:
        return False

    result = await db.execute(
        select(Rule).where(Rule.id == parsed_id)
    )
    rule = result.scalar_one_or_none()

    if not rule:
        return False

    rule_set_id = rule.rule_set_id

    # await db.execute(
    #     delete(LiveRuleEntry).where(LiveRuleEntry.rule_id == parsed_id)
    # )
    # Delete merge proposal items referencing this rule
    await db.execute(
        delete(MergeProposalItem).where(
            MergeProposalItem.incoming_rule_id == parsed_id
        )
    )

    # Delete the rule
    await db.delete(rule)

    await db.commit()

    await on_rule_set_modified(db, rule_set_id)

    return True


async def add_rule_to_set(rule_set_id: str, rule_data: dict, db: AsyncSession) -> Rule:
    rule = Rule(
        rule_set_id=uuid.UUID(rule_set_id),
        **rule_data,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    await on_rule_set_modified(db, rule_set_id)
    return rule
