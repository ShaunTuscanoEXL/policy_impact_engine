"""Audit-event endpoints — query the chronological event log.

Slice 1 lays the foundation by writing events from every verb-button.
Slice 3 will consume this from the BRD detail page (timeline panel)
and the live-repo page (production audit view).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit_event import AuditEntityType, AuditEvent
from app.schemas.audit import AuditEventResponse
from app.services import audit_service

router = APIRouter(prefix="/audit-events", tags=["Audit"])


def _to_response(ev: AuditEvent) -> AuditEventResponse:
    action_val = ev.action.value if hasattr(ev.action, "value") else str(ev.action)
    entity_val = ev.entity_type.value if hasattr(ev.entity_type, "value") else str(ev.entity_type)
    return AuditEventResponse(
        id=str(ev.id),
        action=action_val,
        entity_type=entity_val,
        entity_id=str(ev.entity_id),
        actor=ev.actor,
        rationale=ev.rationale,
        brd_id=str(ev.brd_id) if ev.brd_id else None,
        repository_id=str(ev.repository_id) if ev.repository_id else None,
        metadata=ev.event_metadata,
        created_at=ev.created_at.isoformat(),
    )


@router.get("", response_model=list[AuditEventResponse])
async def list_events(
    brd_id: str | None = Query(default=None),
    repository_id: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Query the audit log. Supports four mutually-exclusive shapes:

    - `?brd_id=...`        timeline for one BRD (Slice 3 main consumer)
    - `?repository_id=...` timeline for one repo (production audit)
    - `?entity_type=X&entity_id=Y` everything that happened to one entity
    - (no filters)         everything, newest first

    Returns events newest-first, capped at `limit`.
    """
    if brd_id:
        try:
            uid = uuid.UUID(brd_id)
        except ValueError:
            raise HTTPException(400, "Invalid brd_id")
        events = await audit_service.list_events_for_brd(db, brd_id=uid, limit=limit)
    elif repository_id:
        try:
            uid = uuid.UUID(repository_id)
        except ValueError:
            raise HTTPException(400, "Invalid repository_id")
        events = await audit_service.list_events_for_repo(db, repository_id=uid, limit=limit)
    elif entity_type and entity_id:
        try:
            et = AuditEntityType(entity_type.upper())
            eid = uuid.UUID(entity_id)
        except ValueError as e:
            raise HTTPException(400, f"Invalid entity filter: {e}")
        events = await audit_service.list_events_for_entity(
            db, entity_type=et, entity_id=eid, limit=limit
        )
    else:
        from sqlalchemy import select
        rows = await db.execute(
            select(AuditEvent)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
        events = list(rows.scalars())

    return [_to_response(e) for e in events]
