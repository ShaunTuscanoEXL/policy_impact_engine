"""Regression: lookup-table rules (case-on-discriminator-value) must
NOT collapse to the same canonical_key.

Before Slice 12 the key was {SUBSYSTEM}::{field}::{op_class}::{action_class}
— it ignored the equality value and the action's target_field. As a
result, this Repeat Customer BRD pattern:

    RULE-007: IF credit_risk_band == LOW    THEN SET customer_segment = SEGMENT_A
    RULE-008: IF credit_risk_band == MEDIUM THEN SET customer_segment = SEGMENT_B
    RULE-009: IF credit_risk_band == HIGH   THEN SET customer_segment = SEGMENT_C

…produced ONE canonical_key for all three, and only the last variant
survived merge apply (next_snapshot[ck] = incoming overwrites).

The fix:
1. Append target_class to every canonical_key (RULE-013 SET max_tenure
   vs RULE-010 ADJUST eligible_amount now differ even though the
   trigger is identical).
2. Insert the equality VALUE for EQ/NEQ/IN/NIN on non-numeric values
   (lookup-table variants now differ on the discriminator).
3. Numeric threshold comparisons (`fico < 680`) still omit the value
   so THRESHOLD_TIGHTENING detection still works.
"""
from __future__ import annotations

import pytest

from app.services.canonical_key import make_canonical_key


# ── Lookup-table pattern from the Repeat Customer BRD ──────────────────


def _eq_cond(field, value):
    return [{"field": field, "operator": "==", "value": value, "logic": "AND"}]


def _set(target, value):
    return [{"action_type": "SET", "target_field": target, "value": value, "description": ""}]


def _adjust(target, value):
    return [{"action_type": "ADJUST", "target_field": target, "value": value, "description": ""}]


def test_segment_assignment_lookup_table_keys_are_distinct():
    """RULE-007/008/009: same field & action_class, different enum
    values. Must produce three distinct canonical_keys."""
    ka = make_canonical_key("SCORING_MODEL", _eq_cond("credit_risk_band", "LOW"),
                            _set("customer_segment", "SEGMENT_A"))
    kb = make_canonical_key("SCORING_MODEL", _eq_cond("credit_risk_band", "MEDIUM"),
                            _set("customer_segment", "SEGMENT_B"))
    kc = make_canonical_key("SCORING_MODEL", _eq_cond("credit_risk_band", "HIGH"),
                            _set("customer_segment", "SEGMENT_C"))
    assert len({ka, kb, kc}) == 3, (
        f"All three credit_risk_band variants collapsed to the same key: "
        f"LOW={ka!r} MEDIUM={kb!r} HIGH={kc!r}"
    )


def test_segment_based_amount_adjust_keys_are_distinct():
    """RULE-010/011/012: ADJUST eligible_amount, three segments."""
    ka = make_canonical_key("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_A"),
                            _adjust("eligible_amount", 0.4))
    kb = make_canonical_key("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_B"),
                            _adjust("eligible_amount", 0.25))
    kc = make_canonical_key("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_C"),
                            _adjust("eligible_amount", -0.1))
    assert len({ka, kb, kc}) == 3, (ka, kb, kc)


def test_segment_based_tenure_set_keys_are_distinct():
    """RULE-013/014/015: SET max_tenure_months, three segments."""
    ka = make_canonical_key("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_A"),
                            _set("max_tenure_months", 72))
    kb = make_canonical_key("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_B"),
                            _set("max_tenure_months", 60))
    kc = make_canonical_key("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_C"),
                            _set("max_tenure_months", 36))
    assert len({ka, kb, kc}) == 3, (ka, kb, kc)


def test_same_trigger_different_target_keys_are_distinct():
    """RULE-010 (ADJUST eligible_amount) vs RULE-013 (SET max_tenure):
    same trigger condition, different target field. Must differ."""
    k_amt = make_canonical_key("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_A"),
                                _adjust("eligible_amount", 0.4))
    k_ten = make_canonical_key("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_A"),
                                _set("max_tenure_months", 72))
    assert k_amt != k_ten


