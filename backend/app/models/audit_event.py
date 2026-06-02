"""AuditEvent — a single immutable row per meaningful action taken in
the system. Backs the per-BRD audit timeline (Slice 3) and the
"decision attribution" footer everywhere a verb-button writes state.

Design choice: append-only event log alongside the existing
`decided_by` columns on MergeProposal / LiveRuleRepository / ImpactRun.
The event log doesn't replace those columns (they're still read on the
hot path and indexed); it captures the FULL chronology — including
events that don't have a natural home column (rule_set approval,
suite execution, rule edits) — so the timeline doesn't need to UNION
six different join queries.

Each row records:
  - WHO took the action (`actor`, free-text now; real auth later)
  - WHAT happened (`action`, e.g. "RULE_SET_APPROVED")
  - WHICH entity (`entity_type` + `entity_id`)
  - WHY (`rationale`, optional free-text)
  - CONTEXT (`brd_id`, `repository_id`) for cheap filtering
  - PAYLOAD (`metadata`) for structured side data (counts, version
    numbers, before/after enums) the UI may want to render inline
"""
import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    String, Text, DateTime, JSON, Enum as SAEnum, Index, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def UUID(as_uuid: bool = True):  # noqa: N802 — dialect-agnostic alias
    return Uuid(as_uuid=as_uuid)


class AuditAction(str, enum.Enum):
    # BRD lifecycle
    BRD_UPLOADED = "BRD_UPLOADED"
    RULES_EXTRACTED = "RULES_EXTRACTED"

    # Rule-set lifecycle
    RULE_SET_APPROVED = "RULE_SET_APPROVED"
    RULE_EDITED = "RULE_EDITED"
    RULE_DELETED = "RULE_DELETED"
    RULE_ADDED = "RULE_ADDED"

    # Merge / live repo
    MERGE_PROPOSAL_CREATED = "MERGE_PROPOSAL_CREATED"
    MERGE_PROPOSAL_APPLIED = "MERGE_PROPOSAL_APPLIED"
    MERGE_PROPOSAL_REJECTED = "MERGE_PROPOSAL_REJECTED"
    MERGE_ITEM_DECIDED = "MERGE_ITEM_DECIDED"
    VERSION_PROMOTED = "VERSION_PROMOTED"

    # Impact + tests
    IMPACT_RUN_STARTED = "IMPACT_RUN_STARTED"
    IMPACT_RUN_COMPLETED = "IMPACT_RUN_COMPLETED"
    SUITE_GENERATED = "SUITE_GENERATED"
    SUITE_EXECUTED = "SUITE_EXECUTED"


class AuditEntityType(str, enum.Enum):
    BRD = "BRD"
    RULE_SET = "RULE_SET"
    RULE = "RULE"
    MERGE_PROPOSAL = "MERGE_PROPOSAL"
    LIVE_REPO = "LIVE_REPO"
    LIVE_VERSION = "LIVE_VERSION"
    IMPACT_RUN = "IMPACT_RUN"
    TEST_SUITE = "TEST_SUITE"


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        # Dominant query: timeline for one BRD, newest first.
        Index("ix_audit_brd_created", "brd_id", "created_at"),
        # Secondary: timeline for one repo (production-side audit view).
        Index("ix_audit_repo_created", "repository_id", "created_at"),
        # Tertiary: lookup by entity (e.g. "show me everything that
        # happened to merge proposal X").
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    action: Mapped[AuditAction] = mapped_column(SAEnum(AuditAction), index=True)
    entity_type: Mapped[AuditEntityType] = mapped_column(SAEnum(AuditEntityType))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))

    # Free-text attribution. Will get tightened to a real user FK once
    # auth lands; today this is whatever the UI sent.
    actor: Mapped[str] = mapped_column(String(128), default="system")
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cheap-filter context — denormalized so the BRD page can pull its
    # whole timeline with one indexed query.
    brd_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Structured side data — version numbers, before/after enums,
    # rule counts. Anything the UI wants to render inline next to the
    # event without a follow-up fetch.
    event_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
