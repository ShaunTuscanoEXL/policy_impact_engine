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
    # The version currently flagged as production-live. May be null on a
    # brand-new repo before its first version is promoted, and may be a
    # version_number BELOW current_version when a newer candidate exists
    # but hasn't been promoted yet.
    production_version_id: str | None = None
    production_version_number: int | None = None
    production_promoted_at: str | None = None
    production_promoted_by: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class PromoteVersionRequest(BaseModel):
    version_number: int = Field(description="Version number to mark as production-live.")
    promoted_by: str | None = Field(
        default=None,
        description="Operator name; falls back to 'system' if omitted.",
    )


class PromoteVersionResponse(BaseModel):
    repository_id: str
    production_version_id: str
    production_version_number: int
    promoted_by: str
    promoted_at: str


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


# ── Slice 1 ──────────────────────────────────────────────────────────────

class ProposeFromBrdRequest(BaseModel):
    brd_id: str
    repository_id: str | None = Field(
        default=None,
        description="If omitted, the default repo for (product, jurisdiction) is used or created.",
    )
    product: str = "PERSONAL"
    jurisdiction: str = "US"
    auto_apply_when_empty: bool = Field(
        default=True,
        description="If the live repo is empty, apply the proposal immediately as v1 (baseline).",
    )
    decided_by: str | None = Field(
        default=None,
        description="Required when auto_apply_when_empty fires; falls back to 'auto-baseline'.",
    )


class ProposeFromBrdResponse(BaseModel):
    proposal_id: str
    repository_id: str
    auto_applied: bool
    new_version_number: int | None = None
    summary: str | None = None


class BackfillResponse(BaseModel):
    rules_classified: int


# ── Slice 3: Python import ──────────────────────────────────────────────

class ImportPythonRequest(BaseModel):
    source: str = Field(description="Full Python source matching the codegen format.")
    summary: str | None = Field(
        default=None, description="Override the auto-generated version summary."
    )
    decided_by: str | None = None


class ImportPythonResponse(BaseModel):
    new_version_number: int
    new_version_id: str
    rules_imported: int
    warnings: list[str] = []
    summary: str
