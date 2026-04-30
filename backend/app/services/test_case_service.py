import csv
import io
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.test_case import TestCaseSuite, TestCase, TestCaseCategory
from app.models.rule import RuleSet, Rule
from app.models.brd import BrdDocument
from app.models.live_repo import LiveRuleVersion
from app.schemas.rule import RuleDefinition, Condition, Action
from app.pipeline.test_case_generator import generate_test_cases, suggest_counts
from app.services.customer_matcher import match_customers

logger = logging.getLogger(__name__)


def _format_filter_part(f: dict) -> str:
    """Format a single filter condition for human-readable display."""
    op = f.get("operator", "")
    val = f.get("value", "")
    field = f.get("field_name", "")
    if op == "between" and isinstance(val, (list, tuple)) and len(val) == 2:
        return f"{field} between {val[0]} and {val[1]}"
    if op in ("in", "not_in") and isinstance(val, (list, tuple)):
        return f"{field} {op} [{', '.join(str(v) for v in val)}]"
    return f"{field} {op} {val}"


def _rules_to_defs(rules: list) -> list[RuleDefinition]:
    """Convert DB Rule objects to RuleDefinition schema objects."""
    rule_defs = []
    for r in rules:
        conditions = r.conditions if isinstance(r.conditions, list) else []
        actions = r.actions if isinstance(r.actions, list) else []
        rule_defs.append(RuleDefinition(
            rule_id=r.rule_id,
            rule_name=r.rule_name,
            description=r.description or "",
            rule_type=r.rule_type.value if hasattr(r.rule_type, 'value') else r.rule_type,
            conditions=[Condition(**c) if isinstance(c, dict) else c for c in conditions],
            actions=[Action(**a) if isinstance(a, dict) else a for a in actions],
            priority=r.priority,
            uuid=str(r.id) if getattr(r, "id", None) else None,
        ))
    return rule_defs


async def suggest_test_counts(rule_set_id: str, db: AsyncSession) -> dict | None:
    """Suggest test case counts for a rule set based on complexity analysis."""
    result = await db.execute(
        select(RuleSet).options(selectinload(RuleSet.rules)).where(RuleSet.id == rule_set_id)
    )
    rule_set = result.scalar_one_or_none()
    if not rule_set:
        return None

    rule_defs = _rules_to_defs(rule_set.rules)
    return suggest_counts(rule_defs)


def _snapshot_rules_to_defs(snapshot: list[dict]) -> list[RuleDefinition]:
    """Convert the rule_snapshot list (dicts) on a LiveRuleVersion to
    RuleDefinition objects so the existing generator can operate on them
    just like it does on RuleSet.rules."""
    rule_defs: list[RuleDefinition] = []
    for r in snapshot or []:
        if not isinstance(r, dict):
            continue
        conditions = r.get("conditions") or []
        actions = r.get("actions") or []
        rt_raw = r.get("rule_type") or "ELIGIBILITY"
        rule_defs.append(RuleDefinition(
            rule_id=str(r.get("rule_id") or r.get("id") or "RULE"),
            rule_name=str(r.get("rule_name") or r.get("rule_id") or "Rule"),
            description=str(r.get("description") or ""),
            rule_type=rt_raw if hasattr(rt_raw, "value") else rt_raw,
            conditions=[Condition(**c) if isinstance(c, dict) else c for c in conditions],
            actions=[Action(**a) if isinstance(a, dict) else a for a in actions],
            priority=int(r.get("priority", 0)),
            uuid=str(r.get("id")) if r.get("id") else None,
        ))
    return rule_defs


