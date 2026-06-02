"""Merge Proposal — HITL reconciliation between an incoming BRD's rule
set and a Live Rule Repository.

A MergeProposal is created when a candidate rule_set is reconciled
against a live repo. Each MergeProposalItem captures one diff (rule-vs-
rule or new/retired) along with a suggested_action and the human's
final user_action.

See docs/plans/2026-04-30-live-rule-repository.md §6 for the conflict
taxonomy.
"""
import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    String, Text, Integer, DateTime, JSON, ForeignKey, Enum as SAEnum, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


def UUID(as_uuid: bool = True):  # noqa: N802 — dialect-agnostic alias
    return Uuid(as_uuid=as_uuid)
from app.database import Base


class MergeProposalStatus(str, enum.Enum):
    PENDING = "PENDING"      # awaiting reviewer decisions on items
    APPROVED = "APPROVED"    # all hard-conflict items resolved, ready to apply
    REJECTED = "REJECTED"    # reviewer dismissed the whole proposal
    APPLIED = "APPLIED"      # promoted to a new live version


class MergeItemCategory(str, enum.Enum):
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    THRESHOLD_TIGHTENING = "THRESHOLD_TIGHTENING"
    THRESHOLD_RELAXATION = "THRESHOLD_RELAXATION"
    OPPOSITE_DIRECTION = "OPPOSITE_DIRECTION"
    TIERED_REPLACEMENT = "TIERED_REPLACEMENT"
    OVERLAPPING_RANGE = "OVERLAPPING_RANGE"
    NEW_RULE = "NEW_RULE"
    REMOVED_RULE = "REMOVED_RULE"
    ACTION_DRIFT = "ACTION_DRIFT"
    COVERAGE_GAP = "COVERAGE_GAP"


class MergeItemSeverity(str, enum.Enum):
    INFO = "INFO"      # informational, not blocking
    SOFT = "SOFT"      # warn but allow apply
    HARD = "HARD"      # block apply until user_action set


class MergeSuggestedAction(str, enum.Enum):
    ACCEPT = "ACCEPT"            # take the incoming rule
    REJECT = "REJECT"            # discard the incoming rule, keep live
    SUPERSEDE = "SUPERSEDE"      # incoming replaces live (lineage recorded)
    SUPERSEDE_GROUP = "SUPERSEDE_GROUP"  # whole tier group replaced
    DROP = "DROP"                # incoming is duplicate, drop silently
    KEEP_BOTH = "KEEP_BOTH"      # both coexist (rare; needs disjoint conditions)
    EDIT_NEEDED = "EDIT_NEEDED"  # reviewer must hand-edit before apply
    RETIRE = "RETIRE"            # mark a live rule inactive
    NEEDS_HUMAN = "NEEDS_HUMAN"  # default for hard conflicts


class MergeProposal(Base):
    __tablename__ = "merge_proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("live_rule_repositories.id")
    )
    base_version: Mapped[int] = mapped_column(Integer)              # which version we diffed against
    source_brd_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brd_documents.id")
    )
    source_rule_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rule_sets.id")
    )
    status: Mapped[MergeProposalStatus] = mapped_column(
        SAEnum(MergeProposalStatus), default=MergeProposalStatus.PENDING
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items = relationship(
        "MergeProposalItem",
        back_populates="proposal",
        cascade="all, delete-orphan",
    )


class MergeProposalItem(Base):
    __tablename__ = "merge_proposal_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merge_proposals.id")
    )
    category: Mapped[MergeItemCategory] = mapped_column(SAEnum(MergeItemCategory))
    severity: Mapped[MergeItemSeverity] = mapped_column(
        SAEnum(MergeItemSeverity), default=MergeItemSeverity.INFO
    )

    # Either side may be null depending on the category:
    #   NEW_RULE       → live_rule_id null
    #   REMOVED_RULE   → incoming_rule_id null
    incoming_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules.id"), nullable=True
    )
    live_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules.id"), nullable=True
    )

    canonical_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # Field-level diff for UI rendering. Shape depends on category, e.g.
    # {"field": "dti_ratio", "old_threshold": 0.40, "new_threshold": 0.35,
    #  "old_action": "REJECT", "new_action": "REJECT"}
    diff: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    suggested_action: Mapped[MergeSuggestedAction] = mapped_column(
        SAEnum(MergeSuggestedAction), default=MergeSuggestedAction.NEEDS_HUMAN
    )
    user_action: Mapped[MergeSuggestedAction | None] = mapped_column(
        SAEnum(MergeSuggestedAction), nullable=True
    )
    user_edits: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(default=1.0)

    proposal = relationship("MergeProposal", back_populates="items")
