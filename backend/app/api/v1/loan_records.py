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


# Pre-defined binning strategies — match how lending teams actually
# segment borrowers, instead of equi-width bins that don't align with
# any meaningful threshold.
_FICO_BAND_EDGES: list[tuple[float, float, str]] = [
    (300, 579, "Subprime\n(<580)"),
    (580, 669, "Near-prime\n(580–669)"),
    (670, 739, "Prime\n(670–739)"),
    (740, 799, "Super-prime\n(740–799)"),
    (800, 850, "Exceptional\n(800+)"),
]
_INCOME_BRACKET_EDGES: list[tuple[float, float, str]] = [
    (0, 3000, "<$3k"),
    (3000, 5000, "$3k–5k"),
    (5000, 7500, "$5k–7.5k"),
    (7500, 10000, "$7.5k–10k"),
    (10000, 15000, "$10k–15k"),
    (15000, 25000, "$15k–25k"),
    (25000, 1_000_000, "$25k+"),
]
_DTI_BAND_EDGES: list[tuple[float, float, str]] = [
    (0, 0.20, "0–20%"),
    (0.20, 0.36, "20–36%\n(comfortable)"),
    (0.36, 0.43, "36–43%\n(QM cap)"),
    (0.43, 0.50, "43–50%"),
    (0.50, 1.0, "50%+\n(stretched)"),
]


@router.get("/histogram")
async def get_histogram(
    field: str = Query("bureau_score", description="Field to bucket: bureau_score | monthly_income | dti_ratio"),
    bins: int = Query(20, ge=4, le=60),
    mode: str = Query(
        "auto",
        description=(
            "Binning strategy: 'auto' picks the recommended bands per field "
            "(FICO bands for bureau_score, lending income brackets for "
            "monthly_income, QM-anchored bands for dti_ratio). 'equi_width' "
            "forces equal-width bins of size derived from `bins`."
        ),
    ),
    sample: int = Query(
        15000,
        ge=500,
        le=200000,
        description=(
            "Cap on the number of records to scan for the histogram. With "
            "100k+ rows the full scan can take 10s+ — sampling 15k preserves "
            "the distribution shape and keeps the response under 2s."
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    """Return a histogram of one numeric field across the loan corpus.

    Used by the loan-records page to render distribution charts. The
    bucketing is done in Python because the field lives in JSONB. We
    cap the scan at ``sample`` rows so the page loads quickly even on
    100k+ corpora.

    Default ``mode=auto`` uses meaningful lending-domain bands (FICO
    segments, income brackets, QM-anchored DTI bands) so the chart
    aligns with how lenders think rather than producing equi-width
    bins that don't map to any threshold.
    """
    from sqlalchemy import select
    from app.models.loan_record import LoanRecord
    rows_q = await db.execute(select(LoanRecord.request_payload).limit(sample))
    values: list[float] = []
    for (payload,) in rows_q.all():
        if not payload:
            continue
        bcm = payload.get("borrower_credit_model", {}) or {}
        if field == "bureau_score":
            v = (bcm.get("bureau_credits", {}) or {}).get("bureau_score")
        elif field == "monthly_income":
            v = (bcm.get("customer_inputs", {}) or {}).get("monthly_income")
        elif field == "dti_ratio":
            v = (payload.get("calculated_attributes", {}) or {}).get("debt_to_income_ratio")
        else:
            v = None
        if isinstance(v, (int, float)):
            values.append(float(v))
    if not values:
        return {"field": field, "bins": [], "min": None, "max": None, "count": 0, "mode": mode}

    lo, hi = min(values), max(values)

    # Pick the band table for "auto" mode based on the field
    band_table: list[tuple[float, float, str]] | None = None
    effective_mode = mode
    if mode == "auto":
        if field == "bureau_score":
            band_table = _FICO_BAND_EDGES
            effective_mode = "fico_bands"
        elif field == "monthly_income":
            band_table = _INCOME_BRACKET_EDGES
            effective_mode = "income_brackets"
        elif field == "dti_ratio":
            band_table = _DTI_BAND_EDGES
            effective_mode = "dti_bands"
        else:
            effective_mode = "equi_width"

    if band_table:
        # Variable-width bands using domain-specific edges
        bins_payload = []
        for x0, x1, label in band_table:
            count = sum(1 for v in values if x0 <= v < x1)
            # The very last band is inclusive on the upper side
            if (x0, x1) == (band_table[-1][0], band_table[-1][1]):
                count = sum(1 for v in values if x0 <= v <= x1)
            bins_payload.append({"x0": x0, "x1": x1, "count": count, "label": label})
        return {
            "field": field,
            "bins": bins_payload,
            "min": lo,
            "max": hi,
            "count": len(values),
            "mode": effective_mode,
        }

    # Fallback: equi-width
    if lo == hi:
        return {
            "field": field,
            "bins": [{"x0": lo, "x1": hi, "count": len(values)}],
            "min": lo,
            "max": hi,
            "count": len(values),
            "mode": "equi_width",
        }
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - lo) / width))
        counts[idx] += 1
    bins_payload = [
        {"x0": lo + i * width, "x1": lo + (i + 1) * width, "count": counts[i]}
        for i in range(bins)
    ]
    return {
        "field": field,
        "bins": bins_payload,
        "min": lo,
        "max": hi,
        "count": len(values),
        "mode": "equi_width",
    }


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
