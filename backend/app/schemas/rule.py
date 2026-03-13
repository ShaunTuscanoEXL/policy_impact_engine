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


class RuleResponse(BaseModel):
    id: str
    rule_id: str
    rule_name: str
    description: str | None
    rule_type: str
    conditions: list[dict]
    actions: list[dict]
    priority: int
    confidence: float
    compiled_expression: str | None
    has_conflicts: bool
    conflict_details: dict | None

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

    model_config = {"from_attributes": True}


class RuleUpdateRequest(BaseModel):
    rule_name: str | None = None
    description: str | None = None
    rule_type: RuleTypeEnum | None = None
    conditions: list[Condition] | None = None
    actions: list[Action] | None = None
    priority: int | None = None
