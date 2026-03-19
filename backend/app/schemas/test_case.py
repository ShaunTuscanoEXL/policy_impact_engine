from pydantic import BaseModel
from enum import Enum


class TestCaseCategoryEnum(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    BOUNDARY = "BOUNDARY"
    EDGE = "EDGE"
    INTERACTION = "INTERACTION"


class TestCaseGenerateRequest(BaseModel):
    rule_set_id: str
    positive_count: int = 3
    negative_count: int = 3
    boundary_count: int = 5
    edge_count: int = 3
    interaction_count: int = 2
    max_matches: int = 10


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
    filter_logic: list[dict]
    filter_description: str | None = None
    expected_outcome: dict
    matched_loan_ids: list[str] = []
    match_count: int = 0
    matched_customers: list[MatchedCustomer] = []

    model_config = {"from_attributes": True}


class TestCaseSuiteResponse(BaseModel):
    id: str
    rule_set_id: str
    rule_set_name: str | None = None
    total_cases: int
    cases_by_category: dict
    test_cases: list[TestCaseResponse] = []
    created_at: str

    model_config = {"from_attributes": True}


class TestCaseSuiteListResponse(BaseModel):
    id: str
    rule_set_id: str
    rule_set_name: str | None = None
    total_cases: int
    cases_by_category: dict
    created_at: str

    model_config = {"from_attributes": True}
