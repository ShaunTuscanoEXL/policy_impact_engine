from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.dashboard_service import (
    get_activity_feed,
    get_dashboard_stats,
    get_dashboard_trends,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Hero dashboard payload — counts, pipeline funnel, live repos with
    production version + has_unpromoted_candidate flag, latest impact run
    summary, latest suite-execution summary, pending merge queue."""
    return await get_dashboard_stats(db)


@router.get("/activity")
async def dashboard_activity(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Recent events across BRDs, versions, promotions, merge proposals,
    impact runs, and suite executions — newest first."""
    return await get_activity_feed(db, limit=limit)


@router.get("/trends")
async def dashboard_trends(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Time-series data for dashboard charts: approval-rate per impact
    run + rule-count per version."""
    return await get_dashboard_trends(db, limit=limit)
