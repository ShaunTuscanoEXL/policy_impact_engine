import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, DateTime, Enum as SAEnum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TestCaseCategory(str, enum.Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    BOUNDARY = "BOUNDARY"
    EDGE = "EDGE"
    INTERACTION = "INTERACTION"


class TestCaseSuite(Base):
    __tablename__ = "test_case_suites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rule_sets.id"))
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    cases_by_category: Mapped[dict] = mapped_column(JSON)
    coverage_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    suggested_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rule_set = relationship("RuleSet", back_populates="test_case_suites")
    test_cases = relationship("TestCase", back_populates="suite", cascade="all, delete-orphan")


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suite_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("test_case_suites.id"))
    test_case_id: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_rule_ids: Mapped[dict] = mapped_column(JSON)
    category: Mapped[TestCaseCategory] = mapped_column(SAEnum(TestCaseCategory))
    input_values: Mapped[dict] = mapped_column(JSON, default=dict)
    filter_logic: Mapped[dict] = mapped_column(JSON)
    matched_loan_ids: Mapped[list] = mapped_column(JSON, default=list)
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    expected_outcome: Mapped[dict] = mapped_column(JSON)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    suite = relationship("TestCaseSuite", back_populates="test_cases")
