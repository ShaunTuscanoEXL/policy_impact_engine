"""Schemas for audit-event responses."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    id: str
    action: str
    entity_type: str
    entity_id: str
    actor: str
    rationale: str | None
    brd_id: str | None
    repository_id: str | None
    metadata: dict[str, Any] | None = None
    created_at: str
