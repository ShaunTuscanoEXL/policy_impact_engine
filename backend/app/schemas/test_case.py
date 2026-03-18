from pydantic import BaseModel
from enum import Enum


class TestCaseCategoryEnum(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    BOUNDARY = "BOUNDARY"
    EDGE = "EDGE"
    INTERACTION = "INTERACTION"


class TestCaseResponse(BaseModel):
    id: str
    test_case_id: str
    description: str
    source_rule_ids: list[str]
    category: str
    inputs: dict
    expected_outcome: dict

    model_config = {"from_attributes": True}


class TestCaseSuiteResponse(BaseModel):
    id: str
    rule_set_id: str
    total_cases: int
    cases_by_category: dict
    test_cases: list[TestCaseResponse] = []
    created_at: str

    model_config = {"from_attributes": True}


class TestCaseGenerateRequest(BaseModel):
    rule_set_id: str
    baseline_config: dict | None = None


class TestCaseSuiteListResponse(BaseModel):
    id: str
    rule_set_id: str
    total_cases: int
    cases_by_category: dict
    created_at: str

    model_config = {"from_attributes": True}
