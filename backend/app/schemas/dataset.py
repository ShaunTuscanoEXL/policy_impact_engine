from pydantic import BaseModel


class DatasetUploadResponse(BaseModel):
    id: str
    name: str
    file_type: str
    row_count: int
    column_schema: dict | None
    sample_data: list | dict | None
    column_mapping: dict | None = None
    created_at: str


class DatasetListResponse(BaseModel):
    id: str
    name: str
    description: str | None
    file_type: str
    row_count: int
    created_at: str
    column_mapping: dict | None = None

    model_config = {"from_attributes": True}


class DatasetProfileResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    file_type: str | None = None
    row_count: int
    column_schema: dict | None
    data_profile: dict | None
    sample_data: list | dict | None
    column_mapping: dict | None = None
    baseline_config: dict | None = None
    created_at: str | None = None


class DatasetMappingRequest(BaseModel):
    column_mapping: dict
    baseline_config: dict | None = None