async def generate_and_save(
    rule_set_id: str,
    rules: list,
    counts: dict,
    db: AsyncSession,
    max_matches: int = 10,
) -> TestCaseSuite:
    """Generate test cases, match customers, and persist to DB."""
    rule_defs = _rules_to_defs(rules)

    # Generate test cases
    output = generate_test_cases(
        rules=rule_defs,
        rule_set_id=rule_set_id,
        **counts,
    )

    # Create suite
    suite = TestCaseSuite(
        rule_set_id=rule_set_id,
        total_cases=output.total_cases,
        cases_by_category=output.cases_by_category,
        coverage_stats=output.coverage_stats,
        suggested_counts=output.suggested_counts,
    )
    db.add(suite)
    await db.flush()  # Get suite.id

    # For each test case, match customers from loan DB
    for tc in output.test_cases:
        # Use savepoint so a failed match query doesn't poison the transaction
        matched_ids = []
        try:
            async with db.begin_nested():
                matched = await match_customers(tc.filter_logic, db, limit=max_matches)
                matched_ids = [m["loan_application_id"] for m in matched]
        except Exception as e:
            logger.warning("Customer matching failed for %s: %s", tc.test_case_id, e)

        test_case = TestCase(
            suite_id=suite.id,
            test_case_id=tc.test_case_id,
            description=tc.description,
            source_rule_ids=tc.source_rule_ids,
            source_rule_uuids=tc.source_rule_uuids or None,
            category=TestCaseCategory(tc.category.value),
            input_values=tc.input_values,
            filter_logic=tc.filter_logic,
            expected_outcome=tc.expected_outcome,
            rationale=tc.rationale,
            matched_loan_ids=matched_ids,
            match_count=len(matched_ids),
        )
        db.add(test_case)

    await db.commit()
    await db.refresh(suite)
    return suite


async def generate_from_version(
    version_id: str,
    counts: dict,
    db: AsyncSession,
    max_matches: int = 10,
) -> TestCaseSuite | None:
    """Generate a test case suite from a LiveRuleVersion's snapshot.

    The version's snapshot is the authoritative live rule set at that
    version, so this produces tests that exercise exactly what the
    repository says is "current" — independent of any specific BRD's
    rule_set.

    The TestCaseSuite still requires a rule_set_id (existing schema).
    We bind the suite to whichever rule_set the version originated from
    (its source_brd_id's latest rule_set), or to the most recent
    rule_set if no source_brd is recorded.
    """
    import uuid as _uuid
    try:
        version_uuid = _uuid.UUID(str(version_id))
    except (TypeError, ValueError):
        return None
    version = await db.get(LiveRuleVersion, version_uuid)
    if version is None:
        return None

    # Find a rule_set to bind the suite to (existing schema requires it)
    rs_q = await db.execute(
        select(RuleSet).order_by(RuleSet.created_at.desc()).limit(1)
    )
    if version.source_brd_id is not None:
        bound_q = await db.execute(
            select(RuleSet)
            .where(RuleSet.brd_document_id == version.source_brd_id)
            .order_by(RuleSet.created_at.desc())
            .limit(1)
        )
        bound = bound_q.scalar_one_or_none() or rs_q.scalar_one_or_none()
    else:
        bound = rs_q.scalar_one_or_none()
    if bound is None:
        return None

    rule_defs = _snapshot_rules_to_defs(list(version.rule_snapshot or []))
    output = generate_test_cases(
        rules=rule_defs,
        rule_set_id=str(bound.id),
        **counts,
    )

    suite = TestCaseSuite(
        rule_set_id=bound.id,
        total_cases=output.total_cases,
        cases_by_category=output.cases_by_category,
        coverage_stats={
            **(output.coverage_stats or {}),
            "source_live_version_id": str(version.id),
            "source_live_version_number": version.version_number,
        },
        suggested_counts=output.suggested_counts,
    )
    db.add(suite)
    await db.flush()

    for tc in output.test_cases:
        matched_ids: list[str] = []
        try:
            async with db.begin_nested():
                matched = await match_customers(tc.filter_logic, db, limit=max_matches)
                matched_ids = [m["loan_application_id"] for m in matched]
        except Exception as e:  # noqa: BLE001
            logger.warning("Customer matching failed for %s: %s", tc.test_case_id, e)

        db.add(TestCase(
            suite_id=suite.id,
            test_case_id=tc.test_case_id,
            description=tc.description,
            source_rule_ids=tc.source_rule_ids,
            source_rule_uuids=tc.source_rule_uuids or None,
            category=TestCaseCategory(tc.category.value),
            input_values=tc.input_values,
            filter_logic=tc.filter_logic,
            expected_outcome=tc.expected_outcome,
            rationale=tc.rationale,
            matched_loan_ids=matched_ids,
            match_count=len(matched_ids),
        ))

    await db.commit()
    await db.refresh(suite)
    return suite


