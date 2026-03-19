import csv
import io
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import loan_record_service
from app.schemas.loan_record import (
    LoanRecordResponse,
    LoanRecordListItem,
    LoanRecordStatsResponse,
    LoanRecordUploadResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/loan-records", tags=["Loan Records"])


@router.get("/stats", response_model=LoanRecordStatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregate statistics about the loan records database."""
    stats = await loan_record_service.get_stats(db)
    return LoanRecordStatsResponse(**stats)


@router.get("", response_model=list[LoanRecordListItem])
async def list_loan_records(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, description="Search by loan_application_id"),
    db: AsyncSession = Depends(get_db),
):
    """List loan records with pagination and optional search."""
    records = await loan_record_service.list_loan_records(db, limit=limit, offset=offset, search=search)
    items = []
    for r in records:
        # Extract key fields from JSONB for the list view
        req = r.request_payload or {}
        resp = r.response_payload or {}
        bcm = req.get("borrower_credit_model", {})
        items.append(LoanRecordListItem(
            id=str(r.id),
            loan_application_id=r.loan_application_id,
            decision_status=resp.get("decision_status"),
            bureau_score=bcm.get("bureau_credits", {}).get("bureau_score"),
            monthly_income=bcm.get("customer_inputs", {}).get("monthly_income"),
            desired_amount=req.get("desired_amount"),
            created_at=r.created_at.isoformat(),
        ))
    return items


@router.get("/{record_id}", response_model=LoanRecordResponse)
async def get_loan_record(record_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single loan record with full request/response payloads."""
    record = await loan_record_service.get_loan_record(record_id, db)
    if not record:
        raise HTTPException(404, "Loan record not found")
    return LoanRecordResponse(
        id=str(record.id),
        loan_application_id=record.loan_application_id,
        request_payload=record.request_payload,
        response_payload=record.response_payload,
        created_at=record.created_at.isoformat(),
    )


@router.post("/upload", response_model=LoanRecordUploadResponse)
async def upload_loan_records(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Bulk import loan records from a CSV or JSON file.

    CSV format: loan_application_id, request_payload (JSON string), response_payload (JSON string)
    JSON format: array of {loan_application_id, request_payload, response_payload}
    """
    content = await file.read()
    text = content.decode("utf-8")
    records = []

    if file.filename and file.filename.endswith(".json"):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                records = data
            else:
                raise HTTPException(400, "JSON file must contain an array of records")
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON file")
    else:
        # CSV
        try:
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                records.append({
                    "loan_application_id": row["loan_application_id"],
                    "request_payload": json.loads(row["request_payload"]),
                    "response_payload": json.loads(row["response_payload"]),
                })
        except (KeyError, json.JSONDecodeError) as e:
            raise HTTPException(400, f"Invalid CSV format: {e}")

    result = await loan_record_service.bulk_import(records, db)
    return LoanRecordUploadResponse(**result)


@router.post("/seed")
async def seed_loan_records(db: AsyncSession = Depends(get_db)):
    """Trigger re-seeding of the loan records database with synthetic data."""
    from scripts.seed_loan_records import generate_records
    from app.models.loan_record import LoanRecord as LR
    from sqlalchemy import select, func

    count = await db.execute(select(func.count(LR.id)))
    existing = count.scalar() or 0

    if existing > 0:
        return {"status": "already_seeded", "count": existing}

    records = generate_records(2000)
    for rec in records:
        db.add(LR(**rec))
    await db.commit()
    return {"status": "seeded", "count": len(records)}
