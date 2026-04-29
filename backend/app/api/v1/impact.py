"""Impact-run endpoints — start a new run, fetch a single run, list."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.impact import CreateImpactRunRequest, ImpactRunResponse
from app.services import impact_service as svc

router = APIRouter(prefix="/impact-run", tags=["Impact Runs"])


def _to_response(run) -> ImpactRunResponse:
    return ImpactRunResponse(
        id=str(run.id),
        repository_id=str(run.repository_id),
        base_version_id=str(run.base_version_id) if run.base_version_id else None,
        candidate_version_id=str(run.candidate_version_id),
        status=run.status.value,
        summary=run.summary,
        error=run.error,
        created_at=run.created_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        created_by=run.created_by,
    )


@router.post("", response_model=ImpactRunResponse, status_code=201)
async def create_impact_run(
    payload: CreateImpactRunRequest, db: AsyncSession = Depends(get_db)
):
    try:
        run = await svc.execute_impact_run(
            db,
            repository_id=uuid.UUID(payload.repository_id),
            base_version_id=(uuid.UUID(payload.base_version_id) if payload.base_version_id else None),
            candidate_version_id=uuid.UUID(payload.candidate_version_id),
            loan_record_filter=payload.loan_record_filter,
            created_by=payload.created_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_response(run)


@router.get("/{run_id}", response_model=ImpactRunResponse)
async def get_impact_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    run = await svc.get_impact_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Impact run not found")
    return _to_response(run)


@router.get("", response_model=list[ImpactRunResponse])
async def list_impact_runs(
    repository_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    runs = await svc.list_impact_runs(
        db, repository_id=uuid.UUID(repository_id) if repository_id else None
    )
    return [_to_response(r) for r in runs]
