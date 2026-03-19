from pydantic import BaseModel


class LoanRecordResponse(BaseModel):
    id: str
    loan_application_id: str
    request_payload: dict
    response_payload: dict
    created_at: str

    model_config = {"from_attributes": True}


class LoanRecordListItem(BaseModel):
    id: str
    loan_application_id: str
    decision_status: str | None = None
    bureau_score: int | None = None
    monthly_income: float | None = None
    desired_amount: float | None = None
    created_at: str

    model_config = {"from_attributes": True}


class LoanRecordStatsResponse(BaseModel):
    total_records: int
    decision_distribution: dict
    bureau_score_range: dict
    income_range: dict


class LoanRecordUploadResponse(BaseModel):
    imported: int
    skipped: int
    errors: int