def test_full_repeat_customer_brd_18_rules_produce_18_keys():
    """End-to-end: the 18 rules extracted from the Repeat Customer BRD
    should produce 18 distinct canonical_keys (modulo legitimate dups
    if any). Pre-fix this collapsed to 4."""
    brd_rules = [
        # 1. framework eligibility
        ("UNCLASSIFIED", _eq_cond("repeat_type", "REPEAT"),
         _set("framework_eligibility", "ELIGIBLE")),
        # 2..6. good-customer flag inputs
        ("UNCLASSIFIED", _eq_cond("recent_repayment_behavior", "NO_MISSED_OR_DELAYED_REPAYMENTS"),
         _set("good_customer_flag", True)),
        ("DTI_GATE", [{"field": "dti_ratio", "operator": "<=", "value": 0.2, "logic": "AND"}],
         _set("good_customer_flag", True)),
        ("DTI_GATE", [{"field": "net_monthly_surplus", "operator": ">", "value": 0, "logic": "AND"}],
         _set("good_customer_flag", True)),
        ("BANKING_BEHAVIOR", [{"field": "salary_credit_consistency_6m", "operator": ">", "value": 0.75, "logic": "AND"}],
         _set("good_customer_flag", True)),
        ("BUREAU_GATE", _eq_cond("overdue_accounts", 0),
         _set("good_customer_flag", True)),
        # 7..9. segment assignment
        ("SCORING_MODEL", _eq_cond("credit_risk_band", "LOW"),
         _set("customer_segment", "SEGMENT_A")),
        ("SCORING_MODEL", _eq_cond("credit_risk_band", "MEDIUM"),
         _set("customer_segment", "SEGMENT_B")),
        ("SCORING_MODEL", _eq_cond("credit_risk_band", "HIGH"),
         _set("customer_segment", "SEGMENT_C")),
        # 10..12. amount adjust by segment
        ("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_A"),
         _adjust("eligible_amount", 0.4)),
        ("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_B"),
         _adjust("eligible_amount", 0.25)),
        ("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_C"),
         _adjust("eligible_amount", -0.1)),
        # 13..15. tenure set by segment
        ("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_A"),
         _set("max_tenure_months", 72)),
        ("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_B"),
         _set("max_tenure_months", 60)),
        ("AMOUNT_CAP", _eq_cond("customer_segment", "SEGMENT_C"),
         _set("max_tenure_months", 36)),
        # 16..17. APR adjust by segment
        ("RATE_MODIFIER", _eq_cond("customer_segment", "SEGMENT_A"),
         _adjust("interest_rate", -0.025)),
        ("RATE_MODIFIER", _eq_cond("customer_segment", "SEGMENT_B"),
         _adjust("interest_rate", -0.015)),
        # 18. segment C explicit no-change
        ("PRICING_TIER", _eq_cond("customer_segment", "SEGMENT_C"),
         _set("interest_rate_adjustment", 0)),
    ]
    keys = [make_canonical_key(sub, conds, acts) for sub, conds, acts in brd_rules]
    unique = set(keys)
    assert len(unique) == len(brd_rules), (
        f"{len(brd_rules)} rules collapsed to {len(unique)} keys. "
        f"Pre-Slice-12 this was 4 — the BRD lost {len(brd_rules) - len(unique)} rules at merge."
    )


# ── Threshold-tightening pairing must still work (numeric ==) ──────────


def test_threshold_tightening_keys_still_pair_for_numeric_equality():
    """`fico == 680` and `fico == 720` are different thresholds of the
    SAME rule. They must share canonical_key so the merge engine can
    pair them and detect THRESHOLD_TIGHTENING. (Critical: this is the
    historical promise we MUST NOT break.)"""
    k680 = make_canonical_key(
        "BUREAU_GATE", _eq_cond("bureau_score", 680),
        [{"action_type": "REJECT", "target_field": "decision_status",
          "value": "REJECTED", "description": ""}],
    )
    k720 = make_canonical_key(
        "BUREAU_GATE", _eq_cond("bureau_score", 720),
        [{"action_type": "REJECT", "target_field": "decision_status",
          "value": "REJECTED", "description": ""}],
    )
    assert k680 == k720, (
        f"Numeric threshold variants should pair for THRESHOLD_TIGHTENING. "
        f"680→{k680!r} vs 720→{k720!r}"
    )


def test_threshold_tightening_keys_still_pair_for_numeric_lt():
    """Same principle for `<`."""
    k1 = make_canonical_key(
        "BUREAU_GATE",
        [{"field": "bureau_score", "operator": "<", "value": 680, "logic": "AND"}],
        [{"action_type": "REJECT", "target_field": "decision_status",
          "value": "REJECTED", "description": ""}],
    )
    k2 = make_canonical_key(
        "BUREAU_GATE",
        [{"field": "bureau_score", "operator": "<", "value": 720, "logic": "AND"}],
        [{"action_type": "REJECT", "target_field": "decision_status",
          "value": "REJECTED", "description": ""}],
    )
    assert k1 == k2


def test_action_drift_still_detected_by_pairing_key():
    """REJECT vs FLAG on the same condition should remain distinct in
    canonical_key (so they're not classified as DUPLICATE) — the
    pairing_key (which strips action_class) is what pairs them for
    ACTION_DRIFT classification."""
    k_rej = make_canonical_key(
        "BUREAU_GATE",
        [{"field": "bureau_score", "operator": "<", "value": 600, "logic": "AND"}],
        [{"action_type": "REJECT", "target_field": "decision_status", "value": "REJECTED", "description": ""}],
    )
    k_flg = make_canonical_key(
        "BUREAU_GATE",
        [{"field": "bureau_score", "operator": "<", "value": 600, "logic": "AND"}],
        [{"action_type": "FLAG", "target_field": "decision_status", "value": "MANUAL_REVIEW", "description": ""}],
    )
    assert k_rej != k_flg


# ── Backward compatibility: keys still encode the original info ────────


def test_new_key_format_has_target_class_suffix():
    """Every canonical_key produced by the new generator must contain a
    target_class segment. Old format had 4 segments, new has >= 5."""
    k = make_canonical_key(
        "BUREAU_GATE",
        [{"field": "bureau_score", "operator": "<", "value": 680, "logic": "AND"}],
        [{"action_type": "REJECT", "target_field": "decision_status", "value": "REJECTED", "description": ""}],
    )
    # Old: BUREAU_GATE::bureau_score::LT::REJECT  (3 separators / 4 segments)
    # New: BUREAU_GATE::bureau_score::LT::REJECT::DECISION  (4 sep / 5 segs)
    assert k.count("::") >= 4
    assert k.endswith("::DECISION")
