"""API endpoints for test case generation and retrieval."""

import io
import csv
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.test_case import (
    TestCaseGenerateRequest,
    TestCaseSuiteResponse,
    TestCaseResponse,
    TestCaseSuiteListResponse,
)
from app.services import test_case_service
from app.services.rule_service import get_rule_set as get_rule_set_service

router = APIRouter(prefix="/test-cases", tags=["Test Cases"])


@router.get("", response_model=list[TestCaseSuiteListResponse])
async def list_all_suites(db: AsyncSession = Depends(get_db)):
    """List all test case suites with rule set names."""
    suites = await test_case_service.list_suites(db)
    result = []
    for s in suites:
        rs_name = None
        try:
            rs = await get_rule_set_service(str(s.rule_set_id), db)
            if rs:
                rs_name = rs.name
        except Exception:
            pass
        result.append(TestCaseSuiteListResponse(
            id=str(s.id),
            rule_set_id=str(s.rule_set_id),
            rule_set_name=rs_name,
            total_cases=s.total_cases,
            cases_by_category=s.cases_by_category or {},
            created_at=s.created_at.isoformat() if s.created_at else "",
        ))
    return result


@router.post("/generate", response_model=TestCaseSuiteResponse, status_code=200)
async def generate_test_cases(body: TestCaseGenerateRequest, db: AsyncSession = Depends(get_db)):
    """Generate test cases for an approved rule set (standalone endpoint)."""
    rule_set = await get_rule_set_service(body.rule_set_id, db)
    if not rule_set:
        raise HTTPException(status_code=404, detail="Rule set not found")
    if not rule_set.rules:
        raise HTTPException(status_code=400, detail="No rules found in rule set")

    suite = await test_case_service.generate_and_save(
        rule_set_id=body.rule_set_id,
        rules=rule_set.rules,
        baseline_config=body.baseline_config,
        db=db,
    )
    await db.commit()

    # Re-fetch with test cases loaded
    suite = await test_case_service.get_suite(str(suite.id), db)
    return _suite_to_response(suite, rule_set_name=rule_set.name)


@router.get("/by-ruleset/{rule_set_id}", response_model=TestCaseSuiteResponse | None, status_code=200)
async def get_by_rule_set(rule_set_id: str, db: AsyncSession = Depends(get_db)):
    """Get the most recent test case suite for a rule set."""
    suite = await test_case_service.get_by_rule_set(rule_set_id, db)
    if not suite:
        return None
    rs_name = await _resolve_rule_set_name(rule_set_id, db)
    return _suite_to_response(suite, rule_set_name=rs_name)


@router.get("/{suite_id}", response_model=TestCaseSuiteResponse, status_code=200)
async def get_test_case_suite(suite_id: str, db: AsyncSession = Depends(get_db)):
    """Get a test case suite by ID with all test cases."""
    suite = await test_case_service.get_suite(suite_id, db)
    if not suite:
        raise HTTPException(status_code=404, detail="Test case suite not found")
    rs_name = await _resolve_rule_set_name(str(suite.rule_set_id), db)
    return _suite_to_response(suite, rule_set_name=rs_name)


@router.get("/{suite_id}/export/csv")
async def export_csv(suite_id: str, db: AsyncSession = Depends(get_db)):
    """Export test cases as CSV download."""
    suite = await test_case_service.get_suite(suite_id, db)
    if not suite:
        raise HTTPException(status_code=404, detail="Test case suite not found")

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row - collect all unique input fields
    all_input_fields = set()
    for tc in suite.test_cases:
        all_input_fields.update(tc.inputs.keys())
    input_fields = sorted(all_input_fields)

    header = ["test_case_id", "description", "category", "source_rule_ids"] + input_fields + [
        "expected_decision", "expected_eligible_amount", "expected_interest_rate",
        "expected_baseline_decision", "expected_flags"
    ]
    writer.writerow(header)

    for tc in suite.test_cases:
        outcome = tc.expected_outcome or {}
        row = [
            tc.test_case_id,
            tc.description,
            tc.category.value if hasattr(tc.category, 'value') else tc.category,
            ";".join(tc.source_rule_ids) if tc.source_rule_ids else "",
        ]
        # Input fields
        for f in input_fields:
            row.append(tc.inputs.get(f, ""))
        # Expected outcome
        row.extend([
            outcome.get("decision", ""),
            outcome.get("eligible_amount", ""),
            outcome.get("interest_rate", ""),
            outcome.get("baseline_decision", ""),
            ";".join(outcome.get("flags", [])),
        ])
        writer.writerow(row)

    filename = f"test_cases_{suite_id}.csv"
    return StreamingResponse(
        io.StringIO(output.getvalue()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{suite_id}/export/json")
async def export_json(suite_id: str, db: AsyncSession = Depends(get_db)):
    """Export test cases as JSON download."""
    suite = await test_case_service.get_suite(suite_id, db)
    if not suite:
        raise HTTPException(status_code=404, detail="Test case suite not found")

    data = {
        "suite_id": str(suite.id),
        "rule_set_id": str(suite.rule_set_id),
        "total_cases": suite.total_cases,
        "cases_by_category": suite.cases_by_category,
        "test_cases": [
            {
                "test_case_id": tc.test_case_id,
                "description": tc.description,
                "category": tc.category.value if hasattr(tc.category, 'value') else tc.category,
                "source_rule_ids": tc.source_rule_ids,
                "inputs": tc.inputs,
                "expected_outcome": tc.expected_outcome,
            }
            for tc in suite.test_cases
        ],
    }

    filename = f"test_cases_{suite_id}.json"
    return StreamingResponse(
        io.StringIO(json.dumps(data, indent=2)),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _suite_to_response(suite, rule_set_name: str | None = None) -> TestCaseSuiteResponse:
    """Convert a TestCaseSuite ORM object to a response schema."""
    return TestCaseSuiteResponse(
        id=str(suite.id),
        rule_set_id=str(suite.rule_set_id),
        rule_set_name=rule_set_name,
        total_cases=suite.total_cases,
        cases_by_category=suite.cases_by_category or {},
        test_cases=[
            TestCaseResponse(
                id=str(tc.id),
                test_case_id=tc.test_case_id,
                description=tc.description,
                source_rule_ids=tc.source_rule_ids or [],
                category=tc.category.value if hasattr(tc.category, 'value') else tc.category,
                inputs=tc.inputs or {},
                expected_outcome=tc.expected_outcome or {},
            )
            for tc in (suite.test_cases or [])
        ],
        created_at=suite.created_at.isoformat() if suite.created_at else "",
    )


async def _resolve_rule_set_name(rule_set_id: str, db: AsyncSession) -> str | None:
    """Resolve rule set ID to its name."""
    try:
        rs = await get_rule_set_service(rule_set_id, db)
        return rs.name if rs else None
    except Exception:
        return None
