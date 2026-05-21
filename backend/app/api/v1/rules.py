from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import rule_service
from app.schemas.rule import (
    ApproveRuleSetRequest,
    RuleResponse,
    RuleSetResponse,
    RuleUpdateRequest,
    RuleDefinition,
)

router = APIRouter(tags=["Rules"])


def _rule_set_to_response(rs) -> RuleSetResponse:
    return RuleSetResponse(
        id=str(rs.id),
        brd_document_id=str(rs.brd_document_id),
        version=rs.version,
        name=rs.name,
        description=rs.description,
        status=rs.status.value,
        created_at=rs.created_at.isoformat(),
        approved_by=getattr(rs, "approved_by", None),
        approved_at=rs.approved_at.isoformat() if getattr(rs, "approved_at", None) else None,
        approval_notes=getattr(rs, "approval_notes", None),
        rules=[
            RuleResponse(
                id=str(r.id),
                rule_id=r.rule_id,
                rule_name=r.rule_name,
                description=r.description,
                rule_type=r.rule_type.value,
                subsystem=r.subsystem.value if r.subsystem else None,
                canonical_key=r.canonical_key,
                conditions=r.conditions if isinstance(r.conditions, list) else [],
                actions=r.actions if isinstance(r.actions, list) else [],
                priority=r.priority,
                confidence=r.confidence,
                compiled_expression=r.compiled_expression,
                has_conflicts=r.has_conflicts,
                conflict_details=r.conflict_details,
                policy_intent=getattr(r, "policy_intent", None),
                regulatory_citation=getattr(r, "regulatory_citation", None),
            )
            for r in rs.rules
        ],
    )


def _rule_to_response(r) -> RuleResponse:
    return RuleResponse(
        id=str(r.id),
        rule_id=r.rule_id,
        rule_name=r.rule_name,
        description=r.description,
        rule_type=r.rule_type.value,
        subsystem=r.subsystem.value if r.subsystem else None,
        canonical_key=r.canonical_key,
        conditions=r.conditions if isinstance(r.conditions, list) else [],
        actions=r.actions if isinstance(r.actions, list) else [],
        priority=r.priority,
        confidence=r.confidence,
        compiled_expression=r.compiled_expression,
        has_conflicts=r.has_conflicts,
        conflict_details=r.conflict_details,
        policy_intent=getattr(r, "policy_intent", None),
        regulatory_citation=getattr(r, "regulatory_citation", None),
    )


# ── Rule Set endpoints ──────────────────────────────────────────────


@router.get("/rule-sets", response_model=list[RuleSetResponse])
async def list_rule_sets(db: AsyncSession = Depends(get_db)):
    rule_sets = await rule_service.list_rule_sets(db)
    return [_rule_set_to_response(rs) for rs in rule_sets]


@router.get("/rule-sets/{rule_set_id}", response_model=RuleSetResponse)
async def get_rule_set(rule_set_id: str, db: AsyncSession = Depends(get_db)):
    rs = await rule_service.get_rule_set(rule_set_id, db)
    if not rs:
        raise HTTPException(404, "Rule set not found")
    return _rule_set_to_response(rs)


@router.patch("/rule-sets/{rule_set_id}/approve", response_model=RuleSetResponse)
async def approve_rule_set(
    rule_set_id: str,
    body: ApproveRuleSetRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    rs = await rule_service.approve_rule_set(
        rule_set_id,
        db,
        approved_by=(body.approved_by if body else None),
        approval_notes=(body.approval_notes if body else None),
    )
    if not rs:
        raise HTTPException(404, "Rule set not found")
    return _rule_set_to_response(rs)


@router.post("/rule-sets/{rule_set_id}/version", response_model=RuleSetResponse)
async def create_rule_set_version(rule_set_id: str, db: AsyncSession = Depends(get_db)):
    rs = await rule_service.create_rule_set_version(rule_set_id, db)
    if not rs:
        raise HTTPException(404, "Rule set not found")
    return _rule_set_to_response(rs)


# ── Individual Rule endpoints ────────────────────────────────────────


@router.post("/rule-sets/{rule_set_id}/rules", response_model=RuleResponse)
async def add_rule(
    rule_set_id: str,
    rule_data: RuleDefinition,
    db: AsyncSession = Depends(get_db),
):
    rs = await rule_service.get_rule_set(rule_set_id, db)
    if not rs:
        raise HTTPException(404, "Rule set not found")
    rule = await rule_service.add_rule_to_set(
        rule_set_id,
        {
            "rule_id": rule_data.rule_id,
            "rule_name": rule_data.rule_name,
            "description": rule_data.description,
            "rule_type": rule_data.rule_type,
            "conditions": [c.model_dump() for c in rule_data.conditions],
            "actions": [a.model_dump() for a in rule_data.actions],
            "priority": rule_data.priority,
            "confidence": rule_data.confidence,
            "source_section": rule_data.source_section,
        },
        db,
    )
    return _rule_to_response(rule)


@router.patch("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    body: RuleUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    updates = body.model_dump(exclude_unset=True)
    # Serialize nested pydantic models to dicts for JSON columns
    if "conditions" in updates and updates["conditions"] is not None:
        updates["conditions"] = [c.model_dump() for c in body.conditions]
    if "actions" in updates and updates["actions"] is not None:
        updates["actions"] = [a.model_dump() for a in body.actions]
    rule = await rule_service.update_rule(rule_id, updates, db)
    if not rule:
        raise HTTPException(404, "Rule not found")
    return _rule_to_response(rule)


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await rule_service.delete_rule(rule_id, db)
    if not deleted:
        raise HTTPException(404, "Rule not found")
    return {"detail": "Rule deleted"}
