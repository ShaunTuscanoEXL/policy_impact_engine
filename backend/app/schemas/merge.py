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


class MergeRulePayload(BaseModel):
    """Full rule shape exposed inline on merge items so the workbench
    can render the actual policy (rule name, conditions, actions with
    target_field+value, subsystem, etc.) without losing fidelity to
    the canonical projection in `diff`."""
    rule_id: str | None = None
    rule_name: str | None = None
    description: str | None = None
    rule_type: str | None = None
    subsystem: str | None = None
    canonical_key: str | None = None
    conditions: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    priority: int | None = None
    confidence: float | None = None
    source_section: str | None = None


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
    # Full rule details — populated by the API layer by joining
    # incoming_rule_id against the rules table and live_rule_id against
    # the live snapshot. Lets the workbench show the entire rule
    # (name, all conditions, all actions with target+value) instead of
    # just the canonical 4-field projection in `diff`.
    incoming_rule: MergeRulePayload | None = None
    live_rule: MergeRulePayload | None = None


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
