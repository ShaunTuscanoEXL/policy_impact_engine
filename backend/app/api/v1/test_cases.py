import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import test_case_service, rule_service
from app.services.customer_matcher import match_customers
from app.schemas.test_case import (
    TestCaseGenerateRequest,
    TestCaseSuiteResponse,
    TestCaseSuiteListResponse,
    TestCaseResponse,
    MatchedCustomer,
    SuggestCountsRequest,
    SuggestedCountsResponse,
    GenerateFromVersionRequest,
    ExecuteSuiteRequest,
    SuiteExecutionResponse,
)
from app.services.test_suite_executor import execute_suite_against_version
import uuid as _uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/test-cases", tags=["Test Cases"])


@router.post("/suggest-counts", response_model=SuggestedCountsResponse)
async def suggest_counts(body: SuggestCountsRequest, db: AsyncSession = Depends(get_db)):
    """Auto-suggest test case counts based on rule set complexity.

    Analyzes the number of rules, conditions, numeric thresholds,
    and overlapping rule pairs to recommend how many test cases
    of each type would provide comprehensive coverage.
    """
    result = await test_case_service.suggest_test_counts(body.rule_set_id, db)
    if result is None:
        raise HTTPException(404, "Rule set not found")
    return SuggestedCountsResponse(**result)


@router.post("/generate", response_model=TestCaseSuiteResponse)
async def generate_test_cases(body: TestCaseGenerateRequest, db: AsyncSession = Depends(get_db)):
    """Generate test cases from a rule set.

    If counts are omitted (None), auto-suggests based on rule complexity.
    If counts are provided, uses them as maximums per category.
    """
    rule_set = await rule_service.get_rule_set(body.rule_set_id, db)
    if not rule_set:
        raise HTTPException(404, "Rule set not found")

    # Delete existing suites for this rule set (replace, not accumulate)
    existing_suites = await test_case_service.get_suites_by_rule_set(body.rule_set_id, db)
    for old_suite in existing_suites:
        await test_case_service.delete_suite(str(old_suite.id), db)

    counts = {
        "positive_count": body.positive_count,
        "negative_count": body.negative_count,
        "boundary_count": body.boundary_count,
        "edge_count": body.edge_count,
        "interaction_count": body.interaction_count,
    }

    suite = await test_case_service.generate_and_save(
        rule_set_id=body.rule_set_id,
        rules=rule_set.rules,
        counts=counts,
        max_matches=body.max_matches,
        db=db,
    )

    # Re-fetch with eagerly loaded test cases
    suite = await test_case_service.get_suite(str(suite.id), db)
    return await _build_suite_response(suite, rule_set.name, db)


def _build_last_execution_inline(suite) -> dict | None:
    """Project the suite's stored last_execution_report into the slim
    inline shape used by list endpoints. Returns None if the suite has
    never been executed."""
    if not suite.last_executed_at or not suite.last_execution_report:
        return None
    rep = suite.last_execution_report or {}
    summary = rep.get("summary", {}) or {}
    matches = int(summary.get("matches_expected") or 0)
    deviates = int(summary.get("deviates_from_expected") or 0)
    total = matches + deviates
    return {
        "executed_at": suite.last_executed_at.isoformat(),
        "version_number": rep.get("version_number"),
        "total_assertions": total,
        "passing": matches,
        "failing": deviates,
        "pass_rate": (matches / total) if total else 0.0,
    }


@router.get("", response_model=list[TestCaseSuiteListResponse])
async def list_test_suites(db: AsyncSession = Depends(get_db)):
    """List all test case suites."""
    suites = await test_case_service.list_suites(db)

    # Batch-fetch the rule_set last_modified_at for staleness detection
    from sqlalchemy import select as _s
    from app.models.rule import RuleSet as _RS
    rs_ids = {item["suite"].rule_set_id for item in suites}
    rs_lm: dict = {}
    if rs_ids:
        rows = await db.execute(_s(_RS.id, _RS.last_modified_at).where(_RS.id.in_(rs_ids)))
        rs_lm = {row[0]: row[1] for row in rows.all()}

    out = []
    for item in suites:
        suite = item["suite"]
        last_mod = rs_lm.get(suite.rule_set_id)
        is_stale = bool(last_mod and suite.created_at and last_mod > suite.created_at)
        out.append(TestCaseSuiteListResponse(
            id=str(suite.id),
            rule_set_id=str(suite.rule_set_id),
            rule_set_name=item["rule_set_name"],
            brd_id=item.get("brd_id"),
            brd_filename=item.get("brd_filename"),
            total_cases=suite.total_cases,
            cases_by_category=suite.cases_by_category,
            created_at=suite.created_at.isoformat(),
            last_execution=_build_last_execution_inline(suite),
            is_stale=is_stale,
        ))
    return out


