from pydantic import BaseModel, Field
from typing import Any


class CreateMergeProposalRequest(BaseModel):
    repository_id: str
    source_rule_set_id: str = Field(description="Candidate rule set produced from a BRD")


class MergeItemUpdateRequest(BaseModel):
    user_action: str | None = Field(
        default=None,
        description="ACCEPT | REJECT | SUPERSEDE | SUPERSEDE_GROUP | DROP | KEEP_BOTH | EDIT_NEEDED | RETIRE",
    )
    user_edits: dict | None = None
    notes: str | None = None


class MergeApplyRequest(BaseModel):
    decided_by: str | None = Field(
        default=None,
        description="Username/identifier of the reviewer applying the merge",
    )


class MergeItemResponse(BaseModel):
    id: str
    category: str
    severity: str
    canonical_key: str | None
    incoming_rule_id: str | None
    live_rule_id: str | None
    diff: dict[str, Any] | None
    suggested_action: str
    user_action: str | None
    user_edits: dict | None
    notes: str | None
    rationale: str | None
    confidence: float


class MergeProposalResponse(BaseModel):
    id: str
    repository_id: str
    base_version: int
    source_brd_id: str
    source_rule_set_id: str
    status: str
    summary: str | None
    decided_by: str | None
    decided_at: str | None
    created_at: str
    items: list[MergeItemResponse] = []
    counts_by_category: dict[str, int] = {}
    counts_by_severity: dict[str, int] = {}
    blockers: list[str] = []  # item ids that block apply (hard + unresolved)


class MergeApplyResponse(BaseModel):
    applied: bool
    new_version_number: int | None = None
    new_version_id: str | None = None
    blockers: list[str] = []
    summary: str | None = None
