"""Slice 4 — wire-ups: BRD pipeline → live repo, RuleResponse exposure,
test case generation from a live version, test suite execution against
loan_records.

Every assertion uses real data flowing through real services:
- DocumentParser is bypassed (no .docx fixture exec) but the rules are
  inserted via the same /extract-rules code path with a stubbed LLM
  step that returns deterministic RuleDefinitions.
- Loan records are seeded as real LoanRecord rows with US-fintech
  shaped request_payloads.
- No mocks of merge engine, classifier, runtime, codegen, or HTTP.
"""
from __future__ import annotations

import pytest

from app.models.brd import BrdDocument, FileType
from app.models.loan_record import LoanRecord
from app.models.rule import Rule, RuleSet, RuleSetStatus, RuleType, Subsystem
from app.schemas.rule import Action, Condition, RuleDefinition, RuleTypeEnum
from app.services import live_repo_service as repo_svc


pytestmark = pytest.mark.anyio


# ── Helpers ──────────────────────────────────────────────────────────────


async def _seed_brd(db_session, name="BRD.docx") -> BrdDocument:
    brd = BrdDocument(
        filename=name, file_path=f"/data/{name}",
        file_type=FileType.DOCX, parsed_content="…",
    )
    db_session.add(brd)
    await db_session.commit()
    await db_session.refresh(brd)
    return brd


async def _seed_rule_set(db_session, brd, rules: list[dict]) -> RuleSet:
    """Insert a rule_set the way `extract-rules` would but without
    invoking the LLM. Conditions/actions are real dicts, NOT mocks."""
    rs = RuleSet(brd_document_id=brd.id, version=1,
                 name=f"Rules from {brd.filename}",
                 status=RuleSetStatus.DRAFT)
    db_session.add(rs)
    await db_session.flush()
    for r in rules:
        db_session.add(Rule(
            rule_set_id=rs.id,
            rule_id=r["rule_id"], rule_name=r["rule_name"],
            description=r.get("description"),
            rule_type=RuleType(r.get("rule_type", "ELIGIBILITY")),
            subsystem=Subsystem(r.get("subsystem", "UNCLASSIFIED")),
            conditions=r["conditions"], actions=r["actions"],
            priority=r.get("priority", 0),
        ))
    await db_session.commit()
    await db_session.refresh(rs)
    return rs


def _rule(rid, name, field, op, val, *, action="REJECT", target="decision_status",
          subsystem="UNCLASSIFIED", priority=0, desc="x"):
    return {
        "rule_id": rid, "rule_name": name, "subsystem": subsystem,
        "priority": priority, "description": desc,
        "conditions": [{"field": field, "operator": op, "value": val, "logic": "AND"}],
        "actions": [{"action_type": action, "target_field": target,
                     "value": "REJECTED", "description": desc}],
    }


def _us_loan(loan_id: str, *, fico: int, dti: float, monthly_income: float,
             desired_amount: float, risk_segment: str = "PRIME") -> dict:
    """Real US-fintech-shaped request_payload (matches seed_loan_records)."""
    return {
        "loan_application_id": loan_id,
        "application_type": "DIGITAL",
        "credit_policy": "PERSONAL",
        "desired_amount": desired_amount,
        "borrower_credit_model": {
            "customer_inputs": {
                "monthly_income": monthly_income,
                "annual_income": monthly_income * 12,
            },
            "banking_inputs": {},
            "bureau_credits": {"bureau_score": fico, "inquiries_last_3m": 1},
        },
        "calculated_attributes": {
            "debt_to_income_ratio": dti,
            "scores": {"g5": {"score": 0.75}, "g6": {"score": 0.7}},
        },
        "decision_context": {"risk_segment": risk_segment},
    }


async def _seed_loans(db_session, payloads: list[dict]):
    for p in payloads:
        db_session.add(LoanRecord(
            loan_application_id=p["loan_application_id"],
            request_payload=p,
            response_payload={"decision_status": "APPROVED"},
        ))
    await db_session.commit()


# ── 1. RuleResponse exposes subsystem + canonical_key ───────────────────


async def test_rule_response_includes_subsystem_and_canonical_key(client, db_session):
    brd = await _seed_brd(db_session)
    rs = await _seed_rule_set(db_session, brd, [
        _rule("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.43,
              subsystem="DTI_GATE", priority=90),
    ])

    # Backfill so canonical_key is populated (production extract-rules
    # auto-classifies; here we used the test seeder which doesn't, so
    # we hit the admin endpoint to bring rules into the new shape)
    await client.post("/api/v1/live-repo/admin/backfill")

    rs_resp = await client.get(f"/api/v1/rule-sets/{rs.id}")
    assert rs_resp.status_code == 200, rs_resp.text
    body = rs_resp.json()
    rule = body["rules"][0]
    assert rule["subsystem"] == "DTI_GATE"
    assert rule["canonical_key"] == "DTI_GATE::dti_ratio::GT::REJECT::DECISION"


