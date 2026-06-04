"""ImpactRun — record of a "what changes if we apply candidate version
on top of base version" comparison run.

Slice 2 ships a synchronous in-process runner. A future slice can swap
the implementation to Celery without changing the API or model.
"""
import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    String, Text, Integer, DateTime, JSON, ForeignKey, Enum as SAEnum, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def UUID(as_uuid: bool = True):  # noqa: N802 — dialect-agnostic alias
    return Uuid(as_uuid=as_uuid)


class ImpactRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ImpactRun(Base):
    __tablename__ = "impact_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("live_rule_repositories.id")
    )
    base_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("live_rule_versions.id"), nullable=True
    )
    candidate_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("live_rule_versions.id")
    )
    loan_record_filter: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[ImpactRunStatus] = mapped_column(
        SAEnum(ImpactRunStatus), default=ImpactRunStatus.PENDING
    )

    # Summary structure (see docs/plans/2026-04-30-live-rule-repository.md §4.7):
    # {
    #   "total_loans": 10000,
    #   "decision_distribution": {
    #     "base":      {"APPROVED": 6240, "FLAGGED": 1180, "REJECTED": 2580},
    #     "candidate": {"APPROVED": 5970, "FLAGGED": 1310, "REJECTED": 2720}
    #   },
    #   "decision_flips": {
    #     "approved_to_rejected": 320,
    #     "rejected_to_approved": 50,
    #     "approved_to_flagged": 130,
    #     "flagged_to_approved": 20,
    #     ...
    #   },
    #   "by_subsystem": {"DTI_GATE": {"flips_caused": 280}},
    #   "by_segment":   {"PRIME": {"approval_rate_change": -0.034}, ...}
    # }
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
