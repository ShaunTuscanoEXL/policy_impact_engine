"""Targeted unit tests for `_build_filters` in test_case_generator.

Born of a real-world bug: the function used to always emit `cond.operator`
in the filter, which meant any negative/boundary test that picked an input
value VIOLATING the rule's condition produced a filter that selected loans
where the rule would FIRE — exactly the opposite of what the test asserts.

These tests pin down each shape: scalar (>, >=, <, <=, ==, !=), between,
in/not_in, with both keep_range_operators on and off.
"""
from __future__ import annotations

import pytest

from app.pipeline.test_case_generator import _build_filters
from app.schemas.rule import Condition


def _f(field: str, op: str, value):
    """Helper: build a (Condition, json_path) tuple."""
    return (Condition(field=field, operator=op, value=value), field)


# ── Positive cases (input satisfies — keep operator) ─────────────────────

def test_positive_gt_keeps_operator():
    out = _build_filters([_f("dti_ratio", ">", 0.35)], {"dti_ratio": 0.40})
    assert out[0]["operator"] == ">"
    assert out[0]["value"] == 0.40


def test_positive_lt_keeps_operator():
    out = _build_filters([_f("bureau_score", "<", 720)], {"bureau_score": 700})
    assert out[0]["operator"] == "<"
    assert out[0]["value"] == 700


def test_positive_between_keeps_between():
    out = _build_filters(
        [_f("bureau_score", "between", [700, 749])],
        {"bureau_score": 720},
        keep_range_operators=True,
    )
    assert out[0]["operator"] == "between"
    assert out[0]["value"] == [700, 749]


# ── Negative cases (input violates — invert operator) ────────────────────

def test_negative_gt_inverts_to_lte_at_threshold():
    """Rule: dti > 0.35 ; input 0.35 violates ; filter must select
    loans where rule wouldn't fire → dti <= 0.35."""
    out = _build_filters(
        [_f("dti_ratio", ">", 0.35)],
        {"dti_ratio": 0.35},
        keep_range_operators=False,
    )
    assert out[0]["operator"] == "<="
    assert out[0]["value"] == 0.35


def test_negative_lt_inverts_to_gte_at_threshold():
    """Rule: bureau < 720 ; input 720 violates ; filter must be bureau >= 720."""
    out = _build_filters(
        [_f("bureau_score", "<", 720)],
        {"bureau_score": 720},
        keep_range_operators=False,
    )
    assert out[0]["operator"] == ">="
    assert out[0]["value"] == 720


def test_negative_gte_inverts_to_lt():
    out = _build_filters(
        [_f("monthly_income", ">=", 5000)],
        {"monthly_income": 4999},
        keep_range_operators=False,
    )
    assert out[0]["operator"] == "<"


def test_negative_lte_inverts_to_gt():
    out = _build_filters(
        [_f("dti_ratio", "<=", 0.43)],
        {"dti_ratio": 0.50},
        keep_range_operators=False,
    )
    assert out[0]["operator"] == ">"


def test_negative_eq_inverts_to_neq():
    out = _build_filters(
        [_f("loan_type", "==", "PERSONAL")],
        {"loan_type": "INVALID_VALUE"},
        keep_range_operators=False,
    )
    assert out[0]["operator"] == "!="
    assert out[0]["value"] == "PERSONAL"


def test_negative_neq_inverts_to_eq():
    out = _build_filters(
        [_f("region", "!=", "RESTRICTED")],
        {"region": "RESTRICTED"},
        keep_range_operators=False,
    )
    assert out[0]["operator"] == "=="


# ── Boundary "at-threshold" — same as negative (input doesn't satisfy `>`) ─

def test_boundary_gt_at_threshold_inverts():
    """The exact case that originally failed: BND-001 for dti > 0.35
    used to emit filter `dti > 0.35` and assert RULE_NOT_TRIGGERED →
    guaranteed FAIL. Now emits `dti <= 0.35`."""
    out = _build_filters(
        [_f("dti_ratio", ">", 0.35)],
        {"dti_ratio": 0.35},      # exactly at boundary, fails strict >
        keep_range_operators=False,
    )
    assert out[0]["operator"] == "<="
    assert out[0]["value"] == 0.35


def test_boundary_just_above_keeps_operator():
    out = _build_filters(
        [_f("dti_ratio", ">", 0.35)],
        {"dti_ratio": 0.36},      # just above, satisfies the rule
        keep_range_operators=False,
    )
    assert out[0]["operator"] == ">"
    assert out[0]["value"] == 0.36


# ── between with input outside range ─────────────────────────────────────

def test_between_input_below_range_uses_lt_threshold():
    out = _build_filters(
        [_f("bureau_score", "between", [700, 749])],
        {"bureau_score": 650},
        keep_range_operators=False,
    )
    assert out[0]["operator"] == "<"
    assert out[0]["value"] == 700


def test_between_input_above_range_uses_gt_threshold():
    out = _build_filters(
        [_f("bureau_score", "between", [700, 749])],
        {"bureau_score": 800},
        keep_range_operators=False,
    )
    assert out[0]["operator"] == ">"
    assert out[0]["value"] == 749


# ── in / not_in inversion ────────────────────────────────────────────────

def test_in_inverts_to_not_in_for_negative():
    out = _build_filters(
        [_f("city_tier", "in", ["TIER_1", "TIER_2"])],
        {"city_tier": "TIER_3"},
        keep_range_operators=False,
    )
    assert out[0]["operator"] == "not_in"
    assert out[0]["value"] == ["TIER_1", "TIER_2"]


def test_in_keeps_operator_for_positive():
    out = _build_filters(
        [_f("city_tier", "in", ["TIER_1", "TIER_2"])],
        {"city_tier": "TIER_1"},
        keep_range_operators=False,
    )
    assert out[0]["operator"] == "in"


def test_not_in_inverts_to_in_for_negative():
    out = _build_filters(
        [_f("status", "not_in", ["DELINQUENT", "DEFAULT"])],
        {"status": "DELINQUENT"},
        keep_range_operators=False,
    )
    assert out[0]["operator"] == "in"


# ── Multi-condition rule: each filter independently inverted ─────────────

def test_multi_condition_with_guard_satisfied_and_threshold_violated():
    """Real BRD-001 shape: loan_type==PERSONAL guard + dti > 0.35 threshold.
    For a NEG test where dti is at-boundary (0.35), the loan_type guard
    is still satisfied (input PERSONAL), so its filter stays ==. The dti
    filter inverts to <=."""
    out = _build_filters(
        [
            _f("loan_type", "==", "PERSONAL"),
            _f("dti_ratio", ">", 0.35),
        ],
        {"loan_type": "PERSONAL", "dti_ratio": 0.35},
        keep_range_operators=False,
    )
    assert out[0]["operator"] == "=="     # guard kept
    assert out[0]["value"] == "PERSONAL"
    assert out[1]["operator"] == "<="     # threshold inverted
    assert out[1]["value"] == 0.35
