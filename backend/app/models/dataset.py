import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class DatasetFileType(str, enum.Enum):
    CSV = "CSV"
    JSON = "JSON"


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(String(1024))
    file_type: Mapped[DatasetFileType] = mapped_column(SAEnum(DatasetFileType))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sample_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    column_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    baseline_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    simulations = relationship("Simulation", back_populates="dataset")