@router.get("/by-ruleset/{rule_set_id}", response_model=list[TestCaseSuiteListResponse])
async def get_suites_by_ruleset(rule_set_id: str, db: AsyncSession = Depends(get_db)):
    """Get all test suites for a specific rule set."""
    suites = await test_case_service.get_suites_by_rule_set(rule_set_id, db)
    rule_set = await rule_service.get_rule_set(rule_set_id, db)
    rs_name = rule_set.name if rule_set else None
    return [
        TestCaseSuiteListResponse(
            id=str(s.id),
            rule_set_id=str(s.rule_set_id),
            rule_set_name=rs_name,
            total_cases=s.total_cases,
            cases_by_category=s.cases_by_category,
            created_at=s.created_at.isoformat(),
        )
        for s in suites
    ]


@router.get("/by-brd/{brd_id}/export/{format}")
async def export_by_brd(brd_id: str, format: str, db: AsyncSession = Depends(get_db)):
    """Export all test cases for a BRD across all rule sets."""
    if format not in ("csv", "json"):
        raise HTTPException(400, "Format must be 'csv' or 'json'")

    result = await test_case_service.export_by_brd(brd_id, format, db)
    if result is None:
        raise HTTPException(404, "No test suites found for this BRD")

    if format == "csv":
        return StreamingResponse(
            iter([result]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=test_cases_brd_{brd_id}.csv"},
        )
    return result


@router.get("/{suite_id}", response_model=TestCaseSuiteResponse)
async def get_test_suite(suite_id: str, db: AsyncSession = Depends(get_db)):
    """Get a test case suite with all test cases and matched customers."""
    suite = await test_case_service.get_suite(suite_id, db)
    if not suite:
        raise HTTPException(404, "Test case suite not found")

    rule_set = await rule_service.get_rule_set(str(suite.rule_set_id), db)
    rs_name = rule_set.name if rule_set else None

    return await _build_suite_response(suite, rs_name, db)


@router.get("/{suite_id}/export/{format}")
async def export_test_suite(suite_id: str, format: str, db: AsyncSession = Depends(get_db)):
    """Export a test case suite as CSV or JSON."""
    if format not in ("csv", "json"):
        raise HTTPException(400, "Format must be 'csv' or 'json'")

    result = await test_case_service.export_suite(suite_id, format, db)
    if result is None:
        raise HTTPException(404, "Test case suite not found")

    if format == "csv":
        return StreamingResponse(
            iter([result]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=test_cases_{suite_id}.csv"},
        )
    return result


@router.delete("/{suite_id}")
async def delete_test_suite(suite_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a test case suite."""
    deleted = await test_case_service.delete_suite(suite_id, db)
    if not deleted:
        raise HTTPException(404, "Test case suite not found")
    return {"status": "deleted"}


# ── Slice 4 wire-ups ────────────────────────────────────────────────────


@router.post("/generate-from-version", response_model=TestCaseSuiteResponse)
async def generate_from_version(
    body: GenerateFromVersionRequest, db: AsyncSession = Depends(get_db)
):
    """Generate a test case suite directly from a LiveRuleVersion's
    snapshot — the authoritative live rule set at that version.

    Every loan match comes from real loan_records (no mocks). Counts
    are honoured per category; passing None auto-suggests via the
    same heuristic the rule_set generator uses.
    """
    counts = {
        "positive_count": body.positive_count,
        "negative_count": body.negative_count,
        "boundary_count": body.boundary_count,
        "edge_count": body.edge_count,
        "interaction_count": body.interaction_count,
    }
    suite = await test_case_service.generate_from_version(
        version_id=body.version_id,
        counts=counts,
        max_matches=body.max_matches,
        db=db,
    )
    if suite is None:
        raise HTTPException(404, "Live rule version not found or no rule set to bind to")
    suite = await test_case_service.get_suite(str(suite.id), db)
    rule_set = await rule_service.get_rule_set(str(suite.rule_set_id), db)
    return await _build_suite_response(suite, rule_set.name if rule_set else None, db)


@router.post("/{suite_id}/execute", response_model=SuiteExecutionResponse)
async def execute_test_suite(
    suite_id: str,
    body: ExecuteSuiteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run every test case in this suite against a LiveRuleVersion's
    rules using each test case's pre-resolved matched_loan_ids.

    Returns a report comparing each test case's expected_decision to
    the actual decisions the rules produce when applied to the
    matched loans. Useful for "did my BRD's intent actually land
    once it merged into the live repo?"
    """
    try:
        report = await execute_suite_against_version(
            db,
            suite_id=_uuid.UUID(suite_id),
            version_id=_uuid.UUID(body.version_id),
            executed_by=body.executed_by,
            rationale=body.rationale,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    return SuiteExecutionResponse(**report)


async def _build_suite_response(suite, rule_set_name: str | None, db: AsyncSession) -> TestCaseSuiteResponse:
    """Build a full suite response with test cases and matched customer details."""
    test_case_responses = []

    for tc in (suite.test_cases or []):
        # Build human-readable filter description
        filter_parts = []
        for f in (tc.filter_logic or []):
            op = f.get('operator', '')
            val = f.get('value', '')
            field = f.get('field_name', '')
            if op == 'between' and isinstance(val, (list, tuple)) and len(val) == 2:
                filter_parts.append(f"{field} between {val[0]} and {val[1]}")
            elif op in ('in', 'not_in') and isinstance(val, (list, tuple)):
                filter_parts.append(f"{field} {op} [{', '.join(str(v) for v in val)}]")
            else:
                filter_parts.append(f"{field} {op} {val}")

        # Fetch matched customer details
        customers = []
        for loan_id in (tc.matched_loan_ids or []):
            from app.models.loan_record import LoanRecord
            from sqlalchemy import select
            lr_result = await db.execute(
                select(LoanRecord).where(LoanRecord.loan_application_id == loan_id)
            )
            lr = lr_result.scalar_one_or_none()
            if lr:
                customers.append(MatchedCustomer(
                    id=str(lr.id),
                    loan_application_id=lr.loan_application_id,
                    request_payload=lr.request_payload,
                    response_payload=lr.response_payload,
                    match_reason=" AND ".join(filter_parts),
                ))

        test_case_responses.append(TestCaseResponse(
            id=str(tc.id),
            test_case_id=tc.test_case_id,
            description=tc.description,
            source_rule_ids=tc.source_rule_ids or [],
            source_rule_uuids=tc.source_rule_uuids or None,
            category=tc.category.value if hasattr(tc.category, 'value') else tc.category,
            input_values=tc.input_values or {},
            filter_logic=tc.filter_logic or [],
            filter_description=" AND ".join(filter_parts) if filter_parts else None,
            expected_outcome=tc.expected_outcome or {},
            rationale=tc.rationale,
            matched_loan_ids=tc.matched_loan_ids or [],
            match_count=tc.match_count or 0,
            matched_customers=customers,
        ))

    # Sort by category order, then by test_case_id within each category
    category_order = {"POSITIVE": 0, "NEGATIVE": 1, "BOUNDARY": 2, "EDGE": 3, "INTERACTION": 4}
    test_case_responses.sort(
        key=lambda tc: (category_order.get(tc.category, 99), tc.test_case_id)
    )

    # Compute staleness — was the source rule_set modified after this
    # suite was generated? If yes the test cases (and any prior
    # execution report) may not reflect the current rules.
    rs_lm = None
    is_stale = False
    try:
        from sqlalchemy import select as _s
        from app.models.rule import RuleSet as _RS
        rs_q = await db.execute(_s(_RS.last_modified_at).where(_RS.id == suite.rule_set_id))
        rs_lm = rs_q.scalar_one_or_none()
        if rs_lm and suite.created_at and rs_lm > suite.created_at:
            is_stale = True
    except Exception:
        pass

    return TestCaseSuiteResponse(
        id=str(suite.id),
        rule_set_id=str(suite.rule_set_id),
        rule_set_name=rule_set_name,
        total_cases=suite.total_cases,
        cases_by_category=suite.cases_by_category,
        coverage_stats=suite.coverage_stats or {},
        suggested_counts=suite.suggested_counts or {},
        test_cases=test_case_responses,
        created_at=suite.created_at.isoformat(),
        last_execution_report=suite.last_execution_report,
        last_executed_at=suite.last_executed_at.isoformat() if suite.last_executed_at else None,
        last_executed_against_version_id=str(suite.last_executed_against_version_id) if suite.last_executed_against_version_id else None,
        is_stale=is_stale,
        rule_set_last_modified_at=rs_lm.isoformat() if rs_lm else None,
        last_executed_by=getattr(suite, "last_executed_by", None),
        last_execution_rationale=getattr(suite, "last_execution_rationale", None),
    )
