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
    page_number: int | None = None
