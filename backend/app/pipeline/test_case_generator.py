"""Test case generation engine.

Generates comprehensive test cases from compiled business rules.
Each test case includes input values and deterministic expected outcomes
computed by running inputs through the actual baseline + rule engine.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

from app.pipeline.rule_compiler import CompiledRule
from app.schemas.rule import RuleDefinition, Condition
from app.simulation.baseline import (
    DEFAULT_BASELINE, DEFAULT_RATE, RATE_TIERS,
    apply_baseline, assign_eligible_amount, assign_interest_rate,
)

logger = logging.getLogger(__name__)


class TestCaseCategory(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    BOUNDARY = "BOUNDARY"
    EDGE = "EDGE"
    INTERACTION = "INTERACTION"


@dataclass
class GeneratedTestCase:
    test_case_id: str
    description: str
    source_rule_ids: list[str]
    inputs: dict
    expected_outcome: dict
    category: TestCaseCategory


@dataclass
class TestCaseSuiteOutput:
    rule_set_id: str | None
    total_cases: int
    cases_by_category: dict
    test_cases: list[GeneratedTestCase] = field(default_factory=list)


_FIELD_DEFAULTS: dict[str, int | float] = {
    "bureau_score": 750, "monthly_income": 60000,
    "desired_amount": 200000, "dti_ratio": 0.30,
}

_FIELD_RANGES: dict[str, dict] = {
    "bureau_score": {"min": 300, "max": 900, "type": "int"},
    "monthly_income": {"min": 10000, "max": 500000, "type": "float"},
    "desired_amount": {"min": 50000, "max": 5000000, "type": "float"},
    "dti_ratio": {"min": 0.0, "max": 1.0, "type": "float"},
}

_MAX_INTERACTION_CASES = 5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_test_cases(
    compiled_rules: list[CompiledRule],
    rules: list[RuleDefinition],
    baseline_config: dict | None = None,
) -> TestCaseSuiteOutput:
    """Generate a full test-case suite from compiled business rules.

    For each rule, positive / negative / boundary / edge cases are created.
    Cross-rule interaction cases are appended at the end.  Every case gets
    its ``expected_outcome`` filled by running inputs through the real
    baseline + rule engine.
    """
    counter: dict[str, int] = {"n": 0}
    all_cases: list[GeneratedTestCase] = []

    for rule_def in rules:
        all_cases.extend(_generate_positive_cases(rule_def, counter))
        all_cases.extend(_generate_negative_cases(rule_def, counter))
        all_cases.extend(_generate_boundary_cases(rule_def, counter))
        all_cases.extend(_generate_edge_cases(rule_def, counter))

    all_cases.extend(_generate_interaction_cases(rules, counter))

    for tc in all_cases:
        tc.expected_outcome = _compute_expected_outcome(
            tc.inputs, compiled_rules, baseline_config,
        )

    cases_by_category: dict[str, int] = {}
    for tc in all_cases:
        cases_by_category[tc.category.value] = cases_by_category.get(tc.category.value, 0) + 1

    logger.info("Generated %d test cases across %d rules", len(all_cases), len(rules))
    return TestCaseSuiteOutput(
        rule_set_id=None, total_cases=len(all_cases),
        cases_by_category=cases_by_category, test_cases=all_cases,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_id(rule_id: str, category: str, counter: dict[str, int]) -> str:
    counter["n"] += 1
    return f"TC-{rule_id.replace('-', '')}-{category}-{counter['n']:02d}"


def _is_numeric(cond: Condition) -> bool:
    v = cond.value
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v)
            return True
        except ValueError:
            return False
    if isinstance(v, list) and v:
        return all(isinstance(x, (int, float)) for x in v)
    return False


def _num(value) -> float:
    return float(value)


def _make_baseline_inputs(rule_def: RuleDefinition) -> dict:
    """Return default inputs adjusted so every condition in *rule_def* is met."""
    inputs = dict(_FIELD_DEFAULTS)
    for cond in rule_def.conditions:
        if cond.field not in _FIELD_DEFAULTS or not _is_numeric(cond):
            continue
        v = _num(cond.value) if not isinstance(cond.value, list) else None
        op = cond.operator
        if op == ">=" and v is not None:
            inputs[cond.field] = max(inputs[cond.field], v + 10)
        elif op == "<=" and v is not None:
            inputs[cond.field] = min(inputs[cond.field], v - 0.01)
        elif op == ">" and v is not None:
            inputs[cond.field] = max(inputs[cond.field], v + 1)
        elif op == "<" and v is not None:
            inputs[cond.field] = min(inputs[cond.field], v - 1)
        elif op == "==" and v is not None:
            inputs[cond.field] = v
        elif op == "between" and isinstance(cond.value, list) and len(cond.value) == 2:
            inputs[cond.field] = (float(cond.value[0]) + float(cond.value[1])) / 2
    return inputs


def _satisfying_value(cond: Condition, margin_factor: float = 1.0) -> float | None:
    """Return a value that clearly satisfies *cond* with comfortable margin."""
    if not _is_numeric(cond):
        return None
    op = cond.operator
    if op == "between" and isinstance(cond.value, list) and len(cond.value) == 2:
        return (float(cond.value[0]) + float(cond.value[1])) / 2
    v = _num(cond.value) if not isinstance(cond.value, list) else None
    if v is None:
        return None
    margin = 50 * margin_factor if cond.field == "bureau_score" else v * 0.1 * margin_factor
    mapping = {">=": v + abs(margin), "<=": v - abs(margin), ">": v + 1, "<": v - 1, "==": v}
    return mapping.get(op)


def _violating_value(cond: Condition) -> float | None:
    """Return a value that violates *cond*."""
    if not _is_numeric(cond):
        return None
    op = cond.operator
    if op == "between" and isinstance(cond.value, list) and len(cond.value) == 2:
        return float(cond.value[0]) - 1
    v = _num(cond.value) if not isinstance(cond.value, list) else None
    if v is None:
        return None
    margin = 50 if cond.field == "bureau_score" else 0.1
    mapping = {">=": v - abs(margin), "<=": v + abs(margin), ">": v, "<": v, "==": v + 1}
    return mapping.get(op)


# ---------------------------------------------------------------------------
# Per-rule generators
# ---------------------------------------------------------------------------

def _generate_positive_cases(rule_def: RuleDefinition, counter: dict[str, int]) -> list[GeneratedTestCase]:
    """Generate 1-2 cases where ALL conditions are satisfied."""
    cases: list[GeneratedTestCase] = []
    base = _make_baseline_inputs(rule_def)

    inputs_1 = dict(base)
    for cond in rule_def.conditions:
        val = _satisfying_value(cond, margin_factor=1.0)
        if val is not None and cond.field in _FIELD_DEFAULTS:
            inputs_1[cond.field] = val
    cases.append(GeneratedTestCase(
        test_case_id=_next_id(rule_def.rule_id, "POS", counter),
        description=f"Positive: all conditions of {rule_def.rule_name} satisfied",
        source_rule_ids=[rule_def.rule_id], inputs=inputs_1,
        expected_outcome={}, category=TestCaseCategory.POSITIVE,
    ))

    if len(rule_def.conditions) > 2:
        inputs_2 = dict(base)
        for cond in rule_def.conditions:
            val = _satisfying_value(cond, margin_factor=2.0)
            if val is not None and cond.field in _FIELD_DEFAULTS:
                inputs_2[cond.field] = val
        cases.append(GeneratedTestCase(
            test_case_id=_next_id(rule_def.rule_id, "POS", counter),
            description=f"Positive (variant): {rule_def.rule_name} wider margin",
            source_rule_ids=[rule_def.rule_id], inputs=inputs_2,
            expected_outcome={}, category=TestCaseCategory.POSITIVE,
        ))
    return cases


def _generate_negative_cases(rule_def: RuleDefinition, counter: dict[str, int]) -> list[GeneratedTestCase]:
    """Generate one case per condition that violates just that condition."""
    cases: list[GeneratedTestCase] = []
    base = _make_baseline_inputs(rule_def)
    for cond in rule_def.conditions:
        viol = _violating_value(cond)
        if viol is None:
            continue
        inputs = dict(base)
        inputs[cond.field] = viol
        cases.append(GeneratedTestCase(
            test_case_id=_next_id(rule_def.rule_id, "NEG", counter),
            description=f"Negative: violates '{cond.field} {cond.operator} {cond.value}' of {rule_def.rule_name}",
            source_rule_ids=[rule_def.rule_id], inputs=inputs,
            expected_outcome={}, category=TestCaseCategory.NEGATIVE,
        ))
    return cases


def _generate_boundary_cases(rule_def: RuleDefinition, counter: dict[str, int]) -> list[GeneratedTestCase]:
    """Generate boundary-value cases for each numeric condition."""
    cases: list[GeneratedTestCase] = []
    base = _make_baseline_inputs(rule_def)

    for cond in rule_def.conditions:
        if not _is_numeric(cond):
            continue
        op = cond.operator
        test_values: list[float] = []

        if op == "between" and isinstance(cond.value, list) and len(cond.value) == 2:
            lo, hi = float(cond.value[0]), float(cond.value[1])
            test_values = [lo - 1, lo, hi, hi + 1]
        elif isinstance(cond.value, list):
            continue
        else:
            v = _num(cond.value)
            if op in (">=", "<=", "=="):
                test_values = [v - 1, v, v + 1]
            elif op == ">":
                test_values = [v, v + 1]
            elif op == "<":
                test_values = [v - 1, v]

        for tv in test_values:
            inputs = dict(base)
            inputs[cond.field] = tv
            cases.append(GeneratedTestCase(
                test_case_id=_next_id(rule_def.rule_id, "BND", counter),
                description=f"Boundary: {cond.field}={tv} vs '{cond.operator} {cond.value}' of {rule_def.rule_name}",
                source_rule_ids=[rule_def.rule_id], inputs=inputs,
                expected_outcome={}, category=TestCaseCategory.BOUNDARY,
            ))
    return cases


def _generate_edge_cases(rule_def: RuleDefinition, counter: dict[str, int]) -> list[GeneratedTestCase]:
    """Generate edge cases with extreme input values."""
    zero = {"bureau_score": 0, "monthly_income": 0, "desired_amount": 0, "dti_ratio": 0.0}
    high = {"bureau_score": 999, "monthly_income": 999999, "desired_amount": 9999999, "dti_ratio": 0.99}
    cases = []
    for label, inp in [("all zeros", zero), ("extreme highs", high)]:
        cases.append(GeneratedTestCase(
            test_case_id=_next_id(rule_def.rule_id, "EDGE", counter),
            description=f"Edge ({label}): {rule_def.rule_name}",
            source_rule_ids=[rule_def.rule_id], inputs=dict(inp),
            expected_outcome={}, category=TestCaseCategory.EDGE,
        ))
    return cases


# ---------------------------------------------------------------------------
# Interaction cases
# ---------------------------------------------------------------------------

def _generate_interaction_cases(rules: list[RuleDefinition], counter: dict[str, int]) -> list[GeneratedTestCase]:
    """Generate cases exercising pairs of rules that share a common field."""
    cases: list[GeneratedTestCase] = []
    field_to_rules: dict[str, list[RuleDefinition]] = {}
    for rule in rules:
        for cond in rule.conditions:
            field_to_rules.setdefault(cond.field, []).append(rule)

    seen: set[tuple[str, str]] = set()
    for field_name, related in field_to_rules.items():
        if len(related) < 2:
            continue
        for i in range(len(related)):
            for j in range(i + 1, len(related)):
                if len(cases) >= _MAX_INTERACTION_CASES:
                    return cases
                r1, r2 = related[i], related[j]
                pair = tuple(sorted([r1.rule_id, r2.rule_id]))
                if pair in seen:
                    continue
                seen.add(pair)

                inputs = _make_baseline_inputs(r1)
                for cond in r2.conditions:
                    val = _satisfying_value(cond)
                    if val is not None and cond.field in _FIELD_DEFAULTS:
                        inputs[cond.field] = val

                # Check for contradictions with r1 conditions
                conflict = False
                for cond in r1.conditions:
                    if not _is_numeric(cond) or cond.field not in inputs:
                        continue
                    cur = inputs[cond.field]
                    v = _num(cond.value) if not isinstance(cond.value, list) else None
                    if v is None:
                        continue
                    op = cond.operator
                    if (op == ">=" and cur < v) or (op == "<=" and cur > v) or \
                       (op == ">" and cur <= v) or (op == "<" and cur >= v) or \
                       (op == "==" and cur != v):
                        conflict = True
                        break
                if conflict:
                    continue

                cases.append(GeneratedTestCase(
                    test_case_id=_next_id(f"{r1.rule_id}x{r2.rule_id}", "INT", counter),
                    description=f"Interaction: {r1.rule_name} + {r2.rule_name} (field: {field_name})",
                    source_rule_ids=[r1.rule_id, r2.rule_id], inputs=inputs,
                    expected_outcome={}, category=TestCaseCategory.INTERACTION,
                ))
    return cases


# ---------------------------------------------------------------------------
# Expected outcome computation
# ---------------------------------------------------------------------------

def _compute_expected_outcome(
    inputs: dict, compiled_rules: list[CompiledRule], baseline_config: dict | None,
) -> dict:
    """Run inputs through the baseline + rule engine to get a deterministic outcome.

    Creates a single-row DataFrame, applies baseline decisions, then each
    compiled rule in priority order.  Returns the final decision, amounts,
    rate, and any flags set by rules.
    """
    df = pd.DataFrame([inputs])
    for col, default in _FIELD_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default

    df = apply_baseline(df, config=baseline_config)
    df["sim_decision"] = df["baseline_decision"]
    df["sim_eligible_amount"] = df["baseline_eligible_amount"]
    df["sim_interest_rate"] = df["baseline_interest_rate"]

    for rule in sorted(compiled_rules, key=lambda r: r.priority):
        try:
            mask = rule.evaluate(df)
            if mask.any():
                df = rule.apply(df, mask)
        except Exception:
            logger.debug("Rule %s skipped during outcome computation", rule.rule_id)

    row = df.iloc[0]
    flags = [c.replace("flag_", "") for c in df.columns if c.startswith("flag_") and bool(row[c])]
    return {
        "decision": str(row["sim_decision"]),
        "eligible_amount": float(row["sim_eligible_amount"]),
        "interest_rate": float(row["sim_interest_rate"]),
        "baseline_decision": str(row["baseline_decision"]),
        "flags": flags,
    }
