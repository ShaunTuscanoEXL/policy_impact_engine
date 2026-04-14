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
)

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


@router.get("", response_model=list[TestCaseSuiteListResponse])
async def list_test_suites(db: AsyncSession = Depends(get_db)):
    """List all test case suites."""
    suites = await test_case_service.list_suites(db)
    return [
        TestCaseSuiteListResponse(
            id=str(item["suite"].id),
            rule_set_id=str(item["suite"].rule_set_id),
            rule_set_name=item["rule_set_name"],
            brd_id=item.get("brd_id"),
            brd_filename=item.get("brd_filename"),
            total_cases=item["suite"].total_cases,
            cases_by_category=item["suite"].cases_by_category,
            created_at=item["suite"].created_at.isoformat(),
        )
        for item in suites
    ]


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
    )
