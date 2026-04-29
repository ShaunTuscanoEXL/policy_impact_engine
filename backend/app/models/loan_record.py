import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Index, JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


# Dialect-aware payload type: native JSONB on Postgres (preserving index/query
# performance + the GIN indexes below), plain JSON on other backends so the
# schema can be created against SQLite for tests.
_PAYLOAD_TYPE = JSON().with_variant(JSONB(), "postgresql")


class LoanRecord(Base):
    __tablename__ = "loan_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_application_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    request_payload: Mapped[dict] = mapped_column(_PAYLOAD_TYPE, nullable=False)
    response_payload: Mapped[dict] = mapped_column(_PAYLOAD_TYPE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # GIN indexes are Postgres-only; SQLAlchemy silently skips the
    # postgresql_using kwarg on other dialects but the index is still
    # registered. Wrap in __table_args__ so we can guard at create time.
    __table_args__ = (
        Index("idx_loan_records_request_gin", "request_payload", postgresql_using="gin"),
        Index("idx_loan_records_response_gin", "response_payload", postgresql_using="gin"),
    )
