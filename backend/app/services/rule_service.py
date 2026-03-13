import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.rule import RuleSet, Rule, RuleSetStatus


async def list_rule_sets(db: AsyncSession) -> list[RuleSet]:
    result = await db.execute(
        select(RuleSet).options(selectinload(RuleSet.rules)).order_by(RuleSet.created_at.desc())
    )
    return list(result.scalars().all())


async def get_rule_set(rule_set_id: str, db: AsyncSession) -> RuleSet | None:
    result = await db.execute(
        select(RuleSet)
        .where(RuleSet.id == uuid.UUID(rule_set_id))
        .options(selectinload(RuleSet.rules))
    )
    return result.scalar_one_or_none()


async def approve_rule_set(rule_set_id: str, db: AsyncSession) -> RuleSet | None:
    rs = await get_rule_set(rule_set_id, db)
    if not rs:
        return None
    rs.status = RuleSetStatus.APPROVED
    await db.commit()
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
    result = await db.execute(select(Rule).where(Rule.id == uuid.UUID(rule_id)))
    rule = result.scalar_one_or_none()
    if not rule:
        return None
    for key, value in updates.items():
        if value is not None and hasattr(rule, key):
            setattr(rule, key, value)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_rule(rule_id: str, db: AsyncSession) -> bool:
    result = await db.execute(select(Rule).where(Rule.id == uuid.UUID(rule_id)))
    rule = result.scalar_one_or_none()
    if not rule:
        return False
    await db.delete(rule)
    await db.commit()
    return True


async def add_rule_to_set(rule_set_id: str, rule_data: dict, db: AsyncSession) -> Rule:
    rule = Rule(
        rule_set_id=uuid.UUID(rule_set_id),
        **rule_data,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule
