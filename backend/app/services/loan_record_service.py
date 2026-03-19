from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.models.loan_record import LoanRecord


async def list_loan_records(db: AsyncSession, limit: int = 50, offset: int = 0, search: str | None = None):
    """List loan records with optional search by loan_application_id."""
    q = select(LoanRecord).order_by(LoanRecord.created_at.desc())
    if search:
        q = q.where(LoanRecord.loan_application_id.ilike(f"%{search}%"))
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


async def get_loan_record(record_id: str, db: AsyncSession):
    """Get a single loan record by ID."""
    result = await db.execute(select(LoanRecord).where(LoanRecord.id == record_id))
    return result.scalar_one_or_none()


async def get_stats(db: AsyncSession):
    """Get aggregate statistics about the loan records."""
    total = await db.execute(select(func.count(LoanRecord.id)))
    total_count = total.scalar() or 0

    if total_count == 0:
        return {
            "total_records": 0,
            "decision_distribution": {},
            "bureau_score_range": {"min": 0, "max": 0, "avg": 0},
            "income_range": {"min": 0, "max": 0, "avg": 0},
        }

    # Decision distribution from response_payload
    decision_q = await db.execute(text("""
        SELECT response_payload->>'decision_status' as decision, COUNT(*) as cnt
        FROM loan_records
        GROUP BY response_payload->>'decision_status'
    """))
    decision_dist = {row[0]: row[1] for row in decision_q.fetchall()}

    # Bureau score stats
    bureau_q = await db.execute(text("""
        SELECT
            MIN((request_payload->'borrower_credit_model'->'bureau_credits'->>'bureau_score')::numeric) as min_score,
            MAX((request_payload->'borrower_credit_model'->'bureau_credits'->>'bureau_score')::numeric) as max_score,
            AVG((request_payload->'borrower_credit_model'->'bureau_credits'->>'bureau_score')::numeric) as avg_score
        FROM loan_records
    """))
    bureau_row = bureau_q.fetchone()

    # Income stats
    income_q = await db.execute(text("""
        SELECT
            MIN((request_payload->'borrower_credit_model'->'customer_inputs'->>'monthly_income')::numeric) as min_income,
            MAX((request_payload->'borrower_credit_model'->'customer_inputs'->>'monthly_income')::numeric) as max_income,
            AVG((request_payload->'borrower_credit_model'->'customer_inputs'->>'monthly_income')::numeric) as avg_income
        FROM loan_records
    """))
    income_row = income_q.fetchone()

    return {
        "total_records": total_count,
        "decision_distribution": decision_dist,
        "bureau_score_range": {
            "min": float(bureau_row[0] or 0),
            "max": float(bureau_row[1] or 0),
            "avg": round(float(bureau_row[2] or 0), 1),
        },
        "income_range": {
            "min": float(income_row[0] or 0),
            "max": float(income_row[1] or 0),
            "avg": round(float(income_row[2] or 0), 1),
        },
    }


async def bulk_import(records: list[dict], db: AsyncSession) -> dict:
    """Import loan records from a list of dicts."""
    imported = 0
    skipped = 0
    errors = 0
    for rec in records:
        try:
            existing = await db.execute(
                select(LoanRecord).where(LoanRecord.loan_application_id == rec["loan_application_id"])
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue
            loan = LoanRecord(
                loan_application_id=rec["loan_application_id"],
                request_payload=rec["request_payload"],
                response_payload=rec["response_payload"],
            )
            db.add(loan)
            imported += 1
        except Exception:
            errors += 1
    await db.commit()
    return {"imported": imported, "skipped": skipped, "errors": errors}


async def query_by_filters(filters: list[dict], db: AsyncSession, limit: int = 10):
    """Query loan records using JSONB filters from test case conditions.

    Each filter: {"path": "borrower_credit_model.bureau_credits.bureau_score", "operator": ">=", "value": 700}
    """
    conditions = []
    for f in filters:
        path_parts = f["path"].split(".")
        op = f["operator"]
        val = f["value"]

        # Build JSONB accessor
        if len(path_parts) == 1:
            accessor = f"request_payload->>'{path_parts[0]}'"
        else:
            arrows = "->".join(f"'{p}'" for p in path_parts[:-1])
            accessor = f"request_payload->{arrows}->>'{path_parts[-1]}'"

        # Handle numeric vs string comparisons
        if isinstance(val, (int, float)):
            accessor_cast = f"({accessor})::numeric"
            conditions.append(f"{accessor_cast} {op} {val}")
        elif isinstance(val, str):
            conditions.append(f"{accessor} {op} '{val}'")
        elif isinstance(val, list):
            # For "in" operator
            vals = ", ".join(f"'{v}'" for v in val)
            conditions.append(f"{accessor} IN ({vals})")

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    query = text(f"""
        SELECT id, loan_application_id, request_payload, response_payload
        FROM loan_records
        WHERE {where_clause}
        LIMIT :limit
    """)

    result = await db.execute(query, {"limit": limit})
    return [dict(row._mapping) for row in result.fetchall()]
