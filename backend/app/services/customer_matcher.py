"""Matches loan records from the database against test case filter conditions."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.loan_record import LoanRecord
from app.services.field_registry import json_path_to_sql

logger = logging.getLogger(__name__)


def _is_postgres(db: AsyncSession) -> bool:
    """Detect if the bound engine is Postgres. JSONB syntax (`->`,
    `::numeric`) is Postgres-only; on other backends we fall back to a
    Python-side filter so the same code path still works for tests and
    SQLite-based dev sandboxes."""
    try:
        return db.bind.dialect.name == "postgresql"
    except (AttributeError, TypeError):
        # If db.bind isn't directly accessible (e.g. session-bound),
        # consult the engine attached to the session's transaction
        try:
            return db.get_bind().dialect.name == "postgresql"
        except Exception:
            return False


def _eval_filter_in_python(payload: dict, filter_logic: list[dict]) -> bool:
    """In-process implementation of the same filter semantics the
    Postgres SQL builds. Used as a fallback on non-Postgres backends.

    Each filter dict shape:
        {field_name, json_path, operator, value}
    """
    for f in filter_logic:
        actual = _extract_value(payload, f.get("json_path", ""))
        op = (f.get("operator") or "").strip().lower()
        target = f.get("value")

        if op == "between":
            if not isinstance(target, (list, tuple)) or len(target) != 2:
                return False
            try:
                a = float(actual)
                lo, hi = float(target[0]), float(target[1])
            except (TypeError, ValueError):
                return False
            if not (lo <= a <= hi):
                return False
            continue

        if op in ("in", "not_in"):
            if not isinstance(target, (list, tuple)):
                return False
            if op == "in" and actual not in target:
                return False
            if op == "not_in" and actual in target:
                return False
            continue

        if op in ("==", "="):
            if isinstance(target, (int, float)) and actual is not None:
                try:
                    if float(actual) != float(target):
                        return False
                    continue
                except (TypeError, ValueError):
                    pass
            if str(actual) != str(target):
                return False
            continue
        if op == "!=":
            if str(actual) == str(target):
                return False
            continue

        if op in (">", ">=", "<", "<="):
            try:
                a = float(actual)
                b = float(target)
            except (TypeError, ValueError):
                return False
            if op == ">"  and not (a >  b): return False
            if op == ">=" and not (a >= b): return False
            if op == "<"  and not (a <  b): return False
            if op == "<=" and not (a <= b): return False
            continue

        # Unknown operator → conservative: filter out
        return False
    return True


async def _match_python_fallback(
    filter_logic: list[dict],
    db: AsyncSession,
    limit: int,
) -> list[dict]:
    """SQLite/dev fallback that loads all loans and filters in Python.

    Slow at production scale (loads the corpus into memory) but
    correct, dialect-free, and exactly what the test suite executor
    needs to drive end-to-end tests against real loan_records without
    a Postgres dependency.
    """
    if not filter_logic:
        return []
    result = await db.execute(select(LoanRecord))
    matched: list[dict] = []
    for loan in result.scalars():
        payload = loan.request_payload or {}
        if not _eval_filter_in_python(payload, filter_logic):
            continue
        reasons = []
        for f in filter_logic:
            actual_val = _extract_value(payload, f.get("json_path", ""))
            reasons.append(
                f"{f.get('field_name')}={actual_val} ({f.get('operator')} {f.get('value')})"
            )
        matched.append({
            "id": str(loan.id),
            "loan_application_id": loan.loan_application_id,
            "request_payload": payload,
            "response_payload": loan.response_payload or {},
            "match_reason": ", ".join(reasons),
        })
        if len(matched) >= limit:
            break
    return matched


async def match_customers(
    filter_logic: list[dict],
    db: AsyncSession,
    limit: int = 10,
) -> list[dict]:
    """Query loan_records for customers matching the filter conditions.

    Each filter: {"field_name": "bureau_score", "json_path": "borrower_credit_model.bureau_credits.bureau_score",
                  "operator": ">=", "value": 700}

    Uses parameterized queries to prevent SQL injection.
    Returns list of matched records with match_reason.

    On non-Postgres backends (SQLite test env, dev sandboxes) we
    transparently fall back to a Python-side filter so callers don't
    need to know which backend is running.
    """
    if not filter_logic:
        return []

    if not _is_postgres(db):
        return await _match_python_fallback(filter_logic, db, limit)

    where_parts = []
    params: dict = {"limit": limit}
    param_idx = 0

    for f in filter_logic:
        path = f.get("json_path", "")
        op = f.get("operator", "=")
        val = f.get("value")

        sql_accessor = json_path_to_sql(path)

        # Handle between operator
        if op == "between":
            if isinstance(val, (list, tuple)) and len(val) == 2:
                p_lo = f"p{param_idx}"
                p_hi = f"p{param_idx + 1}"
                params[p_lo] = float(val[0])
                params[p_hi] = float(val[1])
                where_parts.append(f"({sql_accessor})::numeric BETWEEN :{p_lo} AND :{p_hi}")
                param_idx += 2
            continue

        # Handle in / not_in operators
        if op in ("in", "not_in"):
            if isinstance(val, (list, tuple)) and val:
                sql_kw = "NOT IN" if op == "not_in" else "IN"
                placeholders = []
                for v in val:
                    p_name = f"p{param_idx}"
                    params[p_name] = v
                    placeholders.append(f":{p_name}")
                    param_idx += 1
                joined = ", ".join(placeholders)
                if all(isinstance(v, (int, float)) for v in val):
                    where_parts.append(f"({sql_accessor})::numeric {sql_kw} ({joined})")
                else:
                    where_parts.append(f"{sql_accessor} {sql_kw} ({joined})")
            continue

        # Skip unsupported operators
        if op not in (">=", "<=", ">", "<", "==", "!="):
            continue

        # Normalize == to =
        sql_op = "=" if op == "==" else ("<>" if op == "!=" else op)

        p_name = f"p{param_idx}"
        params[p_name] = val
        param_idx += 1

        if isinstance(val, (int, float)):
            where_parts.append(f"({sql_accessor})::numeric {sql_op} :{p_name}")
        elif isinstance(val, str):
            where_parts.append(f"{sql_accessor} {sql_op} :{p_name}")
        elif isinstance(val, bool):
            where_parts.append(f"({sql_accessor})::boolean {sql_op} :{p_name}")

    if not where_parts:
        return []

    where_clause = " AND ".join(where_parts)

    # Build proximity ordering for boundary ranking
    order_clause = "created_at DESC"
    for f in filter_logic:
        if isinstance(f.get("value"), (int, float)):
            sql_accessor = json_path_to_sql(f["json_path"])
            p_order = f"p_order"
            params[p_order] = float(f["value"])
            order_clause = f"ABS(({sql_accessor})::numeric - :{p_order}) ASC"
            break

    query = text(f"""
        SELECT id, loan_application_id, request_payload, response_payload
        FROM loan_records
        WHERE {where_clause}
        ORDER BY {order_clause}
        LIMIT :limit
    """)

    try:
        result = await db.execute(query, params)
        rows = result.fetchall()
    except Exception as e:
        logger.warning("Customer matching query failed: %s", e)
        return []

    matched = []
    for row in rows:
        # Build match_reason from the actual values
        reasons = []
        req = row.request_payload if hasattr(row, 'request_payload') else row[2]
        for f in filter_logic:
            actual_val = _extract_value(req, f["json_path"])
            reasons.append(f"{f['field_name']}={actual_val} ({f['operator']} {f['value']})")

        matched.append({
            "id": str(row[0]) if not isinstance(row[0], str) else row[0],
            "loan_application_id": row[1] if isinstance(row[1], str) else str(row[1]),
            "request_payload": row[2] if isinstance(row[2], dict) else {},
            "response_payload": row[3] if isinstance(row[3], dict) else {},
            "match_reason": ", ".join(reasons),
        })

    return matched


def _extract_value(payload: dict, json_path: str):
    """Extract a value from a nested dict using dot-separated path."""
    parts = json_path.split(".")
    current = payload
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current
