"""Slice 2 — business-friendly impact summary.

Validates that `_summarize` (and the public `evaluate_pair_in_memory`
shim) emit the new `business_summary` block with approval-rate delta,
direction-aware flip counts, and projected USD exposure change. The
math is asserted against tiny hand-rolled scenarios so a future
refactor can't silently shift the numbers.
"""
from __future__ import annotations

import pytest

from app.services.impact_service import evaluate_pair_in_memory


pytestmark = pytest.mark.anyio


def _loan(loan_id: str, fico: int, dti: float, amount: float, segment: str = "PRIME") -> dict:
    return {
        "loan_application_id": loan_id,
        "desired_amount": amount,
        "borrower_credit_model": {
            "customer_inputs": {"monthly_income": 8000},
            "bureau_credits": {"bureau_score": fico},
        },
        "calculated_attributes": {"debt_to_income_ratio": dti},
        "decision_context": {"risk_segment": segment},
    }


def _reject_below_fico(threshold: int) -> dict:
    return {
        "id": f"rule-fico-{threshold}",
        "rule_id": "FICO-FLOOR",
        "rule_name": f"Reject FICO < {threshold}",
        "rule_type": "ELIGIBILITY",
        "subsystem": "BUREAU_GATE",
        "canonical_key": f"BUREAU_GATE::bureau_score::lt::REJECT::{threshold}",
        "conditions": [{"field": "bureau_score", "operator": "<", "value": threshold, "logic": "AND"}],
        "actions": [{"action_type": "REJECT", "target_field": "decision_status", "value": "REJECTED", "description": "low FICO"}],
        "priority": 0, "confidence": 1.0,
    }


def test_business_summary_present_with_expected_keys():
    """Schema contract: every key the UI binds to must be present even
    on a no-flip run, so the empty-state path doesn't crash."""
    base = []  # no-op base ⇒ everything APPROVED
    cand = [_reject_below_fico(620)]
    loans = [_loan("L1", fico=700, dti=0.25, amount=10000)]

    summary = evaluate_pair_in_memory(base, cand, loans)
    bs = summary["business_summary"]
    expected_keys = {
        "base_approval_rate",
        "candidate_approval_rate",
        "approval_rate_delta",
        "loans_newly_denied",
        "loans_newly_approved",
        "net_funded_loans_change",
        "base_funded_amount_usd",
        "candidate_funded_amount_usd",
        "exposure_change_loss_usd",
        "exposure_change_gain_usd",
        "net_exposure_change_usd",
        "top_changed_segment",
    }
    assert expected_keys.issubset(set(bs.keys())), bs.keys()


def test_tightening_rule_records_loss_in_exposure():
    """Adding a stricter FICO floor on the candidate side should:
       - flip 2 of 5 loans from APPROVED → REJECTED
       - record loans_newly_denied=2, loans_newly_approved=0
       - record exposure_change_loss_usd = 10k + 5k (the rejected ones)
       - approval_rate_delta = -0.40 (from 1.0 → 0.6)
       - net_exposure_change_usd reflects the loss as negative
    """
    base = []  # all APPROVED
    cand = [_reject_below_fico(650)]
    loans = [
        _loan("L1", fico=700, dti=0.25, amount=20000),  # passes
        _loan("L2", fico=680, dti=0.25, amount=15000),  # passes
        _loan("L3", fico=660, dti=0.25, amount=8000),   # passes
        _loan("L4", fico=620, dti=0.25, amount=10000),  # FAILS
        _loan("L5", fico=600, dti=0.25, amount=5000),   # FAILS
    ]
    summary = evaluate_pair_in_memory(base, cand, loans)
    bs = summary["business_summary"]

    assert bs["loans_newly_denied"] == 2
    assert bs["loans_newly_approved"] == 0
    assert bs["net_funded_loans_change"] == -2
    assert bs["exposure_change_loss_usd"] == pytest.approx(15000.0)
    assert bs["exposure_change_gain_usd"] == pytest.approx(0.0)
    assert bs["approval_rate_delta"] == pytest.approx(-0.40, abs=0.01)
    # base = 5 funded * average, candidate = 3 funded
    assert bs["base_funded_amount_usd"] == pytest.approx(58000.0)
    assert bs["candidate_funded_amount_usd"] == pytest.approx(43000.0)
    assert bs["net_exposure_change_usd"] == pytest.approx(-15000.0)


