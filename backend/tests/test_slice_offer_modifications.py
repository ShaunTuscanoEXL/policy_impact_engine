"""Slice 13 — track non-decision offer modifications in impact summary.

Pricing/eligibility-only BRDs (like the Repeat Customer Offer Framework)
modify offer terms (eligible_amount, interest_rate, max_tenure_months)
without changing APPROVED/FLAGGED/REJECTED. Before Slice 13 these always
showed "0 flips" in impact analysis, making the BRD look like it did
nothing. This test asserts the new offer_modifications block surfaces
those changes.
"""
from __future__ import annotations

import pytest

from app.services.impact_service import evaluate_pair_in_memory


pytestmark = pytest.mark.anyio


def _loan(loan_id: str, fico: int, segment: str = "PRIME", amount: float = 10000) -> dict:
    return {
        "loan_application_id": loan_id,
        "desired_amount": amount,
        "borrower_credit_model": {
            "customer_inputs": {"monthly_income": 8000},
            "bureau_credits": {"bureau_score": fico},
        },
        "calculated_attributes": {"debt_to_income_ratio": 0.25},
        "decision_context": {"risk_segment": segment},
        "customer_segment": "SEGMENT_A",
    }


def _set_offer_rule(rid: str, field: str, value, subsystem: str = "AMOUNT_CAP") -> dict:
    """A rule that sets an offer field for every loan (no condition)."""
    return {
        "id": f"rule-{rid}",
        "rule_id": rid,
        "rule_name": f"Set {field}",
        "rule_type": "PRICING",
        "subsystem": subsystem,
        "canonical_key": f"{subsystem}::{field}::ALWAYS::CAP::OTHER",
        "conditions": [],
        "actions": [
            {
                "action_type": "SET",
                "target_field": field,
                "value": value,
                "description": "",
            }
        ],
        "priority": 0,
        "confidence": 1.0,
    }


def test_offer_modifications_block_is_present_and_well_formed():
    """Schema contract: every impact summary has the block, with the
    keys the BusinessImpactCard binds to."""
    summary = evaluate_pair_in_memory([], [], [_loan("L1", 720)])
    om = summary.get("offer_modifications")
    assert om is not None, "offer_modifications block missing"
    expected = {
        "loans_with_any_offer_change",
        "loans_with_offer_change_but_decision_unchanged",
        "new_writes_by_field",
        "new_writes_by_class",
        "dropped_writes_by_field",
        "fields_touched_only_in_candidate",
    }
    assert expected.issubset(om.keys()), om.keys()


def test_pricing_only_brd_shows_offer_changes_with_zero_decision_flips():
    """The Repeat Customer BRD case: candidate adds rules that touch
    interest_rate / eligible_amount / max_tenure_months on every loan
    but doesn't reject anyone. Decision flips = 0, offer changes > 0."""
    base = []   # base: no rules → all APPROVED, no offer writes
    candidate = [
        _set_offer_rule("R-RATE", "interest_rate", 0.0999, "RATE_MODIFIER"),
        _set_offer_rule("R-AMT", "eligible_amount", 50000, "AMOUNT_CAP"),
        _set_offer_rule("R-TENURE", "max_tenure_months", 72, "AMOUNT_CAP"),
    ]
    loans = [_loan(f"L{i}", 720) for i in range(50)]
    summary = evaluate_pair_in_memory(base, candidate, loans)

    # Zero decision flips — both sides APPROVE every loan
    assert sum(summary["decision_flips"].values()) == 0

    om = summary["offer_modifications"]
    # All 50 loans got new offer writes
    assert om["loans_with_any_offer_change"] == 50
    assert om["loans_with_offer_change_but_decision_unchanged"] == 50

    # Every field shows 50 affected loans
    by_field = {x["field"]: x for x in om["new_writes_by_field"]}
    assert "interest_rate" in by_field
    assert "eligible_amount" in by_field
    assert "max_tenure_months" in by_field
    for f in by_field.values():
        assert f["loans_affected"] == 50

    # Field classes group correctly for the dashboard chips
    by_class = {x["class"]: x for x in om["new_writes_by_class"]}
    assert by_class["RATE"]["loans_affected"] == 50
    assert by_class["AMOUNT"]["loans_affected"] == 50
    assert by_class["TENURE"]["loans_affected"] == 50


def test_offer_modifications_ignores_decision_status_writes():
    """SET decision_status (which IS the decision) shouldn't be
    double-counted as an offer modification — it's already tracked in
    decision_distribution."""
    candidate = [
        {
            "id": "x", "rule_id": "X", "rule_name": "x", "rule_type": "ELIGIBILITY",
            "subsystem": "BUREAU_GATE",
            "canonical_key": "BUREAU_GATE::decision_status::ALWAYS::CAP::DECISION",
            "conditions": [],
            "actions": [{"action_type": "SET", "target_field": "decision_status",
                        "value": "ELIGIBLE", "description": ""}],
            "priority": 0, "confidence": 1.0,
        },
    ]
    summary = evaluate_pair_in_memory([], candidate, [_loan("L1", 720)])
    om = summary["offer_modifications"]
    assert om["loans_with_any_offer_change"] == 0
    assert om["new_writes_by_field"] == []


def test_offer_modifications_reports_dropped_writes_when_candidate_removes_a_rule():
    """If the candidate REMOVES a pricing rule that base had, that
    should show as a dropped_writes entry."""
    base = [_set_offer_rule("R-RATE", "interest_rate", 0.0999, "RATE_MODIFIER")]
    candidate: list = []  # candidate has no pricing rules
    loans = [_loan(f"L{i}", 720) for i in range(10)]
    summary = evaluate_pair_in_memory(base, candidate, loans)
    om = summary["offer_modifications"]
    assert om["loans_with_any_offer_change"] == 10
    dropped = {x["field"]: x for x in om["dropped_writes_by_field"]}
    assert "interest_rate" in dropped
    assert dropped["interest_rate"]["loans_affected"] == 10
    assert om["new_writes_by_field"] == []
