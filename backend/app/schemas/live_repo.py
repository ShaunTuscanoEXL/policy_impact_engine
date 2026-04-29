from pydantic import BaseModel, Field
from typing import Any


class CreateRepositoryRequest(BaseModel):
    name: str
    product: str = Field(description="e.g. 'PERSONAL'")
    jurisdiction: str = Field(description="e.g. 'US'")
    description: str | None = None


class RepositorySummary(BaseModel):
    id: str
    name: str
    product: str
    jurisdiction: str
    description: str | None
    current_version: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class VersionSummary(BaseModel):
    id: str
    version_number: int
    parent_version_id: str | None
    source_brd_id: str | None
    merge_proposal_id: str | None
    summary: str | None
    rule_count: int
    created_at: str
    created_by: str | None

    model_config = {"from_attributes": True}


class VersionDetail(VersionSummary):
    rule_snapshot: list[dict[str, Any]]


class RepositoryDetail(RepositorySummary):
    versions: list[VersionSummary] = []
