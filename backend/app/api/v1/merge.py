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
    MergeItemResponse,
    MergeItemUpdateRequest,
    MergeProposalResponse,
)
from app.services import live_repo_service as svc

router = APIRouter(prefix="/merge-proposal", tags=["Merge Proposals"])


def _item_to_response(item) -> MergeItemResponse:
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
    )


def _proposal_to_response(proposal) -> MergeProposalResponse:
    items = [_item_to_response(i) for i in proposal.items]

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
    return _proposal_to_response(proposal)


@router.get("/{proposal_id}", response_model=MergeProposalResponse)
async def get_proposal(proposal_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    proposal = await svc.get_merge_proposal(db, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Merge proposal not found")
    return _proposal_to_response(proposal)


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


@router.post("/{proposal_id}/apply", response_model=MergeApplyResponse)
async def apply_proposal(
    proposal_id: uuid.UUID,
    payload: MergeApplyRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        new_version, blockers = await svc.apply_merge_proposal(
            db, proposal_id=proposal_id, decided_by=payload.decided_by
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
