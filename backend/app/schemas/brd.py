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

    model_config = {"from_attributes": True}