def test_loosening_rule_records_gain_when_candidate_approves_more():
    """Going the OTHER direction — base rejects, candidate approves —
    should record loans_newly_approved + exposure_change_gain_usd."""
    base = [_reject_below_fico(700)]    # strict — 2 of 3 fail
    cand = [_reject_below_fico(620)]    # loose — 1 of 3 fails
    loans = [
        _loan("L1", fico=720, dti=0.25, amount=10000),  # base PASS, cand PASS
        _loan("L2", fico=650, dti=0.25, amount=15000),  # base FAIL, cand PASS  ← gain
        _loan("L3", fico=600, dti=0.25, amount=5000),   # base FAIL, cand FAIL
    ]
    summary = evaluate_pair_in_memory(base, cand, loans)
    bs = summary["business_summary"]
    assert bs["loans_newly_approved"] == 1
    assert bs["loans_newly_denied"] == 0
    assert bs["exposure_change_gain_usd"] == pytest.approx(15000.0)
    assert bs["exposure_change_loss_usd"] == pytest.approx(0.0)
    assert bs["net_exposure_change_usd"] == pytest.approx(15000.0)


def test_top_changed_segment_picks_largest_absolute_swing():
    """The hero copy ('mostly NEAR_PRIME') needs an unambiguous answer:
    the segment with the biggest |delta| wins. With three segments and
    different fail rates, the one with the worst delta should be
    picked."""
    base = []  # everything APPROVED
    cand = [_reject_below_fico(700)]  # rejects FICO < 700
    loans = [
        # PRIME — all pass
        _loan("P1", fico=750, dti=0.2, amount=10000, segment="PRIME"),
        _loan("P2", fico=750, dti=0.2, amount=10000, segment="PRIME"),
        # NEAR_PRIME — half fail
        _loan("N1", fico=720, dti=0.2, amount=10000, segment="NEAR_PRIME"),
        _loan("N2", fico=680, dti=0.2, amount=10000, segment="NEAR_PRIME"),
        # SUBPRIME — all fail
        _loan("S1", fico=600, dti=0.2, amount=10000, segment="SUBPRIME"),
        _loan("S2", fico=580, dti=0.2, amount=10000, segment="SUBPRIME"),
    ]
    summary = evaluate_pair_in_memory(base, cand, loans)
    bs = summary["business_summary"]
    # SUBPRIME flipped from 100% → 0% (delta -1.0) — biggest swing
    assert bs["top_changed_segment"] == "SUBPRIME"
    seg = summary["by_segment"]["SUBPRIME"]
    assert seg["funded_amount_delta_usd"] == pytest.approx(-20000.0)


def test_per_segment_funded_amounts_match_per_loan_math():
    """Cross-check: per-segment funded_amount_delta should always equal
    candidate_funded_amount - base_funded_amount for that segment."""
    base = []
    cand = [_reject_below_fico(650)]
    loans = [
        _loan("P1", fico=720, dti=0.2, amount=10000, segment="PRIME"),
        _loan("P2", fico=620, dti=0.2, amount=8000, segment="PRIME"),  # rejected
        _loan("N1", fico=680, dti=0.2, amount=15000, segment="NEAR_PRIME"),
        _loan("N2", fico=600, dti=0.2, amount=12000, segment="NEAR_PRIME"),  # rejected
    ]
    summary = evaluate_pair_in_memory(base, cand, loans)
    for seg, info in summary["by_segment"].items():
        assert info["funded_amount_delta_usd"] == pytest.approx(
            info["candidate_funded_amount_usd"] - info["base_funded_amount_usd"]
        ), seg
