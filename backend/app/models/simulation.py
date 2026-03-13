import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, Enum as SAEnum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SimulationStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_name: Mapped[str] = mapped_column(String(256))
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"))
    rule_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rule_sets.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[SimulationStatus] = mapped_column(SAEnum(SimulationStatus), default=SimulationStatus.PENDING)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    dataset = relationship("Dataset", back_populates="simulations")
    rule_set = relationship("RuleSet", back_populates="simulations")
    results = relationship("SimulationResult", back_populates="simulation", cascade="all, delete-orphan")


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id"))
    summary_stats: Mapped[dict] = mapped_column(JSON)
    segment_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    customer_diffs_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    financial_impact: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    conflict_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    simulation = relationship("Simulation", back_populates="results")


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    simulation_ids: Mapped[dict] = mapped_column(JSON, default=list)
    comparison_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
