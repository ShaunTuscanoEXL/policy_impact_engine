"""Slice 10 — production drift watch."""
from __future__ import annotations

import pytest

from app.models.brd import BrdDocument, FileType
from app.models.loan_record import LoanRecord
from app.models.rule import Rule, RuleSet, RuleSetStatus, RuleType, Subsystem


pytestmark = pytest.mark.anyio


async def _seed_brd(db_session, name="DRIFT.docx") -> BrdDocument:
    brd = BrdDocument(
        filename=name, file_path=f"/data/{name}",
        file_type=FileType.DOCX, parsed_content="…",
    )
    db_session.add(brd)
    await db_session.commit()
    await db_session.refresh(brd)
    return brd


async def _seed_rule_set(db_session, brd, rules):
    rs = RuleSet(brd_document_id=brd.id, version=1,
                 name=f"Rules from {brd.filename}", status=RuleSetStatus.DRAFT)
    db_session.add(rs)
    await db_session.flush()
    for r in rules:
        db_session.add(Rule(
            rule_set_id=rs.id,
            rule_id=r["rule_id"], rule_name=r["rule_name"],
            rule_type=RuleType("ELIGIBILITY"),
            subsystem=Subsystem("BUREAU_GATE"),
            conditions=r["conditions"], actions=r["actions"], priority=0,
        ))
    await db_session.commit()
    await db_session.refresh(rs)
    return rs


def _us_loan(loan_id: str, fico: int) -> dict:
    return {
        "loan_application_id": loan_id, "desired_amount": 10000,
        "borrower_credit_model": {"customer_inputs": {"monthly_income": 5000},
                                  "bureau_credits": {"bureau_score": fico}},
        "calculated_attributes": {"debt_to_income_ratio": 0.3},
        "decision_context": {"risk_segment": "PRIME"},
    }


async def test_drift_endpoint_404s_when_no_production_version(client, db_session):
    """No production version → drift can't be computed."""
    # Create an empty repo via the create endpoint.
    repo = (await client.post("/api/v1/live-repo", json={
        "name": "Empty Repo", "product": "PERSONAL", "jurisdiction": "US",
    })).json()
    r = await client.get(f"/api/v1/live-repo/{repo['id']}/drift")
    assert r.status_code == 400
    assert "no production version" in r.json()["detail"].lower()


async def test_drift_returns_zero_predicted_with_warning_when_no_impact_run(client, db_session):
    """When the production version was promoted without an impact run
    on it, predicted distribution is zeros and a warning is set."""
    brd = await _seed_brd(db_session)
    await _seed_rule_set(db_session, brd, [
        {"rule_id": "R1", "rule_name": "Reject FICO<600",
         "conditions": [{"field": "bureau_score", "operator": "<", "value": 600, "logic": "AND"}],
         "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                      "value": "REJECTED", "description": "low FICO"}]},
    ])
    for i, fico in enumerate([700, 700, 580, 580]):
        db_session.add(LoanRecord(
            loan_application_id=f"L-{i}",
            request_payload=_us_loan(f"L-{i}", fico),
            response_payload={"decision_status": "APPROVED"},
        ))
    await db_session.commit()
    propose = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "product": "PERSONAL", "jurisdiction": "US",
        "auto_apply_when_empty": True, "decided_by": "auto",
    })).json()
    repo_id = propose["repository_id"]

    r = await client.get(f"/api/v1/live-repo/{repo_id}/drift")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["production_version_number"] == 1
    assert body["predicted_source"] is None
    assert any("no impact run" in w.lower() for w in body["warnings"])

    # Observed distribution should reflect the actual rule firing
    # (2 approved, 2 rejected based on FICO floor of 600).
    obs = body["observed"]["decision_distribution"]
    assert obs["APPROVED"] == 2
    assert obs["REJECTED"] == 2


async def test_drift_compares_observed_to_predicted_when_impact_run_exists(client, db_session):
    """Run an impact analysis on the production candidate, then drift
    should compare its 'candidate' distribution to the freshly-evaluated
    one. Identical loan corpus = zero drift."""
    brd = await _seed_brd(db_session, "DRIFT2.docx")
    await _seed_rule_set(db_session, brd, [
        {"rule_id": "R1", "rule_name": "Reject FICO<650",
         "conditions": [{"field": "bureau_score", "operator": "<", "value": 650, "logic": "AND"}],
         "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                      "value": "REJECTED", "description": "x"}]},
    ])
    for i, fico in enumerate([700, 700, 600, 600, 600]):
        db_session.add(LoanRecord(
            loan_application_id=f"L-{i}",
            request_payload=_us_loan(f"L-{i}", fico),
            response_payload={"decision_status": "APPROVED"},
        ))
    await db_session.commit()
    propose = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "product": "PERSONAL", "jurisdiction": "US",
        "auto_apply_when_empty": True, "decided_by": "auto",
    })).json()
    repo_id = propose["repository_id"]
    v1 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/1")).json()

    # Run an impact analysis on v1 vs empty baseline → predicted dist
    # should match observed exactly.
    await client.post("/api/v1/impact-run", json={
        "repository_id": repo_id,
        "candidate_version_id": v1["id"],
    })

    r = await client.get(f"/api/v1/live-repo/{repo_id}/drift")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["predicted_source"] is not None
    assert body["predicted_source"]["loan_count"] == 5

    # Identical corpus → drift should be near zero on every label
    drift_dist = body["drift"]["decision_distribution"]
    for label, info in drift_dist.items():
        assert abs(info["delta_pct"]) < 0.01, (label, info)
    assert body["drift"]["max_abs_delta_pct"] < 0.01


async def test_drift_warning_when_loan_corpus_is_empty(client, db_session):
    """Edge case: the corpus got purged. Drift should still return
    200 with empty observed + a warning string."""
    brd = await _seed_brd(db_session, "DRIFT3.docx")
    await _seed_rule_set(db_session, brd, [
        {"rule_id": "R1", "rule_name": "x",
         "conditions": [{"field": "bureau_score", "operator": "<", "value": 600, "logic": "AND"}],
         "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                      "value": "REJECTED", "description": "x"}]},
    ])
    # Seed at least one loan so propose-from-brd's auto-baseline has
    # something to promote against; we'll delete it before drift runs.
    db_session.add(LoanRecord(
        loan_application_id="L-tmp",
        request_payload=_us_loan("L-tmp", 700),
        response_payload={"decision_status": "APPROVED"},
    ))
    await db_session.commit()
    propose = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "product": "PERSONAL", "jurisdiction": "US",
        "auto_apply_when_empty": True, "decided_by": "auto",
    })).json()
    repo_id = propose["repository_id"]

    # Wipe the corpus
    from sqlalchemy import delete
    await db_session.execute(delete(LoanRecord))
    await db_session.commit()

    r = await client.get(f"/api/v1/live-repo/{repo_id}/drift")
    assert r.status_code == 200
    body = r.json()
    assert body["observed"]["loan_count"] == 0
    assert any("no loan records" in w.lower() for w in body["warnings"])