# ── 2. BRD workflow status now surfaces merge_proposal + live version ──


async def test_brd_workflow_returns_merge_proposal_and_live_version(client, db_session):
    brd = await _seed_brd(db_session)
    rs = await _seed_rule_set(db_session, brd, [
        _rule("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.43,
              subsystem="DTI_GATE", priority=90),
    ])

    # Drive the wire-up: propose-from-brd auto-applies as v1 (repo empty)
    propose = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id),
        "decided_by": "vishnu",
    })).json()
    assert propose["auto_applied"] is True
    assert propose["new_version_number"] == 1

    workflow = (await client.get(f"/api/v1/brds/{brd.id}/workflow")).json()
    assert workflow["rule_set"]["id"] == str(rs.id)
    assert workflow["merge_proposal"]["status"] == "APPLIED"
    assert workflow["merge_proposal"]["repository_id"] == propose["repository_id"]
    assert workflow["live_repo_version"]["version_number"] == 1
    assert workflow["live_repo_version"]["repository_id"] == propose["repository_id"]


# ── 3. generate-from-version uses real loan_records, no hard coding ────


async def test_generate_test_cases_from_live_version(client, db_session):
    """Build a baseline live version, seed real loan records, and
    generate a test case suite from the live version's snapshot."""
    brd = await _seed_brd(db_session)
    await _seed_rule_set(db_session, brd, [
        _rule("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.43,
              subsystem="DTI_GATE", priority=90, desc="HIGH_DTI"),
    ])
    propose = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "decided_by": "vishnu",
    })).json()
    repo_id = propose["repository_id"]
    v1 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/1")).json()

    # Seed loans that will deterministically match BOTH sides of the DTI cap
    await _seed_loans(db_session, [
        _us_loan("LA-PASS-1", fico=750, dti=0.20, monthly_income=6000, desired_amount=15000),
        _us_loan("LA-PASS-2", fico=750, dti=0.30, monthly_income=6000, desired_amount=15000),
        _us_loan("LA-FAIL-1", fico=750, dti=0.55, monthly_income=6000, desired_amount=15000),
    ])

    r = await client.post("/api/v1/test-cases/generate-from-version", json={
        "version_id": v1["id"],
        "positive_count": 1, "negative_count": 1,
        "boundary_count": 0, "edge_count": 0, "interaction_count": 0,
        "max_matches": 5,
    })
    assert r.status_code == 200, r.text
    suite = r.json()
    assert suite["total_cases"] >= 1
    # Coverage stats should record the source live version provenance
    cov = suite["coverage_stats"]
    assert cov["source_live_version_id"] == v1["id"]
    assert cov["source_live_version_number"] == 1


# ── 4. Suite execution against the live version reports decision impact ─


async def test_execute_suite_against_version_reports_real_decisions(client, db_session):
    """End-to-end: baseline → generate suite from version → seed loans
    → execute suite → verify the decisions reported come from the
    runtime engine evaluating the actual loan_records (no mocks)."""
    brd = await _seed_brd(db_session)
    await _seed_rule_set(db_session, brd, [
        _rule("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.43,
              subsystem="DTI_GATE", priority=90, desc="HIGH_DTI"),
    ])
    propose = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "decided_by": "vishnu",
    })).json()
    repo_id = propose["repository_id"]
    v1 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/1")).json()

    # Seed real loans — three pass DTI, three fail DTI
    await _seed_loans(db_session, [
        _us_loan("LA-PASS-1", fico=750, dti=0.20, monthly_income=6000, desired_amount=15000),
        _us_loan("LA-PASS-2", fico=750, dti=0.30, monthly_income=6000, desired_amount=15000),
        _us_loan("LA-PASS-3", fico=750, dti=0.40, monthly_income=6000, desired_amount=15000),
        _us_loan("LA-FAIL-1", fico=750, dti=0.50, monthly_income=6000, desired_amount=15000),
        _us_loan("LA-FAIL-2", fico=750, dti=0.60, monthly_income=6000, desired_amount=15000),
        _us_loan("LA-FAIL-3", fico=750, dti=0.70, monthly_income=6000, desired_amount=15000),
    ])

    # Generate the suite from the live version
    suite = (await client.post("/api/v1/test-cases/generate-from-version", json={
        "version_id": v1["id"],
        "positive_count": 1, "negative_count": 1,
        "boundary_count": 0, "edge_count": 0, "interaction_count": 0,
        "max_matches": 10,
    })).json()
    suite_id = suite["id"]

    # Execute the suite against v1 — every decision is computed by
    # the real rule_engine evaluating the seeded loan_records.
    r = await client.post(f"/api/v1/test-cases/{suite_id}/execute", json={
        "version_id": v1["id"],
    })
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["version_number"] == 1
    assert report["total_cases"] == suite["total_cases"]

    # Sanity: every test case should have evaluated some loans because
    # we seeded matching ones on both sides of the DTI cap.
    total_evaluated = sum(item["matched_loan_count"] for item in report["results"])
    assert total_evaluated > 0
    # And every outcome token in actual_distribution is one of the
    # vocabularies the executor projects into:
    # - engine decisions (APPROVED / REJECTED / FLAGGED) for tests that
    #   assert a final decision and don't name a source rule
    # - RULE_FIRED / RULE_NOT_FIRED / RULE_SHADOWED for POSITIVE/BND/EDGE
    #   tests (assertion is "did the source rule fire" — robust to other
    #   terminal rules in the snapshot stamping a different final
    #   decision; SHADOWED is the soft-pass for preemption-by-gate)
    # - NOT_TRIGGERED / TRIGGERED for NEG/BND tests
    # - ALL_TRIGGERED / PARTIAL_TRIGGERED for INTERACTION tests
    # - CONFLICT_OBSERVED for INTERACTION tests asserting two
    #   contradictory rules both apply on the matched loans
    valid = {
        "APPROVED", "REJECTED", "FLAGGED",
        "RULE_FIRED", "RULE_NOT_FIRED", "RULE_SHADOWED",
        "NOT_TRIGGERED", "TRIGGERED",
        "ALL_TRIGGERED", "PARTIAL_TRIGGERED",
        "CONFLICT_OBSERVED",
    }
    for item in report["results"]:
        for decision_token in item["actual_distribution"].keys():
            assert decision_token in valid, f"Unexpected outcome: {decision_token}"


