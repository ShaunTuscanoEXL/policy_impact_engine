"""Execute a generated test_case_suite against the loan_records corpus
through the runtime engine, and report decision distributions + per-test
match counts.

This is the natural follow-on the user asked about: "execution of the
BRD test suite to look for impact". Conceptually:
- A test case is a synthetic/expected scenario that asserts a particular
  policy outcome (REJECTED, APPROVED, FLAGGED, ...).
- We evaluate the SAME live rules against actual loan records that match
  the test case's filter_logic (already pre-computed and stored on
  TestCase.matched_loan_ids during generation).
- The output tells the user "for the loans that matched test case X
  in the bureau, here's what the rules ACTUALLY decided".

This composes with ImpactRun (which compares two whole versions) by
giving a finer-grained per-rule lens.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.live_repo import LiveRuleVersion
from app.models.loan_record import LoanRecord
from app.models.test_case import TestCase, TestCaseSuite
from app.runtime import evaluate_snapshot


async def execute_suite_against_version(
    db: AsyncSession,
    *,
    suite_id: uuid.UUID,
    version_id: uuid.UUID,
) -> dict[str, Any]:
    """Run every test case in ``suite`` against ``version``'s rule
    snapshot using the matched_loan_ids that were resolved at generation
    time. Returns a structured report.

    Report shape:
        {
          "suite_id": "...",
          "version_id": "...",
          "version_number": 17,
          "total_cases": 24,
          "cases_evaluated": 24,
          "results": [
            {
              "test_case_id": "POSITIVE-01",
              "category": "POSITIVE",
              "expected_decision": "APPROVED",
              "matched_loan_count": 12,
              "actual_distribution": {"APPROVED": 11, "REJECTED": 1},
              "matches_expected": 11,
              "deviates_from_expected": 1,
              "first_deviation_reason": "HIGH_DTI_RATIO"  # or null
            },
            ...
          ],
          "summary": {
            "matches_expected": 220,
            "deviates_from_expected": 12,
            "by_category": {
              "POSITIVE": {"matches": 90, "deviates": 4},
              ...
            }
          }
        }

    No mock data. No hard-coded outcomes. Loans come from the
    loan_records table; rules come from the version snapshot; the
    expected decision comes from each test case's expected_outcome.
    """
    # Load suite with test cases + version with snapshot
    suite_q = await db.execute(
        select(TestCaseSuite)
        .options(selectinload(TestCaseSuite.test_cases))
        .where(TestCaseSuite.id == suite_id)
    )
    suite = suite_q.scalar_one_or_none()
    if suite is None:
        raise ValueError(f"Test case suite {suite_id} not found")

    version = await db.get(LiveRuleVersion, version_id)
    if version is None:
        raise ValueError(f"Live rule version {version_id} not found")

    snapshot: list[dict] = list(version.rule_snapshot or [])

    results: list[dict[str, Any]] = []
    total_match = 0
    total_dev = 0
    by_category: dict[str, dict[str, int]] = {}

    for tc in suite.test_cases or []:
        cat = tc.category.value if hasattr(tc.category, "value") else str(tc.category)
        expected_decision = (tc.expected_outcome or {}).get("decision", "APPROVED")
        expected_decision = str(expected_decision).upper()

        actual_dist: dict[str, int] = {}
        first_dev_reason: str | None = None

        if tc.matched_loan_ids:
            # Fetch only the loans referenced by this test case
            loans_q = await db.execute(
                select(LoanRecord).where(
                    LoanRecord.loan_application_id.in_(tc.matched_loan_ids)
                )
            )
            for loan in loans_q.scalars():
                res = evaluate_snapshot(
                    snapshot, loan.request_payload or {},
                    loan_application_id=loan.loan_application_id,
                )
                actual_dist[res.decision] = actual_dist.get(res.decision, 0) + 1
                if first_dev_reason is None and res.decision != expected_decision:
                    first_dev_reason = (res.reasons[0] if res.reasons else None)

        matched_count = sum(actual_dist.values())
        matches_expected = actual_dist.get(expected_decision, 0)
        deviates = matched_count - matches_expected

        total_match += matches_expected
        total_dev += deviates
        cat_bucket = by_category.setdefault(cat, {"matches": 0, "deviates": 0})
        cat_bucket["matches"] += matches_expected
        cat_bucket["deviates"] += deviates

        results.append({
            "test_case_id": tc.test_case_id,
            "category": cat,
            "expected_decision": expected_decision,
            "matched_loan_count": matched_count,
            "actual_distribution": actual_dist,
            "matches_expected": matches_expected,
            "deviates_from_expected": deviates,
            "first_deviation_reason": first_dev_reason,
        })

    report = {
        "suite_id": str(suite.id),
        "version_id": str(version.id),
        "version_number": version.version_number,
        "total_cases": len(suite.test_cases or []),
        "cases_evaluated": len(results),
        "executed_at": datetime.utcnow().isoformat(),
        "results": results,
        "summary": {
            "matches_expected": total_match,
            "deviates_from_expected": total_dev,
            "by_category": by_category,
        },
    }

    # Persist on the suite so the UI can show "X passing / Y failing"
    # without re-running every page load. Last-write-wins is fine — the
    # UI always shows the latest execution + the version it ran against.
    suite.last_execution_report = report
    suite.last_executed_at = datetime.utcnow()
    suite.last_executed_against_version_id = version.id
    await db.commit()

    return report
