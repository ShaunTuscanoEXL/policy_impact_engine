"""Regression: NEGATIVE and BOUNDARY test cases must not produce
overlapping (field, value) inputs for the same condition.

Before the fix, _violating_value() returned values adjacent to the
threshold (v, v-step, v+step) — the exact values that BOUNDARY tests
own — so every numeric scalar operator generated a duplicate test
across the two categories with identical input_values and expected
outcomes. This test asserts the gap is preserved going forward.
"""
from __future__ import annotations

import pytest

from app.pipeline.test_case_generator import (
    _NEGATIVE_OFFSET_MULT,
    _boundary_values,
    _violating_value,
    _get_field_meta,
)
from app.schemas.rule import Condition


def _cond(field: str, op: str, value) -> Condition:
    return Condition(field=field, operator=op, value=value, logic="AND")


# Realistic conditions across the operator vocabulary the extractor emits.
SCALAR_CASES = [
    _cond("bureau_score", ">=", 720),
    _cond("bureau_score", ">", 720),
    _cond("bureau_score", "<=", 680),
    _cond("bureau_score", "<", 680),
    _cond("bureau_score", "==", 700),
    _cond("dti_ratio", ">=", 0.43),
    _cond("dti_ratio", "<", 0.50),
    _cond("monthly_income", "<", 3500),
    _cond("inquiries_last_3m", ">", 5),
]

BETWEEN_CASE = _cond("bureau_score", "between", [620, 720])


@pytest.mark.parametrize("cond", SCALAR_CASES)
def test_negative_value_is_not_one_of_the_boundary_values(cond):
    """For every numeric scalar operator, the NEGATIVE test's violating
    input must NOT be one of BOUNDARY's at-threshold values (v-step,
    v, v+step). Same value across categories = duplicate test case."""
    neg = _violating_value(cond)
    boundary_inputs = {bval for bval, _label, _pass in _boundary_values(cond)}
    assert neg not in boundary_inputs, (
        f"{cond.field} {cond.operator} {cond.value}: "
        f"NEGATIVE produced {neg!r}, which is also a BOUNDARY value "
        f"({boundary_inputs}). Categories overlap."
    )


def test_negative_between_pair_disjoint_from_boundary():
    """For 'between', NEGATIVE produces (lo - 3*step, hi + 3*step) and
    BOUNDARY produces (lo - step, lo, hi, hi + step). The two violating
    pairs must be disjoint."""
    cond = BETWEEN_CASE
    step = _get_field_meta(cond.field).get("step", 1)
    lo, hi = cond.value
    neg_offset = step * _NEGATIVE_OFFSET_MULT
    expected_neg_violations = {lo - neg_offset, hi + neg_offset}
    boundary_inputs = {bval for bval, _label, _pass in _boundary_values(cond)}
    assert expected_neg_violations.isdisjoint(boundary_inputs), (
        f"between [{lo}, {hi}]: NEGATIVE violations {expected_neg_violations} "
        f"overlap BOUNDARY values {boundary_inputs}."
    )


@pytest.mark.parametrize("cond", SCALAR_CASES)
def test_negative_value_still_violates_the_predicate(cond):
    """Widening the offset must not break correctness — the NEGATIVE
    value must still violate the original condition."""
    neg = _violating_value(cond)
    v = cond.value
    op = cond.operator
    assert neg is not None
    if op == ">=":
        assert not (neg >= v), f"{neg} should violate >= {v}"
    elif op == ">":
        assert not (neg > v), f"{neg} should violate > {v}"
    elif op == "<=":
        assert not (neg <= v), f"{neg} should violate <= {v}"
    elif op == "<":
        assert not (neg < v), f"{neg} should violate < {v}"
    elif op == "==":
        assert neg != v, f"{neg} should violate == {v}"
