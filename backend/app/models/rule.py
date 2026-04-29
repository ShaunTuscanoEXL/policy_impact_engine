import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, Enum as SAEnum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class RuleSetStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"


class RuleType(str, enum.Enum):
    ELIGIBILITY = "ELIGIBILITY"
    PRICING = "PRICING"
    CAP = "CAP"
    THRESHOLD = "THRESHOLD"
    SCORING = "SCORING"


class Subsystem(str, enum.Enum):
    """Finer-grained classification of rules — used by the live rule
    repository for grouping in codegen output and routing in HITL UI.

    See docs/plans/2026-04-30-live-rule-repository.md §5 for definitions.
    """
    BUREAU_GATE = "BUREAU_GATE"
    INCOME_GATE = "INCOME_GATE"
    DTI_GATE = "DTI_GATE"
    EMPLOYMENT_GATE = "EMPLOYMENT_GATE"
    BANKING_BEHAVIOR = "BANKING_BEHAVIOR"
    PRICING_TIER = "PRICING_TIER"
    RATE_MODIFIER = "RATE_MODIFIER"
    AMOUNT_CAP = "AMOUNT_CAP"
    FRAUD_SIGNAL = "FRAUD_SIGNAL"
    REGULATORY_FLOOR = "REGULATORY_FLOOR"
    EXPOSURE_LIMIT = "EXPOSURE_LIMIT"
    SCORING_MODEL = "SCORING_MODEL"
    UNCLASSIFIED = "UNCLASSIFIED"


class RuleSet(Base):
    __tablename__ = "rule_sets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brd_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brd_documents.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RuleSetStatus] = mapped_column(SAEnum(RuleSetStatus), default=RuleSetStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    brd_document = relationship("BrdDocument", back_populates="rule_sets")
    rules = relationship("Rule", back_populates="rule_set", cascade="all, delete-orphan")
    test_case_suites = relationship("TestCaseSuite", back_populates="rule_set", cascade="all, delete-orphan")


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rule_sets.id"))
    rule_id: Mapped[str] = mapped_column(String(32))
    rule_name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_type: Mapped[RuleType] = mapped_column(SAEnum(RuleType))
    conditions: Mapped[dict] = mapped_column(JSON)
    actions: Mapped[dict] = mapped_column(JSON)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    compiled_expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_section: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_conflicts: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Live Rule Repository support (Slice 0) ────────────────────────────
    # Stable cross-BRD identity. Same rule reappearing in a later BRD will
    # produce the same canonical_key so the merge engine can recognize it.
    canonical_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # Finer-grained subsystem (BUREAU_GATE, DTI_GATE, …). RuleType stays as
    # the broad category (ELIGIBILITY/PRICING/…); Subsystem is what the
    # codegen output and HITL workbench group by.
    subsystem: Mapped[Subsystem] = mapped_column(
        SAEnum(Subsystem),
        default=Subsystem.UNCLASSIFIED,
        index=True,
    )

    # Normalized form of the rule used for diffing. Shape:
    # {"fields": [...], "operators": [...], "thresholds": [...],
    #  "action_types": [...], "logic": "AND|OR"}
    semantic_signature: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Lineage: when this rule replaces another via SUPERSEDE in a merge.
    supersedes_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rules.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rule_set = relationship("RuleSet", back_populates="rules")
