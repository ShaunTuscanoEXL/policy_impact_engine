from pydantic import BaseModel
from enum import Enum
from typing import Any


class TestCaseCategoryEnum(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    BOUNDARY = "BOUNDARY"
    EDGE = "EDGE"
    INTERACTION = "INTERACTION"


class TestCaseGenerateRequest(BaseModel):
    rule_set_id: str
    positive_count: int | None = None   # None = auto-suggest
    negative_count: int | None = None
    boundary_count: int | None = None
    edge_count: int | None = None
    interaction_count: int | None = None
    max_matches: int = 10


class SuggestCountsRequest(BaseModel):
    rule_set_id: str


class SuggestedCountsResponse(BaseModel):
    positive: int
    negative: int
    boundary: int
    edge: int
    interaction: int
    total: int
    rationale: dict


class MatchedCustomer(BaseModel):
    id: str
    loan_application_id: str
    request_payload: dict
    response_payload: dict
    match_reason: str


class TestCaseResponse(BaseModel):
    id: str
    test_case_id: str
    description: str | None
    source_rule_ids: list[str]
    # Globally unique IDs for the source rule(s) — populated when the
    # test was generated (or backfilled) by the UUID-aware pipeline.
    source_rule_uuids: list[str] | None = None
    category: str
    input_values: dict = {}
    filter_logic: list[dict]
    filter_description: str | None = None
    expected_outcome: dict
    rationale: str | None = None
    matched_loan_ids: list[str] = []
    match_count: int = 0
    matched_customers: list[MatchedCustomer] = []

    model_config = {"from_attributes": True}


class CoverageStats(BaseModel):
    total_rules: int = 0
    rules_with_test_cases: int = 0
    rule_coverage_pct: float = 0.0
    total_conditions: int = 0
    conditions_tested_negative: int = 0
    unresolved_fields: list[str] = []


class TestCaseSuiteResponse(BaseModel):
    id: str
    rule_set_id: str
    rule_set_name: str | None = None
    total_cases: int
    cases_by_category: dict
    coverage_stats: dict = {}
    suggested_counts: dict = {}
    test_cases: list[TestCaseResponse] = []
    created_at: str
    last_execution_report: dict[str, Any] | None = None
    last_executed_at: str | None = None
    last_executed_against_version_id: str | None = None
    # True if the source rule_set has been modified after this suite was
    # generated — the test cases (and any prior execution report) may
    # not reflect the current rule contents. UI surfaces a "STALE" badge.
    is_stale: bool = False
    rule_set_last_modified_at: str | None = None
    # Slice 1: who ran the latest execution and (optionally) why.
    last_executed_by: str | None = None
    last_execution_rationale: str | None = None

    model_config = {"from_attributes": True}


class SuiteLastExecutionInline(BaseModel):
    """Compact summary of the suite's most recent execution — surfaced
    inline on the suite list so the table can show "X passing / Y failing"
    without a per-row drill-in."""
    executed_at: str
    version_number: int | None = None
    total_assertions: int
    passing: int
    failing: int
    pass_rate: float


class TestCaseSuiteListResponse(BaseModel):
    id: str
    rule_set_id: str
    rule_set_name: str | None = None
    brd_id: str | None = None
    brd_filename: str | None = None
    total_cases: int
    cases_by_category: dict
    created_at: str
    # Inline-decorated last execution result (Slice D enrichment)
    last_execution: SuiteLastExecutionInline | None = None
    # Stale = source rule_set was edited after suite generation.
    is_stale: bool = False

    model_config = {"from_attributes": True}


# ── Slice 4 (wire-ups) — generate from a LiveRuleVersion ────────────────

class GenerateFromVersionRequest(BaseModel):
    version_id: str
    positive_count: int | None = None
    negative_count: int | None = None
    boundary_count: int | None = None
    edge_count: int | None = None
    interaction_count: int | None = None
    max_matches: int = 10


# ── Slice 4 — execute a suite vs a live version, return a report ────────

class ExecuteSuiteRequest(BaseModel):
    version_id: str
    executed_by: str | None = None
    rationale: str | None = None


class TestCaseExecutionReport(BaseModel):
    test_case_id: str
    category: str
    expected_decision: str
    # The token actually compared against per-loan. For NEG / BND-at-threshold
    # it's NOT_TRIGGERED; for POSITIVE / BND-above-threshold / EDGE-fires
    # it's RULE_FIRED; for INTERACTION it's ALL_TRIGGERED; otherwise the
    # engine decision verbatim.
    target_outcome: str | None = None
    matched_loan_count: int
    # Distribution in the assertion vocabulary
    # (RULE_FIRED / NOT_TRIGGERED / engine decision token).
    actual_distribution: dict[str, int]
    # Distribution of the engine's actual final decision per loan — useful
    # when the assertion vocabulary hides what really happened (e.g. POSITIVE
    # passes because the source rule fired, but the engine still REJECTED
    # because another terminal rule overrode it).
    engine_decision_distribution: dict[str, int] | None = None
    matches_expected: int
    deviates_from_expected: int
    first_deviation_reason: str | None


class SuiteExecutionResponse(BaseModel):
    suite_id: str
    version_id: str
    version_number: int
    total_cases: int
    cases_evaluated: int
    results: list[TestCaseExecutionReport]
    summary: dict[str, Any]