async def get_suite(suite_id: str, db: AsyncSession):
    """Get a test case suite with all test cases."""
    import uuid as _uuid
    try:
        suite_uuid = _uuid.UUID(str(suite_id))
    except (TypeError, ValueError):
        return None
    result = await db.execute(
        select(TestCaseSuite)
        .options(selectinload(TestCaseSuite.test_cases))
        .where(TestCaseSuite.id == suite_uuid)
    )
    return result.scalar_one_or_none()


async def get_suites_by_rule_set(rule_set_id: str, db: AsyncSession):
    """Get all test suites for a rule set."""
    import uuid as _uuid
    try:
        rs_uuid = _uuid.UUID(str(rule_set_id))
    except (TypeError, ValueError):
        return []
    result = await db.execute(
        select(TestCaseSuite)
        .where(TestCaseSuite.rule_set_id == rs_uuid)
        .order_by(TestCaseSuite.created_at.desc())
    )
    return result.scalars().all()


async def list_suites(db: AsyncSession):
    """List all test case suites with rule set names."""
    result = await db.execute(
        select(TestCaseSuite)
        .order_by(TestCaseSuite.created_at.desc())
    )
    suites = result.scalars().all()

    # Resolve rule set names and BRD info
    enriched = []
    for s in suites:
        rs_result = await db.execute(select(RuleSet).where(RuleSet.id == s.rule_set_id))
        rs = rs_result.scalar_one_or_none()
        brd = None
        if rs and rs.brd_document_id:
            brd_result = await db.execute(select(BrdDocument).where(BrdDocument.id == rs.brd_document_id))
            brd = brd_result.scalar_one_or_none()
        enriched.append({
            "suite": s,
            "rule_set_name": rs.name if rs else None,
            "brd_id": str(brd.id) if brd else None,
            "brd_filename": brd.filename if brd else None,
        })
    return enriched


async def delete_suite(suite_id: str, db: AsyncSession) -> bool:
    """Delete a test case suite."""
    import uuid as _uuid
    try:
        suite_uuid = _uuid.UUID(str(suite_id))
    except (TypeError, ValueError):
        return False
    result = await db.execute(
        select(TestCaseSuite)
        .options(selectinload(TestCaseSuite.test_cases))
        .where(TestCaseSuite.id == suite_uuid)
    )
    suite = result.scalar_one_or_none()
    if not suite:
        return False
    await db.delete(suite)
    await db.commit()
    return True


