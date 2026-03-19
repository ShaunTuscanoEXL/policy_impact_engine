"""Pipeline schemas for document parsing."""
from dataclasses import dataclass
from enum import Enum


class SectionType(str, Enum):
    EXECUTIVE_SUMMARY = "executive_summary"
    BACKGROUND = "background"
    CURRENT_STATE = "current_state"
    RULES = "rules"
    IMPACT = "impact"
    TIMELINE = "timeline"
    APPROVAL = "approval"
    OTHER = "other"


@dataclass
class DocumentSection:
    title: str
    content: str
    section_type: SectionType
    section_id: str = ""
    page_number: int | None = None


@dataclass
class RuleConflict:
    rule_id_1: str
    rule_id_2: str
    conflict_type: str
    description: str
    affected_fields: list[str]


@dataclass
class ValidationResult:
    is_valid: bool
    potential_conflicts: list[RuleConflict]
    warnings: list[str]
