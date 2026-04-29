"""Slice 2 — impact runner end-to-end tests.

Covers:
  - Pure-Python rule engine: REJECT, FLAG, CAP, MODIFY, AND/OR chains, between
  - In-memory impact summary structure
  - Full DB round trip: build two repository versions, seed loan_records,
    run impact via API, verify summary distribution + flips + by_segment
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.brd import BrdDocument, FileType
from app.models.loan_record import LoanRecord
from app.models.rule import Rule, RuleSet, RuleSetStatus, RuleType, Subsystem
from app.runtime.rule_engine import (
    LoanContext,
    evaluate_snapshot,
)
from app.services import live_repo_service as svc
from app.services.impact_service import evaluate_pair_in_memory


pytestmark = pytest.mark.anyio


# ── Synthetic loan factory ───────────────────────────────────────────────

def _loan(loan_id: str, *, fico: int, dti: float, monthly_income: float,
          desired_amount: float, risk_segment: str = "PRIME") -> dict:
    """Produce a request_payload that matches the seed_loan_records.py shape."""
    return {
        "loan_application_id": loan_id,
        "application_type": "DIGITAL",
        "repeat_type": "FIRST_TIME",
        "credit_policy": "PERSONAL",
        "desired_amount": desired_amount,
        "borrower_credit_model": {
            "customer_inputs": {
                "monthly_income": monthly_income,
                "annual_income": monthly_income * 12,
            },
            "banking_inputs": {},
            "bureau_credits": {
                "bureau_score": fico,
                "inquiries_last_3m": 1,
            },
        },
        "calculated_attributes": {
            "debt_to_income_ratio": dti,
            "scores": {
                "g5": {"score": 0.75},
                "g6": {"score": 0.7},
            },
        },
        "decision_context": {
            "risk_segment": risk_segment,
        },
    }


def _rule_dict(rid, name, field, op, val, *, action="REJECT", target="decision_status",
               desc="x", subsystem="UNCLASSIFIED", priority=0):
    return {
        "id": rid, "rule_id": rid, "rule_name": name,
        "subsystem": subsystem, "priority": priority,
        "canonical_key": f"{subsystem}::{field}::{op.upper().replace('>','GT').replace('<','LT')}::{action}",
        "conditions": [{"field": field, "operator": op, "value": val, "logic": "AND"}],
        "actions": [{"action_type": action, "target_field": target,
                     "value": "REJECTED", "description": desc}],
    }


# ── LoanContext + field_registry resolution ──────────────────────────────

def test_loan_context_resolves_registered_fields():
    payload = _loan("L1", fico=720, dti=0.25, monthly_income=6500, desired_amount=20000)
    ctx = LoanContext(payload, loan_application_id="L1")
    assert ctx["bureau_score"] == 720
    assert ctx["dti_ratio"] == 0.25
    assert ctx["monthly_income"] == 6500
    assert ctx["desired_amount"] == 20000
    assert ctx["g5_score"] == 0.75
    # Unknown field → None
    assert ctx.get("nonexistent_field") is None


# ── Rule engine: action types ────────────────────────────────────────────

def test_engine_rejects_when_gate_fires():
    snapshot = [
        _rule_dict("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.43,
                   subsystem="DTI_GATE", priority=90, desc="HIGH_DTI"),
    ]
    payload = _loan("L1", fico=720, dti=0.50, monthly_income=6000, desired_amount=15000)
    res = evaluate_snapshot(snapshot, payload)
    assert res.decision == "REJECTED"
    assert res.terminal_rule_id == "R-DTI-001"
    assert res.reasons == ["HIGH_DTI"]


def test_engine_approves_when_no_gate_fires():
    snapshot = [
        _rule_dict("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.43,
                   subsystem="DTI_GATE", priority=90),
    ]
    payload = _loan("L2", fico=720, dti=0.25, monthly_income=6000, desired_amount=15000)
    res = evaluate_snapshot(snapshot, payload)
    assert res.decision == "APPROVED"
    assert res.terminal_rule_id is None
    assert res.fired_rules == []


def test_engine_flags_when_only_flag_fires():
    snapshot = [
        _rule_dict("R-INQ-FLAG", "Inquiry warn", "inquiries_last_3m", ">", 0,
                   subsystem="BUREAU_GATE", priority=80,
                   action="FLAG", target="manual_review", desc="HUNGRY"),
    ]
    payload = _loan("L3", fico=720, dti=0.20, monthly_income=6000, desired_amount=15000)
    res = evaluate_snapshot(snapshot, payload)
    assert res.decision == "FLAGGED"
    assert res.reasons == ["HUNGRY"]


def test_engine_evaluates_subsystems_in_canonical_order():
    """A REJECT in BUREAU_GATE terminates before PRICING_TIER ever runs."""
    snapshot = [
        # PRICING runs after gates — would set rate but never gets there
        {"id": "R-PRC", "rule_id": "R-PRC", "rule_name": "Pricing",
         "subsystem": "PRICING_TIER", "priority": 50,
         "conditions": [{"field": "bureau_score", "operator": "between", "value": [700, 850]}],
         "actions": [{"action_type": "SET", "target_field": "interest_rate",
                      "value": 0.10, "description": "TIER_2"}]},
        {"id": "R-BUR", "rule_id": "R-BUR", "rule_name": "FICO floor",
         "subsystem": "BUREAU_GATE", "priority": 100,
         "conditions": [{"field": "bureau_score", "operator": "<", "value": 720}],
         "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                      "value": "REJECTED", "description": "SUBPRIME_FICO"}]},
    ]
    payload = _loan("L4", fico=700, dti=0.20, monthly_income=6000, desired_amount=15000)
    res = evaluate_snapshot(snapshot, payload)
    assert res.decision == "REJECTED"
    assert res.terminal_rule_id == "R-BUR"
    # PRICING should NOT have fired because BUREAU_GATE rejected first
    fired_ids = {f.rule_id for f in res.fired_rules}
    assert "R-PRC" not in fired_ids


def test_engine_or_logic_chain():
    snapshot = [{
        "id": "R", "rule_id": "R", "rule_name": "Either gate",
        "subsystem": "BUREAU_GATE", "priority": 90,
        "conditions": [
            {"field": "bureau_score", "operator": "<", "value": 600, "logic": "OR"},
            {"field": "dti_ratio",    "operator": ">", "value": 0.55, "logic": "AND"},
        ],
        "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                     "value": "REJECTED", "description": "OR_GATE"}],
    }]
    # Triggers via DTI even though bureau is fine
    res = evaluate_snapshot(snapshot, _loan("L", fico=720, dti=0.60, monthly_income=6000, desired_amount=15000))
    assert res.decision == "REJECTED"
    # Triggers via bureau even though DTI is fine
    res = evaluate_snapshot(snapshot, _loan("L", fico=580, dti=0.20, monthly_income=6000, desired_amount=15000))
    assert res.decision == "REJECTED"
    # Neither triggers → APPROVED
    res = evaluate_snapshot(snapshot, _loan("L", fico=720, dti=0.20, monthly_income=6000, desired_amount=15000))
    assert res.decision == "APPROVED"


def test_engine_between_operator():
    snapshot = [{
        "id": "R-PRC", "rule_id": "R-PRC", "rule_name": "Tier 2",
        "subsystem": "PRICING_TIER", "priority": 50,
        "conditions": [{"field": "bureau_score", "operator": "between", "value": [720, 769]}],
        "actions": [{"action_type": "SET", "target_field": "interest_rate",
                     "value": 0.1199, "description": "TIER_2_RATE"}],
    }]
    res = evaluate_snapshot(snapshot, _loan("L", fico=750, dti=0.25, monthly_income=6000, desired_amount=15000))
    assert res.decision == "APPROVED"  # SET on amount/rate is not terminal
    assert res.amount_caps == [0.1199]


# ── In-memory impact summary ─────────────────────────────────────────────

def test_evaluate_pair_in_memory_basic_summary():
    """Compare a loose baseline (DTI > 0.50) to a tighter candidate
    (DTI > 0.35). With FICO 720 across the board, dropping DTI cap from
    0.50 to 0.35 should flip several APPROVED -> REJECTED."""
    base = [_rule_dict("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.50,
                       subsystem="DTI_GATE", priority=90)]
    candidate = [_rule_dict("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.35,
                            subsystem="DTI_GATE", priority=90)]
    loans = [
        _loan("L1", fico=750, dti=0.20, monthly_income=6000, desired_amount=15000, risk_segment="PRIME"),
        _loan("L2", fico=750, dti=0.40, monthly_income=6000, desired_amount=15000, risk_segment="PRIME"),
        _loan("L3", fico=750, dti=0.45, monthly_income=6000, desired_amount=15000, risk_segment="PRIME"),
        _loan("L4", fico=750, dti=0.55, monthly_income=6000, desired_amount=15000, risk_segment="NEAR_PRIME"),
    ]
    summary = evaluate_pair_in_memory(base, candidate, loans)
    assert summary["total_loans"] == 4
    # Baseline rejects only L4 (dti=0.55 > 0.50)
    assert summary["decision_distribution"]["base"]["REJECTED"] == 1
    assert summary["decision_distribution"]["base"]["APPROVED"] == 3
    # Candidate rejects L2, L3, L4 (dti > 0.35)
    assert summary["decision_distribution"]["candidate"]["REJECTED"] == 3
    assert summary["decision_distribution"]["candidate"]["APPROVED"] == 1
    # Two flips: L2 and L3 went APPROVED -> REJECTED
    assert summary["decision_flips"]["approved_to_rejected"] == 2
    # By-segment: PRIME approval rate went from 3/3 to 1/3 (-0.6667)
    prime = summary["by_segment"]["PRIME"]
    assert prime["loans"] == 3
    assert prime["base_approval_rate"] == 1.0
    assert prime["candidate_approval_rate"] == round(1/3, 4)
    assert prime["approval_rate_change"] == round(1/3 - 1.0, 4)
    # Subsystem attribution: all flips should be attributed to DTI_GATE
    assert summary["by_subsystem"]["DTI_GATE"]["flips_caused"] == 2


# ── Full DB round trip via API ───────────────────────────────────────────

async def _seed_brd_and_apply(client, db_session, *, rules: list[dict],
                              brd_name: str, decided_by: str = "test"):
    """Helper: seed a BRD + rule_set then apply via propose-from-brd."""
    brd = BrdDocument(filename=brd_name, file_path=f"/data/{brd_name}",
                      file_type=FileType.DOCX, parsed_content="…")
    db_session.add(brd)
    await db_session.commit()
    await db_session.refresh(brd)

    rs = RuleSet(brd_document_id=brd.id, version=1, name=brd_name,
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

    return (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "decided_by": decided_by,
    })).json()


async def _seed_loans(db_session, loans: list[dict]):
    for i, payload in enumerate(loans):
        db_session.add(LoanRecord(
            loan_application_id=payload["loan_application_id"],
            request_payload=payload,
            response_payload={"decision_status": "APPROVED"},
        ))
    await db_session.commit()


def _r(rid, field, op, val, *, action="REJECT", subsystem="UNCLASSIFIED",
       priority=0, target="decision_status", desc="x"):
    return {
        "rule_id": rid, "rule_name": rid, "subsystem": subsystem,
        "priority": priority,
        "conditions": [{"field": field, "operator": op, "value": val, "logic": "AND"}],
        "actions": [{"action_type": action, "target_field": target,
                     "value": "REJECTED", "description": desc}],
    }


async def test_impact_run_full_db_round_trip(client, db_session):
    """End-to-end: baseline a repo with a loose DTI cap, apply a tighter
    DTI cap as v2, then run an impact_run comparing v1 vs v2 against
    seeded loan records. Expect APPROVED -> REJECTED flips."""
    # Baseline (v1): loose DTI cap > 0.50
    baseline = await _seed_brd_and_apply(client, db_session,
        rules=[_r("R-DTI-001", "dti_ratio", ">", 0.50,
                  subsystem="DTI_GATE", priority=90, desc="HIGH_DTI")],
        brd_name="BRD-baseline.docx")
    repo_id = baseline["repository_id"]

    # Tightened (v2): DTI > 0.35
    second = await _seed_brd_and_apply(client, db_session,
        rules=[_r("R-DTI-001-tight", "dti_ratio", ">", 0.35,
                  subsystem="DTI_GATE", priority=90, desc="HIGH_DTI")],
        brd_name="BRD-tight.docx")
    assert second["auto_applied"] is False  # repo already has rules
    # Apply the proposal manually
    apply_resp = (await client.post(
        f"/api/v1/merge-proposal/{second['proposal_id']}/apply",
        json={"decided_by": "vishnu"},
    )).json()
    assert apply_resp["applied"] is True
    new_v_number = apply_resp["new_version_number"]
    assert new_v_number == 2

    # Look up the version uuid for both versions
    v1 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/1")).json()
    v2 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/2")).json()
    base_version_id = v1["id"]
    cand_version_id = v2["id"]

    # Seed 4 loan records
    await _seed_loans(db_session, [
        _loan("LA-00000001", fico=750, dti=0.20, monthly_income=6000, desired_amount=15000, risk_segment="PRIME"),
        _loan("LA-00000002", fico=750, dti=0.40, monthly_income=6000, desired_amount=15000, risk_segment="PRIME"),
        _loan("LA-00000003", fico=750, dti=0.45, monthly_income=6000, desired_amount=15000, risk_segment="PRIME"),
        _loan("LA-00000004", fico=750, dti=0.55, monthly_income=6000, desired_amount=15000, risk_segment="NEAR_PRIME"),
    ])

    # Kick off the impact run
    r = await client.post("/api/v1/impact-run", json={
        "repository_id": repo_id,
        "base_version_id": base_version_id,
        "candidate_version_id": cand_version_id,
        "created_by": "vishnu",
    })
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "COMPLETED"
    summary = run["summary"]
    assert summary["total_loans"] == 4

    # Baseline distribution: only LA-4 rejected (dti=0.55 > 0.50)
    base_dist = summary["decision_distribution"]["base"]
    cand_dist = summary["decision_distribution"]["candidate"]
    assert base_dist["REJECTED"] == 1
    assert base_dist["APPROVED"] == 3
    # Candidate distribution: LA-2, LA-3, LA-4 rejected (dti > 0.35)
    assert cand_dist["REJECTED"] == 3
    assert cand_dist["APPROVED"] == 1

    # 2 flips APPROVED -> REJECTED (LA-2, LA-3)
    assert summary["decision_flips"]["approved_to_rejected"] == 2
    # PRIME segment took the hit
    assert summary["by_segment"]["PRIME"]["loans"] == 3
    assert summary["by_segment"]["PRIME"]["base_approval_rate"] == 1.0
    assert round(summary["by_segment"]["PRIME"]["candidate_approval_rate"], 4) == round(1/3, 4)
    # Attribution to DTI_GATE
    assert summary["by_subsystem"]["DTI_GATE"]["flips_caused"] == 2

    # GET single run echoes back
    one = (await client.get(f"/api/v1/impact-run/{run['id']}")).json()
    assert one["status"] == "COMPLETED"
    assert one["summary"]["total_loans"] == 4

    # LIST runs by repo
    listing = (await client.get(f"/api/v1/impact-run?repository_id={repo_id}")).json()
    assert len(listing) == 1
    assert listing[0]["id"] == run["id"]


async def test_impact_run_against_empty_baseline(client, db_session):
    """base_version_id=None should produce an empty baseline (every
    loan APPROVED), so all candidate REJECTs become flips."""
    baseline = await _seed_brd_and_apply(client, db_session,
        rules=[_r("R-DTI-001", "dti_ratio", ">", 0.30,
                  subsystem="DTI_GATE", priority=90, desc="HIGH_DTI")],
        brd_name="BRD-only.docx")
    repo_id = baseline["repository_id"]
    v1 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/1")).json()

    await _seed_loans(db_session, [
        _loan("LA-100", fico=750, dti=0.20, monthly_income=6000, desired_amount=15000),
        _loan("LA-101", fico=750, dti=0.45, monthly_income=6000, desired_amount=15000),
    ])

    r = await client.post("/api/v1/impact-run", json={
        "repository_id": repo_id,
        "base_version_id": None,
        "candidate_version_id": v1["id"],
    })
    assert r.status_code == 201, r.text
    summary = r.json()["summary"]
    assert summary["decision_distribution"]["base"]["APPROVED"] == 2
    assert summary["decision_distribution"]["candidate"]["REJECTED"] == 1
    assert summary["decision_flips"]["approved_to_rejected"] == 1
