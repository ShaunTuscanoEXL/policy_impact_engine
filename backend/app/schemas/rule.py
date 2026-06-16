from pydantic import BaseModel, Field
from typing import Any
from enum import Enum


class RuleTypeEnum(str, Enum):
    ELIGIBILITY = "ELIGIBILITY"
    PRICING = "PRICING"
    CAP = "CAP"
    THRESHOLD = "THRESHOLD"
    SCORING = "SCORING"


class Condition(BaseModel):
    field: str = Field(description="Data field name, e.g. 'bureau_score'")
    operator: str = Field(description="Comparison operator: >=, <=, ==, !=, in, not_in, between")
    value: Any = Field(description="Threshold value or list of values")
    logic: str = Field(default="AND", description="AND | OR for chaining with next condition")
    # Slice 15 — provenance. "explicit" = the rule's own condition from
    # its BRD line. "scope" = an eligibility/scope gate auto-injected
    # from BRD document context (e.g. "this framework applies to Repeat
    # Good Customers"). Scope conditions are rendered with a badge and
    # are reviewer-removable. Ignored by canonical_key/semantic_signature
    # (it's metadata, not identity).
    origin: str = Field(default="explicit", description="explicit | scope")


class Action(BaseModel):
    action_type: str = Field(description="SET | REJECT | ADJUST | FLAG")
    target_field: str = Field(description="Field to modify, e.g. 'decision_status'")
    value: Any = Field(description="New value or delta")
    description: str = Field(description="Human-readable action description")


class RuleDefinition(BaseModel):
    rule_id: str
    rule_name: str
    description: str
    rule_type: RuleTypeEnum
    conditions: list[Condition]
    actions: list[Action]
    priority: int = 0
    source_section: str = ""
    confidence: float = 1.0
    has_conflicts: bool = False
    conflict_details: dict | None = None
    # Slice 15 — scope/eligibility gates the BRD's document context says
    # apply to this rule (NOT from the rule's own line). The LLM emits
    # these when it sees, e.g., "this whole framework applies to Repeat
    # Good Customers". A post-pass merges them into `conditions` with
    # origin="scope" so they're flagged + reversible.
    applies_when: list[Condition] = []
    # Globally unique identifier (DB row UUID for rule-set rules, or
    # snapshot's `id` field for live-version rules). Used downstream by
    # the test case generator + executor to disambiguate when the
    # human-readable rule_id collides across BRDs.
    uuid: str | None = None


class RuleResponse(BaseModel):
    id: str
    rule_id: str
    rule_name: str
    description: str | None
    rule_type: str
    subsystem: str | None = None
    canonical_key: str | None = None
    conditions: list[dict]
    actions: list[dict]
    priority: int
    confidence: float
    compiled_expression: str | None
    has_conflicts: bool
    conflict_details: dict | None
    # Slice 7: optional governance metadata.
    policy_intent: str | None = None
    regulatory_citation: str | None = None

    model_config = {"from_attributes": True}


class RuleSetResponse(BaseModel):
    id: str
    brd_document_id: str
    version: int
    name: str
    description: str | None
    status: str
    rules: list[RuleResponse] = []
    created_at: str
    # Slice 1: decision attribution.
    approved_by: str | None = None
    approved_at: str | None = None
    approval_notes: str | None = None

    model_config = {"from_attributes": True}


class ApproveRuleSetRequest(BaseModel):
    """Body for `PATCH /rule-sets/{id}/approve`. All fields optional —
    the approve action still works with an empty body for back-compat."""
    approved_by: str | None = None
    approval_notes: str | None = None


class RuleUpdateRequest(BaseModel):
    rule_name: str | None = None
    description: str | None = None
    rule_type: RuleTypeEnum | None = None
    conditions: list[Condition] | None = None
    actions: list[Action] | None = None
    priority: int | None = None
    # Slice 7: governance metadata — policy team can fill these in
    # after extraction.
    policy_intent: str | None = None
    regulatory_citation: str | None = None


# ── Slice 14: BRD coherence report ─────────────────────────────────────

class CoherenceIssueResponse(BaseModel):
    kind: str               # dead_consumer | orphan_producer | unreferenced_eligibility | dependency_cycle
    severity: str           # error | warning | info
    rule_ids: list[str]
    field: str | None = None
    message: str


class CoherenceReportResponse(BaseModel):
    is_coherent: bool
    issue_count: int
    error_count: int
    warning_count: int
    issues: list[CoherenceIssueResponse] = []
    produced_fields: list[str] = []
    consumed_fields: list[str] = []
    # (producer_rule_id, consumer_rule_id, field) tuples for graph rendering
    dependency_edges: list[list[str]] = []
