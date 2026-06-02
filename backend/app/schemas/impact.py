from pydantic import BaseModel, Field
from typing import Any


class CreateImpactRunRequest(BaseModel):
    repository_id: str
    candidate_version_id: str
    base_version_id: str | None = Field(
        default=None,
        description="Omit to compare candidate against an empty baseline (all APPROVED).",
    )
    loan_record_filter: dict | None = Field(
        default=None,
        description="Optional filter (slice 2 supports just {'limit': N}; future slices: cohort filters).",
    )
    created_by: str | None = None
    rationale: str | None = Field(
        default=None,
        description=(
            "Optional reason for kicking off this run — e.g. 'pre-promotion "
            "regression check' or 'investigating drift in PRIME segment'."
        ),
        max_length=2000,
    )


class ImpactRunResponse(BaseModel):
    id: str
    repository_id: str
    base_version_id: str | None
    candidate_version_id: str
    status: str
    summary: dict[str, Any] | None
    error: str | None
    created_at: str
    completed_at: str | None
    created_by: str | None
    rationale: str | None = None
