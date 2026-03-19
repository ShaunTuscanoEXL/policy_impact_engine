import csv
import io
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.test_case import TestCaseSuite, TestCase, TestCaseCategory
from app.models.rule import RuleSet, Rule
from app.schemas.rule import RuleDefinition, Condition, Action
from app.pipeline.test_case_generator import generate_test_cases
from app.services.customer_matcher import match_customers

logger = logging.getLogger(__name__)


async def generate_and_save(
    rule_set_id: str,
    rules: list,
    counts: dict,
    db: AsyncSession,
) -> TestCaseSuite:
    """Generate test cases, match customers, and persist to DB."""
    # Convert DB rules to RuleDefinition objects
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
        ))

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
    )
    db.add(suite)
    await db.flush()  # Get suite.id

    # For each test case, match customers from loan DB
    for tc in output.test_cases:
        matched = await match_customers(tc.filter_logic, db, limit=10)
        matched_ids = [m["loan_application_id"] for m in matched]

        test_case = TestCase(
            suite_id=suite.id,
            test_case_id=tc.test_case_id,
            description=tc.description,
            source_rule_ids=tc.source_rule_ids,
            category=TestCaseCategory(tc.category.value),
            filter_logic=tc.filter_logic,
            expected_outcome=tc.expected_outcome,
            matched_loan_ids=matched_ids,
            match_count=len(matched_ids),
        )
        db.add(test_case)

    await db.commit()
    await db.refresh(suite)
    return suite


async def get_suite(suite_id: str, db: AsyncSession):
    """Get a test case suite with all test cases."""
    result = await db.execute(
        select(TestCaseSuite)
        .options(selectinload(TestCaseSuite.test_cases))
        .where(TestCaseSuite.id == suite_id)
    )
    return result.scalar_one_or_none()


async def get_suites_by_rule_set(rule_set_id: str, db: AsyncSession):
    """Get all test suites for a rule set."""
    result = await db.execute(
        select(TestCaseSuite)
        .where(TestCaseSuite.rule_set_id == rule_set_id)
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

    # Resolve rule set names
    enriched = []
    for s in suites:
        rs_result = await db.execute(select(RuleSet).where(RuleSet.id == s.rule_set_id))
        rs = rs_result.scalar_one_or_none()
        enriched.append({
            "suite": s,
            "rule_set_name": rs.name if rs else None,
        })
    return enriched


async def delete_suite(suite_id: str, db: AsyncSession) -> bool:
    """Delete a test case suite."""
    result = await db.execute(
        select(TestCaseSuite)
        .options(selectinload(TestCaseSuite.test_cases))
        .where(TestCaseSuite.id == suite_id)
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

    # Fetch matched customer details for all test cases
    from app.services import loan_record_service

    if format == "json":
        test_cases_data = []
        for tc in suite.test_cases:
            # Get matched customer records
            customers = []
            for loan_id in (tc.matched_loan_ids or []):
                # Query by loan_application_id
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

            # Build human-readable filter
            filter_parts = []
            for f in (tc.filter_logic or []):
                filter_parts.append(f"{f.get('field_name', '')} {f.get('operator', '')} {f.get('value', '')}")

            test_cases_data.append({
                "test_case_id": tc.test_case_id,
                "description": tc.description,
                "category": tc.category.value if hasattr(tc.category, 'value') else tc.category,
                "filter_logic": tc.filter_logic,
                "filter_description": " AND ".join(filter_parts),
                "expected_outcome": tc.expected_outcome,
                "matched_customers": customers,
            })

        return {
            "suite_id": str(suite.id),
            "rule_set_id": str(suite.rule_set_id),
            "total_cases": suite.total_cases,
            "cases_by_category": suite.cases_by_category,
            "test_cases": test_cases_data,
        }

    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "test_case_id", "description", "category", "filter_logic",
            "expected_outcome", "loan_application_id", "request_payload",
            "response_payload", "match_reason",
        ])

        for tc in suite.test_cases:
            filter_parts = []
            for f in (tc.filter_logic or []):
                filter_parts.append(f"{f.get('field_name', '')} {f.get('operator', '')} {f.get('value', '')}")
            filter_str = " AND ".join(filter_parts)

            for loan_id in (tc.matched_loan_ids or []):
                from app.models.loan_record import LoanRecord
                lr_result = await db.execute(
                    select(LoanRecord).where(LoanRecord.loan_application_id == loan_id)
                )
                lr = lr_result.scalar_one_or_none()
                if lr:
                    writer.writerow([
                        tc.test_case_id,
                        tc.description,
                        tc.category.value if hasattr(tc.category, 'value') else tc.category,
                        filter_str,
                        json.dumps(tc.expected_outcome),
                        lr.loan_application_id,
                        json.dumps(lr.request_payload),
                        json.dumps(lr.response_payload),
                        filter_str,  # match_reason = same as filter for now
                    ])

        return output.getvalue()

    return None


async def export_by_brd(brd_id: str, format: str, db: AsyncSession) -> str | dict | None:
    """Export all test cases across all rule sets for a BRD."""
    # Get all rule sets for this BRD
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
            "filter_logic", "expected_outcome", "loan_application_id",
            "request_payload", "response_payload", "match_reason",
        ])

        for rs in rule_sets:
            suites = await get_suites_by_rule_set(str(rs.id), db)
            for s in suites:
                suite = await get_suite(str(s.id), db)
                if not suite:
                    continue
                for tc in suite.test_cases:
                    filter_parts = [f"{f.get('field_name', '')} {f.get('operator', '')} {f.get('value', '')}" for f in (tc.filter_logic or [])]
                    filter_str = " AND ".join(filter_parts)
                    for loan_id in (tc.matched_loan_ids or []):
                        from app.models.loan_record import LoanRecord
                        lr_result = await db.execute(
                            select(LoanRecord).where(LoanRecord.loan_application_id == loan_id)
                        )
                        lr = lr_result.scalar_one_or_none()
                        if lr:
                            writer.writerow([
                                rs.name, tc.test_case_id, tc.description,
                                tc.category.value if hasattr(tc.category, 'value') else tc.category,
                                filter_str, json.dumps(tc.expected_outcome),
                                lr.loan_application_id, json.dumps(lr.request_payload),
                                json.dumps(lr.response_payload), filter_str,
                            ])

        return all_csv.getvalue()

    return None
