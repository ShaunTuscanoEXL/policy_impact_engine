import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class LoanRecord(Base):
    __tablename__ = "loan_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_application_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_loan_records_request_gin", "request_payload", postgresql_using="gin"),
        Index("idx_loan_records_response_gin", "response_payload", postgresql_using="gin"),
    )
