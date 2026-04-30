from pydantic import BaseModel


class BrdUploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    created_at: str
    rule_set_id: str | None = None


class BrdListResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    created_at: str
    rule_set_count: int = 0
    # Slice D enrichments — let the BRD list show downstream progression
    # without forcing a click into each row.
    total_rules: int = 0
    has_merge_proposal: bool = False
    is_merged_into_repo: bool = False
    has_test_suite: bool = False
    has_executed_test_suite: bool = False

    model_config = {"from_attributes": True}
