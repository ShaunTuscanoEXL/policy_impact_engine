"""audit_service — single chokepoint for recording AuditEvents.

Every verb-button in the system (apply merge / approve rule_set /
promote version / run impact / execute suite) calls `record_event`
with the actor + rationale captured from the request. Failures here
are logged and SWALLOWED — we never want to fail a successful action
just because the audit row didn't write.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditAction, AuditEntityType, AuditEvent

logger = logging.getLogger(__name__)


async def record_event(
    db: AsyncSession,
    *,
    action: AuditAction,
    entity_type: AuditEntityType,
    entity_id: uuid.UUID,
    actor: str | None = None,
    rationale: str | None = None,
    brd_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditEvent | None:
    """Append an event row. Returns the saved event, or None on failure.

    `commit=False` lets a caller batch the audit write into the same
    transaction as the underlying state change so they commit
    atomically. With `commit=True` (default), the event flushes
    immediately so a later rollback in the caller doesn't lose it —
    the audit log is intentionally optimistic.
    """
    try:
        event = AuditEvent(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=(actor or "system").strip()[:128] or "system",
            rationale=(rationale.strip() if rationale else None) or None,
            brd_id=brd_id,
            repository_id=repository_id,
            event_metadata=metadata or None,
        )
        db.add(event)
        if commit:
            await db.commit()
            await db.refresh(event)
        else:
            await db.flush()
        return event
    except Exception as e:
        logger.warning("audit_service.record_event failed: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        return None


async def list_events_for_brd(
    db: AsyncSession,
    *,
    brd_id: uuid.UUID,
    limit: int = 200,
) -> list[AuditEvent]:
    """Timeline view for the BRD detail page."""
    rows = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.brd_id == brd_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())


async def list_events_for_repo(
    db: AsyncSession,
    *,
    repository_id: uuid.UUID,
    limit: int = 200,
) -> list[AuditEvent]:
    """Timeline view for the live-repo / production page."""
    rows = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.repository_id == repository_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())


async def list_events_for_entity(
    db: AsyncSession,
    *,
    entity_type: AuditEntityType,
    entity_id: uuid.UUID,
    limit: int = 50,
) -> list[AuditEvent]:
    """All events for one entity (e.g. one merge proposal)."""
    rows = await db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.entity_type == entity_type,
            AuditEvent.entity_id == entity_id,
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())
