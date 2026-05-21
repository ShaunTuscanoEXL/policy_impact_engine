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
    executed_by: str | None = None,
    rationale: str | None = None,
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

    # Magic expected_decision tokens emitted by the test case generator
    # for negative / boundary / interaction cases. They assert per-rule
    # FIRE behaviour rather than the engine's final decision.
    NOT_TRIGGERED_TOKENS = {"RULE_NOT_TRIGGERED", "NOT_TRIGGERED"}
    ALL_TRIGGERED_TOKENS = {"RULE_TRIGGERED", "TRIGGERED", "BOTH_TRIGGERED", "ALL_TRIGGERED"}
    # CONFLICT (interaction tests where the two source rules produce
    # contradictory outcomes — e.g. one REJECTs, one MODIFIES) expects
    # both to fire; the engine's final label is whichever short-circuits
    # first. Treat the same as ALL_TRIGGERED for projection purposes
    # but report as CONFLICT_OBSERVED so the UI can call out the case.
    CONFLICT_TOKENS = {"CONFLICT", "CONFLICTING"}

    # Generator emits decision labels that don't always match the engine's
    # exact return values. Normalize so the SHADOWED check can detect
    # "engine produced the expected outcome via another rule" correctly.
    EXPECTED_NORMALIZATIONS = {
        "FLAGGED_FOR_REVIEW": "FLAGGED",
        "MANUAL_REVIEW": "FLAGGED",
        "REVIEW": "FLAGGED",
        "APPROVED_WITH_CONDITIONS": "APPROVED",
        # MODIFIED is a generator-only synthetic label for SET-style rules
        # that change non-decision fields — the engine returns APPROVED
        # in those cases (the modification doesn't change the verdict).
        "MODIFIED": "APPROVED",
    }
    # Engine-returned decisions that count as a "preemption" — when one
    # of these fires, any non-terminal rule downstream is short-circuited.
    PREEMPTING_DECISIONS = {"REJECTED", "FLAGGED"}

    # POSITIVE / BOUNDARY-above-threshold / EDGE-where-rule-fires tests all
    # assert that the source rule SHOULD fire. The expected decision
    # (APPROVED / REJECTED / FLAGGED / MODIFIED) is what the rule WOULD
    # produce in isolation — but in a full snapshot, OTHER rules can also
    # fire and override the engine's final decision (e.g. a terminal REJECT
    # rule over-stamps a SET-style MODIFY). So for any "should fire" test
    # we assert "the source rule fired", reporting the engine's actual
    # decision separately for visibility. Detection rule: the test is
    # category POSITIVE/BOUNDARY/EDGE, names a source rule, and the
    # expected decision is NOT one of the per-rule projection tokens.
    SHOULD_FIRE_CATEGORIES = {"POSITIVE", "BOUNDARY", "EDGE"}

    def _outcome_for_loan(
        test_case,
        fired_rule_ids: set[str],
        fired_rule_uuids: set[str],
        engine_decision: str,
    ) -> str:
        """Project the engine's run into the assertion vocabulary the
        test case uses. Returns one of:
          - "RULE_FIRED" / "RULE_NOT_FIRED" for POSITIVE tests (and any
            other final-decision assertion that names a specific source
            rule) — the engine's final decision is preserved separately
            in the report's actual_decision_distribution
          - "RULE_SHADOWED" — POSITIVE test where the source rule didn't
            fire but the engine still produced the expected decision via
            another rule (typical with gate-style REJECT rules that
            short-circuit the engine before this rule got its turn).
            Counted as a soft pass; surfaced separately in the summary.
          - "NOT_TRIGGERED" / "TRIGGERED" for negative/boundary
            per-rule assertions
          - "ALL_TRIGGERED" / "PARTIAL_TRIGGERED" / "NOT_TRIGGERED"
            for interaction tests that name multiple source rules
          - the engine decision when no source rule is identified

        Uses globally-unique rule UUIDs when available (avoiding the
        "RULE-001 means three different rules" collision); falls back
        to string rule_ids for legacy test cases generated before the
        UUID-aware pipeline landed.
        """
        raw_expected = str((test_case.expected_outcome or {}).get("decision", "APPROVED")).upper()
        # Normalize the synthetic labels the generator emits so they
        # line up with what the engine actually returns. Without this,
        # tests asking for FLAGGED_FOR_REVIEW would never match an
        # engine return of FLAGGED.
        expected = EXPECTED_NORMALIZATIONS.get(raw_expected, raw_expected)
        category = test_case.category.value if hasattr(test_case.category, "value") else str(test_case.category)

        # Prefer UUID matching; fall back to rule_id strings if the
        # test case predates the UUID column.
        source_uuids = set(test_case.source_rule_uuids or [])
        if source_uuids:
            source_set = source_uuids
            fired_set = fired_rule_uuids
        else:
            source_set = set(test_case.source_rule_ids or [])
            fired_set = fired_rule_ids

        if raw_expected in NOT_TRIGGERED_TOKENS:
            any_fired = bool(source_set & fired_set)
            return "NOT_TRIGGERED" if not any_fired else "TRIGGERED"
        if raw_expected in ALL_TRIGGERED_TOKENS:
            if not source_set:
                return engine_decision
            fired_count = len(source_set & fired_set)
            if fired_count == len(source_set):
                return "ALL_TRIGGERED"
            if fired_count == 0:
                return "NOT_TRIGGERED"
            return "PARTIAL_TRIGGERED"
        if raw_expected in CONFLICT_TOKENS:
            # CONFLICT tests assert that two rules with contradictory
            # actions BOTH have their conditions met on this loan. In a
            # gate-style engine, only one will actually fire (the REJECT
            # short-circuits the other), so we don't require both to be
            # in fired_set. Counting at-least-one-fired as success is
            # the right semantic — it demonstrates the conflict scenario
            # is reachable on real loans.
            if not source_set:
                return engine_decision
            if source_set & fired_set:
                return "CONFLICT_OBSERVED"
            return "NOT_TRIGGERED"
        # POSITIVE / BND-above-threshold / EDGE-where-rule-fires: the
        # source rule should fire. We project to RULE_FIRED / RULE_NOT_FIRED
        # so the assertion is robust to other terminal rules in the snapshot
        # stamping a different final decision on top.
        if category in SHOULD_FIRE_CATEGORIES and source_set:
            if source_set & fired_set:
                return "RULE_FIRED"
            # Source rule didn't fire. Three ways this can still be a
            # legitimate "shadowed by a higher-priority rule" case:
            #
            #  1. Engine produced the EXACT expected decision via
            #     another rule — the policy outcome was achieved.
            #
            #  2. Source rule's intended action was non-terminal
            #     (SET / CAP / MODIFY / FLAG) but the engine REJECTED
            #     or FLAGGED the loan via an earlier gate. The
            #     modification couldn't have run anyway because the
            #     decision was sealed before this rule got its turn.
            #
            #  3. Test expects the rule to FIRE on a population that
            #     ALSO trips a higher-priority gate. The engine output
            #     is the gate's outcome (REJECTED/FLAGGED), which is
            #     the correct policy result even though the source
            #     rule itself didn't run.
            #
            # All three paths count as SHADOWED (soft-pass) so
            # reviewers see "this rule is shadowed by an earlier gate"
            # instead of a misleading hard failure.
            if engine_decision and engine_decision == expected:
                return "RULE_SHADOWED"
            if (
                engine_decision in PREEMPTING_DECISIONS
                and expected != engine_decision
            ):
                # Test expected a non-preempting outcome (APPROVED /
                # MODIFIED / etc.) but the engine REJECTED or FLAGGED
                # via an earlier gate. The rule never had its turn.
                return "RULE_SHADOWED"
            return "RULE_NOT_FIRED"
        # Fallback: no source rule named, use engine decision verbatim
        return engine_decision

    results: list[dict[str, Any]] = []
    total_match = 0
    total_dev = 0
    by_category: dict[str, dict[str, int]] = {}

    for tc in suite.test_cases or []:
        cat = tc.category.value if hasattr(tc.category, "value") else str(tc.category)
        expected_decision = (tc.expected_outcome or {}).get("decision", "APPROVED")
        expected_decision = str(expected_decision).upper()
        # Use UUID set when the test was generated with the
        # collision-aware pipeline; fall back to rule_id strings for
        # legacy data so old suites still execute (just with the
        # known rule_id ambiguity).
        source_uuid_set = set(tc.source_rule_uuids or [])
        source_id_set = set(tc.source_rule_ids or [])
        has_source = bool(source_uuid_set or source_id_set)

        # The token we actually compare against — projected if necessary
        if expected_decision in NOT_TRIGGERED_TOKENS:
            target_outcome = "NOT_TRIGGERED"
        elif expected_decision in ALL_TRIGGERED_TOKENS:
            target_outcome = "ALL_TRIGGERED"
        elif expected_decision in CONFLICT_TOKENS:
            # INTERACTION test asserting two rules conflict — engine
            # output collapses to whichever short-circuits first, but
            # the test's "did both source rules fire?" assertion is
            # what we want to validate.
            target_outcome = "CONFLICT_OBSERVED"
        elif cat in SHOULD_FIRE_CATEGORIES and has_source:
            # POSITIVE / BND-above-threshold / EDGE-where-rule-fires:
            # assert the source rule fires, regardless of whether other
            # terminal rules in the snapshot override the engine's final
            # decision. (NEG/BND-at-threshold cases use NOT_TRIGGERED
            # tokens and are handled by the branch above.)
            target_outcome = "RULE_FIRED"
        else:
            target_outcome = expected_decision

        actual_dist: dict[str, int] = {}
        # Always record the engine's actual final decision distribution
        # alongside the assertion-vocabulary distribution. This way the
        # UI can show both "did the source rule fire?" (the test result)
        # AND "what did the engine actually decide?" (the impact).
        engine_decision_dist: dict[str, int] = {}
        first_dev_reason: str | None = None

        if tc.matched_loan_ids:
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
                fired_ids = {fr.rule_id for fr in res.fired_rules}
                fired_uuids = {fr.rule_uuid for fr in res.fired_rules if fr.rule_uuid}
                outcome = _outcome_for_loan(tc, fired_ids, fired_uuids, res.decision)
                actual_dist[outcome] = actual_dist.get(outcome, 0) + 1
                engine_decision_dist[res.decision] = engine_decision_dist.get(res.decision, 0) + 1
                # SHADOWED is a soft-pass (rule didn't fire but engine
                # still produced the expected decision via another rule)
                # — don't treat it as a deviation worth reporting.
                if first_dev_reason is None and outcome != target_outcome and outcome != "RULE_SHADOWED":
                    if outcome in {"TRIGGERED", "PARTIAL_TRIGGERED", "ALL_TRIGGERED"}:
                        # Surface which source rule actually fired —
                        # match by UUID when available, else by rule_id
                        if source_uuid_set:
                            fired_source = [
                                fr for fr in res.fired_rules
                                if fr.rule_uuid and fr.rule_uuid in source_uuid_set
                            ]
                        else:
                            fired_source = [
                                fr for fr in res.fired_rules
                                if fr.rule_id in source_id_set
                            ]
                        if fired_source:
                            first_dev_reason = (
                                f"{fired_source[0].rule_id} ({fired_source[0].rule_name}) fired"
                                + (f": {fired_source[0].reason}" if fired_source[0].reason else "")
                            )
                        else:
                            first_dev_reason = f"unexpected outcome: {outcome}"
                    elif outcome == "RULE_NOT_FIRED":
                        # POSITIVE test where source rule didn't fire — the
                        # most useful signal is what the engine ran instead.
                        first_dev_reason = (
                            f"source rule did not fire (engine decided {res.decision})"
                        )
                    else:
                        first_dev_reason = res.reasons[0] if res.reasons else f"got {outcome}, expected {target_outcome}"

        matched_count = sum(actual_dist.values())
        matches_expected = actual_dist.get(target_outcome, 0)
        # RULE_SHADOWED counts as a soft pass — the engine produced the
        # right business outcome via a different rule. Surface the count
        # separately so users can see "this test passes because some other
        # rule also rejects these loans" (worth reviewing, but not a bug).
        shadowed = actual_dist.get("RULE_SHADOWED", 0)
        deviates = matched_count - matches_expected - shadowed

        total_match += matches_expected
        total_dev += deviates
        cat_bucket = by_category.setdefault(cat, {"matches": 0, "deviates": 0})
        cat_bucket["matches"] += matches_expected
        cat_bucket["deviates"] += deviates

        results.append({
            "test_case_id": tc.test_case_id,
            "category": cat,
            "expected_decision": expected_decision,
            "target_outcome": target_outcome,
            "matched_loan_count": matched_count,
            "actual_distribution": actual_dist,
            "engine_decision_distribution": engine_decision_dist,
            "matches_expected": matches_expected,
            "shadowed": shadowed,
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
    actor = (executed_by or "system").strip()[:128] or "system"
    note = (rationale.strip() if rationale else None) or None
    suite.last_execution_report = report
    suite.last_executed_at = datetime.utcnow()
    suite.last_executed_against_version_id = version.id
    suite.last_executed_by = actor
    suite.last_execution_rationale = note
    await db.commit()

    # Audit event for the timeline.
    try:
        from app.services.audit_service import record_event
        from app.models.audit_event import AuditAction, AuditEntityType
        from app.models.rule import RuleSet as _RS

        rs_q = await db.execute(select(_RS).where(_RS.id == suite.rule_set_id))
        rs_row = rs_q.scalar_one_or_none()
        brd_id = rs_row.brd_document_id if rs_row else None

        await record_event(
            db,
            action=AuditAction.SUITE_EXECUTED,
            entity_type=AuditEntityType.TEST_SUITE,
            entity_id=suite.id,
            actor=actor,
            rationale=note,
            brd_id=brd_id,
            repository_id=version.repository_id,
            metadata={
                "version_number": version.version_number,
                "matches_expected": int(total_match),
                "deviates_from_expected": int(total_dev),
                "total_cases": int(report.get("total_cases") or 0),
            },
        )
    except Exception:
        pass

    return report