async def export_suite(suite_id: str, format: str, db: AsyncSession) -> str | dict:
    """Export a test case suite as CSV or JSON with matched customers."""
    suite = await get_suite(suite_id, db)
    if not suite:
        return None

    if format == "json":
        test_cases_data = []
        for tc in suite.test_cases:
            # Get matched customer records
            customers = []
            for loan_id in (tc.matched_loan_ids or []):
                from app.models.loan_record import LoanRecord
                lr_result = await db.execute(
                    select(LoanRecord).where(LoanRecord.loan_application_id == loan_id)
                )
                lr = lr_result.scalar_one_or_none()
                if lr:
                    customers.append({
                        "loan_application_id": lr.loan_application_id,
                        "request_payload": lr.request_payload,
                        "response_payload": lr.response_payload,
                    })

            filter_parts = [_format_filter_part(f) for f in (tc.filter_logic or [])]

            test_cases_data.append({
                "test_case_id": tc.test_case_id,
                "description": tc.description,
                "category": tc.category.value if hasattr(tc.category, 'value') else tc.category,
                "input_values": tc.input_values or {},
                "filter_logic": tc.filter_logic,
                "filter_description": " AND ".join(filter_parts),
                "expected_outcome": tc.expected_outcome,
                "rationale": tc.rationale,
                "matched_customers": customers,
            })

        return {
            "suite_id": str(suite.id),
            "rule_set_id": str(suite.rule_set_id),
            "total_cases": suite.total_cases,
            "cases_by_category": suite.cases_by_category,
            "coverage_stats": suite.coverage_stats or {},
            "suggested_counts": suite.suggested_counts or {},
            "test_cases": test_cases_data,
        }

    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "test_case_id", "description", "category", "rationale",
            "input_values", "filter_logic", "expected_decision",
            "expected_outcome", "source_rule_ids",
            "loan_application_id", "match_reason",
        ])

        for tc in suite.test_cases:
            filter_parts = [_format_filter_part(f) for f in (tc.filter_logic or [])]
            filter_str = " AND ".join(filter_parts)
            exp_decision = (tc.expected_outcome or {}).get("decision", "UNKNOWN")
            source_ids = ", ".join(tc.source_rule_ids or [])
            input_str = json.dumps(tc.input_values or {})

            if tc.matched_loan_ids:
                for loan_id in tc.matched_loan_ids:
                    writer.writerow([
                        tc.test_case_id, tc.description,
                        tc.category.value if hasattr(tc.category, 'value') else tc.category,
                        tc.rationale or "",
                        input_str, filter_str, exp_decision,
                        json.dumps(tc.expected_outcome), source_ids,
                        loan_id, filter_str,
                    ])
            else:
                # Write test case even without matched loans
                writer.writerow([
                    tc.test_case_id, tc.description,
                    tc.category.value if hasattr(tc.category, 'value') else tc.category,
                    tc.rationale or "",
                    input_str, filter_str, exp_decision,
                    json.dumps(tc.expected_outcome), source_ids,
                    "", "",
                ])

        return output.getvalue()

    return None


async def export_by_brd(brd_id: str, format: str, db: AsyncSession) -> str | dict | None:
    """Export all test cases across all rule sets for a BRD."""
    rs_result = await db.execute(
        select(RuleSet).where(RuleSet.brd_document_id == brd_id)
    )
    rule_sets = rs_result.scalars().all()
    if not rule_sets:
        return None

    if format == "json":
        all_suites = []
        for rs in rule_sets:
            suites = await get_suites_by_rule_set(str(rs.id), db)
            for s in suites:
                suite_data = await export_suite(str(s.id), "json", db)
                if suite_data:
                    suite_data["rule_set_name"] = rs.name
                    all_suites.append(suite_data)
        return {"brd_id": brd_id, "test_suites": all_suites}

    elif format == "csv":
        all_csv = io.StringIO()
        writer = csv.writer(all_csv)
        writer.writerow([
            "rule_set_name", "test_case_id", "description", "category",
            "rationale", "input_values", "filter_logic", "expected_decision",
            "expected_outcome", "source_rule_ids",
            "loan_application_id", "match_reason",
        ])

        for rs in rule_sets:
            suites = await get_suites_by_rule_set(str(rs.id), db)
            for s in suites:
                suite = await get_suite(str(s.id), db)
                if not suite:
                    continue
                for tc in suite.test_cases:
                    filter_parts = [_format_filter_part(f) for f in (tc.filter_logic or [])]
                    filter_str = " AND ".join(filter_parts)
                    exp_decision = (tc.expected_outcome or {}).get("decision", "UNKNOWN")
                    source_ids = ", ".join(tc.source_rule_ids or [])
                    input_str = json.dumps(tc.input_values or {})

                    if tc.matched_loan_ids:
                        for loan_id in tc.matched_loan_ids:
                            writer.writerow([
                                rs.name, tc.test_case_id, tc.description,
                                tc.category.value if hasattr(tc.category, 'value') else tc.category,
                                tc.rationale or "",
                                input_str, filter_str, exp_decision,
                                json.dumps(tc.expected_outcome), source_ids,
                                loan_id, filter_str,
                            ])
                    else:
                        writer.writerow([
                            rs.name, tc.test_case_id, tc.description,
                            tc.category.value if hasattr(tc.category, 'value') else tc.category,
                            tc.rationale or "",
                            input_str, filter_str, exp_decision,
                            json.dumps(tc.expected_outcome), source_ids,
                            "", "",
                        ])

        return all_csv.getvalue()

    return None
