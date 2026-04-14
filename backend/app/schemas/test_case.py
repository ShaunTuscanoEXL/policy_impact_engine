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

    model_config = {"from_attributes": True}


class TestCaseSuiteListResponse(BaseModel):
    id: str
    rule_set_id: str
    rule_set_name: str | None = None
    brd_id: str | None = None
    brd_filename: str | None = None
    total_cases: int
    cases_by_category: dict
    created_at: str

    model_config = {"from_attributes": True}
