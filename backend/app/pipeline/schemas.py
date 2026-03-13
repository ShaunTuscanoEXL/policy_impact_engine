from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class SectionType(str, Enum):
    HEADER = "HEADER"
    EXECUTIVE_SUMMARY = "EXECUTIVE_SUMMARY"
    BACKGROUND = "BACKGROUND"
    CURRENT_STATE = "CURRENT_STATE"
    RULES = "RULES"
    IMPACT = "IMPACT"
    TIMELINE = "TIMELINE"
    APPROVAL = "APPROVAL"
    OTHER = "OTHER"


class DocumentSection(BaseModel):
    section_id: str
    title: str
    content: str
    section_type: SectionType
    page_number: int | None = None


class RuleConflict(BaseModel):
    rule_id_1: str
    rule_id_2: str
    conflict_type: str
    description: str
    affected_fields: list[str] = []


class ValidationResult(BaseModel):
    is_valid: bool
    warnings: list[str] = []
    potential_conflicts: list[RuleConflict] = []
