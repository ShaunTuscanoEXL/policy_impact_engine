import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class FileType(str, enum.Enum):
    PDF = "PDF"
    DOCX = "DOCX"


class BrdDocument(Base):
    __tablename__ = "brd_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(512))
    file_path: Mapped[str] = mapped_column(String(1024))
    file_type: Mapped[FileType] = mapped_column(SAEnum(FileType))
    parsed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rule_sets = relationship("RuleSet", back_populates="brd_document", cascade="all, delete-orphan")
