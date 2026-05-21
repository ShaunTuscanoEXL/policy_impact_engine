"""Live Rule Repository — authoritative versioned rule baseline.

A LiveRuleRepository represents the current production rule set for a
(product, jurisdiction) pair. Each merge of a BRD produces a new
LiveRuleVersion (full snapshot + generated python_export). LiveRuleEntry
rows denormalize the HEAD snapshot for fast reads.

See docs/plans/2026-04-30-live-rule-repository.md §4 for the full data
model rationale.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Text, Integer, Boolean, DateTime, JSON, ForeignKey, UniqueConstraint, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


def UUID(as_uuid: bool = True):  # noqa: N802 — dialect-agnostic alias
    return Uuid(as_uuid=as_uuid)
from app.database import Base


class LiveRuleRepository(Base):
    __tablename__ = "live_rule_repositories"
    __table_args__ = (
        UniqueConstraint("product", "jurisdiction", name="uq_live_repo_product_jurisdiction"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256))
    product: Mapped[str] = mapped_column(String(64))           # e.g. "PERSONAL"
    jurisdiction: Mapped[str] = mapped_column(String(8))       # e.g. "US"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    # The version that is "live in production" — may NOT be the latest
    # (current_version). Lets a team create v3 from a BRD, validate it via
    # impact + suite execution, then explicitly promote it. Nullable so
    # existing repos don't have to be migrated; the promote endpoint and
    # the production-backfill on startup will populate it.
    production_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("live_rule_versions.id", use_alter=True, name="fk_repo_production_version"),
        nullable=True,
    )
    production_promoted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    production_promoted_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Slice 1: free-text justification captured at promotion time.
    production_promotion_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Disambiguate: there are now TWO FK paths between repos and versions
    # (LiveRuleVersion.repository_id, plus the new
    # LiveRuleRepository.production_version_id pointer). The `versions`
    # collection follows the historical ownership FK only.
    versions = relationship(
        "LiveRuleVersion",
        back_populates="repository",
        cascade="all, delete-orphan",
        order_by="LiveRuleVersion.version_number",
        foreign_keys="[LiveRuleVersion.repository_id]",
    )
    entries = relationship(
        "LiveRuleEntry",
        back_populates="repository",
        cascade="all, delete-orphan",
    )


class LiveRuleVersion(Base):
    __tablename__ = "live_rule_versions"
    __table_args__ = (
        UniqueConstraint("repository_id", "version_number", name="uq_live_version_repo_n"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("live_rule_repositories.id")
    )
    version_number: Mapped[int] = mapped_column(Integer)

    # Lineage
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("live_rule_versions.id"), nullable=True
    )
    source_brd_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brd_documents.id"), nullable=True
    )
    merge_proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merge_proposals.id"), nullable=True
    )

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full snapshot of all active rules at this version. Each entry is the
    # rule's serialized form (id, rule_id, rule_name, subsystem, conditions,
    # actions, priority, canonical_key, semantic_signature, …).
    rule_snapshot: Mapped[list] = mapped_column(JSON, default=list)

    # Generated rules.py for this version (cached at apply time).
    python_export: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    repository = relationship(
        "LiveRuleRepository",
        back_populates="versions",
        foreign_keys="[LiveRuleVersion.repository_id]",
    )


class LiveRuleEntry(Base):
    """HEAD-only denormalized index of the active rules in a repo.

    Rebuilt on every apply. Lets us answer 'what is the active rule for
    canonical_key X right now?' in O(log n) without parsing the snapshot
    JSON.
    """
    __tablename__ = "live_rule_entries"
    __table_args__ = (
        UniqueConstraint("repository_id", "canonical_key", name="uq_live_entry_repo_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("live_rule_repositories.id")
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rules.id"))
    canonical_key: Mapped[str] = mapped_column(String(128), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_in_version: Mapped[int] = mapped_column(Integer)
    last_modified_in_version: Mapped[int] = mapped_column(Integer)

    repository = relationship("LiveRuleRepository", back_populates="entries")
