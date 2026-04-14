"""Matches loan records from the database against test case filter conditions."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.field_registry import json_path_to_sql

logger = logging.getLogger(__name__)


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
    """
    if not filter_logic:
        return []

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