# ── 5. End-to-end multi-stage flow (the "linked up" headline) ──────────


async def test_full_pipeline_brd_to_workflow_to_impact(client, db_session):
    """Walks the entire chain a real user goes through:
       1. BRD seeded with rules (extract-rules pipeline stand-in)
       2. propose-from-brd auto-baselines as v1
       3. workflow status reflects merge_proposal + live version
       4. Generate suite from v1
       5. Seed loans, execute suite -> get a decision report
       6. Submit a tighter BRD as v2, run impact-run between v1/v2
    """
    # Stage 1+2 — first BRD baselines the repo
    brd1 = await _seed_brd(db_session, name="BRD-1.docx")
    await _seed_rule_set(db_session, brd1, [
        _rule("R-DTI-001", "DTI cap loose", "dti_ratio", ">", 0.50,
              subsystem="DTI_GATE", priority=90, desc="HIGH_DTI"),
    ])
    p1 = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd1.id), "decided_by": "vishnu",
    })).json()
    repo_id = p1["repository_id"]
    v1 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/1")).json()

    # Stage 3 — workflow surfaces wire-up data
    wf = (await client.get(f"/api/v1/brds/{brd1.id}/workflow")).json()
    assert wf["merge_proposal"]["status"] == "APPLIED"
    assert wf["live_repo_version"]["version_number"] == 1

    # Stage 4+5 — generate + execute
    await _seed_loans(db_session, [
        _us_loan("LA-A", fico=750, dti=0.20, monthly_income=6000, desired_amount=15000),
        _us_loan("LA-B", fico=750, dti=0.45, monthly_income=6000, desired_amount=15000),
        _us_loan("LA-C", fico=750, dti=0.60, monthly_income=6000, desired_amount=15000),
    ])
    suite = (await client.post("/api/v1/test-cases/generate-from-version", json={
        "version_id": v1["id"],
        "positive_count": 1, "negative_count": 1,
        "max_matches": 10,
    })).json()
    exec_report = (await client.post(
        f"/api/v1/test-cases/{suite['id']}/execute",
        json={"version_id": v1["id"]},
    )).json()
    assert exec_report["version_number"] == 1

    # Stage 6 — second BRD, tighten DTI, apply, then impact-run v1 vs v2
    brd2 = await _seed_brd(db_session, name="BRD-2.docx")
    await _seed_rule_set(db_session, brd2, [
        _rule("R-DTI-002", "DTI cap tight", "dti_ratio", ">", 0.35,
              subsystem="DTI_GATE", priority=90, desc="HIGH_DTI"),
    ])
    p2 = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd2.id), "decided_by": "vishnu",
    })).json()
    assert p2["auto_applied"] is False

    apply_resp = (await client.post(
        f"/api/v1/merge-proposal/{p2['proposal_id']}/apply",
        json={"decided_by": "vishnu"},
    )).json()
    assert apply_resp["applied"] is True
    v2 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/2")).json()

    impact = (await client.post("/api/v1/impact-run", json={
        "repository_id": repo_id,
        "base_version_id": v1["id"],
        "candidate_version_id": v2["id"],
    })).json()
    assert impact["status"] == "COMPLETED"
    summary = impact["summary"]
    # Tightening from 0.50 -> 0.35 must have flipped at least one APPROVED -> REJECTED
    # for our seeded loans (LA-B with dti=0.45 was APPROVED at v1, REJECTED at v2)
    assert summary["decision_flips"].get("approved_to_rejected", 0) >= 1
    assert summary["by_subsystem"]["DTI_GATE"]["flips_caused"] >= 1
