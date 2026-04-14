"""Test case generator — builds comprehensive, concrete test cases from extracted rules.

Design principles:
  1. Every rule gets at least one POSITIVE and one NEGATIVE test case
  2. Every numeric condition gets BOUNDARY tests (at, above, below threshold)
  3. EDGE cases cover extremes, nulls, and type boundary values
  4. INTERACTION cases find overlapping/conflicting rules
  5. Auto-suggest counts based on rule complexity (conditions × categories)
  6. Concrete input values in every test case — not just filter descriptions
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.schemas.rule import RuleDefinition, Condition, Action
from app.services.field_registry import resolve_field_path

logger = logging.getLogger(__name__)


class TestCaseCategory(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    BOUNDARY = "BOUNDARY"
    EDGE = "EDGE"
    INTERACTION = "INTERACTION"


@dataclass
class FilterCondition:
    """A single filter condition for querying loan records."""
    field_name: str
    json_path: str
    operator: str
    value: Any
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "json_path": self.json_path,
            "operator": self.operator,
            "value": self.value,
            "description": self.description,
        }


@dataclass
class GeneratedTestCase:
    test_case_id: str
    description: str
    source_rule_ids: list[str]
    category: TestCaseCategory
    input_values: dict           # Concrete input values for this test
    filter_logic: list[dict]     # Filter conditions for DB matching
    expected_outcome: dict       # Expected result when rule engine runs
    rationale: str = ""          # Why this test case exists

    def filter_description(self) -> str:
        parts = [f["description"] or f"{f['field_name']} {f['operator']} {f['value']}" for f in self.filter_logic]
        return " AND ".join(parts)


@dataclass
class TestCaseSuiteOutput:
    rule_set_id: str | None
    total_cases: int
    cases_by_category: dict
    test_cases: list[GeneratedTestCase] = field(default_factory=list)
    coverage_stats: dict = field(default_factory=dict)
    suggested_counts: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Field metadata — sensible defaults, ranges, and extreme values
# ---------------------------------------------------------------------------

FIELD_DEFAULTS: dict[str, dict] = {
    "bureau_score": {"type": "int", "default": 750, "min": 300, "max": 900, "step": 1},
    "monthly_income": {"type": "int", "default": 50000, "min": 0, "max": 5000000, "step": 1000},
    "age": {"type": "int", "default": 35, "min": 18, "max": 80, "step": 1},
    "desired_amount": {"type": "int", "default": 500000, "min": 0, "max": 50000000, "step": 10000},
    "dti_ratio": {"type": "float", "default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01},
    "credit_utilization_ratio": {"type": "float", "default": 0.40, "min": 0.0, "max": 1.0, "step": 0.01},
    "employment_tenure_months": {"type": "int", "default": 36, "min": 0, "max": 480, "step": 1},
    "account_vintage_months": {"type": "int", "default": 24, "min": 0, "max": 600, "step": 1},
    "active_loans": {"type": "int", "default": 2, "min": 0, "max": 20, "step": 1},
    "unsecured_loans": {"type": "int", "default": 1, "min": 0, "max": 15, "step": 1},
    "inquiries_last_3m": {"type": "int", "default": 2, "min": 0, "max": 30, "step": 1},
    "inquiries_last_12m": {"type": "int", "default": 5, "min": 0, "max": 50, "step": 1},
    "max_dpd_last_12m": {"type": "int", "default": 0, "min": 0, "max": 365, "step": 1},
    "cheque_bounces_6m": {"type": "int", "default": 0, "min": 0, "max": 20, "step": 1},
    "loan_repayment_bounces_12m": {"type": "int", "default": 0, "min": 0, "max": 20, "step": 1},
    "overdue_accounts": {"type": "int", "default": 0, "min": 0, "max": 10, "step": 1},
    "salary_credit_consistency_6m": {"type": "float", "default": 0.85, "min": 0.0, "max": 1.0, "step": 0.01},
    "banking_stability_index": {"type": "float", "default": 0.75, "min": 0.0, "max": 1.0, "step": 0.01},
    "net_monthly_surplus": {"type": "int", "default": 15000, "min": -100000, "max": 500000, "step": 500},
    "g5_score": {"type": "int", "default": 600, "min": 0, "max": 1000, "step": 1},
    "g6_score": {"type": "int", "default": 650, "min": 0, "max": 1000, "step": 1},
    "interest_rate": {"type": "float", "default": 12.0, "min": 0.0, "max": 36.0, "step": 0.25},
    "eligible_amount": {"type": "int", "default": 500000, "min": 0, "max": 50000000, "step": 10000},
    "transaction_volatility_index": {"type": "float", "default": 0.30, "min": 0.0, "max": 1.0, "step": 0.01},
    "cash_deposits_6m": {"type": "int", "default": 200000, "min": 0, "max": 50000000, "step": 10000},
    "closed_loans": {"type": "int", "default": 3, "min": 0, "max": 30, "step": 1},
    "settled_accounts": {"type": "int", "default": 0, "min": 0, "max": 10, "step": 1},
    "write_offs": {"type": "int", "default": 0, "min": 0, "max": 10, "step": 1},
    "total_active_loans": {"type": "int", "default": 3, "min": 0, "max": 20, "step": 1},
    "low_balance_instances_6m": {"type": "int", "default": 1, "min": 0, "max": 30, "step": 1},
}

ENUM_FIELD_VALUES: dict[str, list[str]] = {
    "employment_type": ["SALARIED", "SELF_EMPLOYED", "NRI"],
    "city_tier": ["TIER_1", "TIER_2", "TIER_3", "TIER_4"],
    "residence_type": ["OWNED", "RENTED", "COMPANY_PROVIDED"],
    "repeat_type": ["NEW", "REPEAT"],
    "application_type": ["FRESH", "TOP_UP"],
    "credit_risk_band": ["ULTRA_PRIME", "PRIME", "NEAR_PRIME", "STANDARD", "SUB_STANDARD", "HIGH_RISK"],
    "decision_status": ["APPROVED", "REJECTED", "REVIEW"],
}


def _get_field_meta(field_name: str) -> dict:
    """Get metadata for a field, with sensible fallback."""
    normalized = field_name.lower().strip().replace(" ", "_").replace("-", "_")
    if normalized in FIELD_DEFAULTS:
        return FIELD_DEFAULTS[normalized]
    # Infer type from common patterns
    if "ratio" in normalized or "index" in normalized or "rate" in normalized:
        return {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}
    if "score" in normalized:
        return {"type": "int", "default": 600, "min": 0, "max": 1000, "step": 1}
    if "months" in normalized or "days" in normalized:
        return {"type": "int", "default": 24, "min": 0, "max": 600, "step": 1}
    if "amount" in normalized or "income" in normalized or "salary" in normalized:
        return {"type": "int", "default": 50000, "min": 0, "max": 10000000, "step": 1000}
    if "count" in normalized or "loans" in normalized or "bounces" in normalized:
        return {"type": "int", "default": 1, "min": 0, "max": 50, "step": 1}
    return {"type": "int", "default": 0, "min": 0, "max": 100, "step": 1}


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_enum_field(field_name: str) -> bool:
    normalized = field_name.lower().strip().replace(" ", "_").replace("-", "_")
    return normalized in ENUM_FIELD_VALUES


# ---------------------------------------------------------------------------
# Auto-suggest: calculate recommended test case counts
# ---------------------------------------------------------------------------

def suggest_counts(rules: list[RuleDefinition]) -> dict:
    """Calculate recommended test case counts based on rule complexity.

    Returns a dict with per-category counts and total, plus coverage rationale.
    """
    if not rules:
        return {"positive": 0, "negative": 0, "boundary": 0, "edge": 0, "interaction": 0, "total": 0}

    n_rules = len(rules)
    total_conditions = sum(len(r.conditions) for r in rules)
    between_conditions = sum(
        1 for r in rules for c in r.conditions
        if c.operator == "between" and isinstance(c.value, (list, tuple)) and len(c.value) == 2
    )
    numeric_conditions = sum(
        1 for r in rules for c in r.conditions
        if _is_numeric(c.value) or _get_field_meta(c.field)["type"] in ("int", "float")
            or (c.operator == "between" and isinstance(c.value, (list, tuple)))
    )
    enum_conditions = sum(
        1 for r in rules for c in r.conditions
        if isinstance(c.value, str) or _is_enum_field(c.field)
    )

    # Count OR groups: OR groups generate 1 negative test per group instead of per condition
    or_group_savings = 0  # conditions "saved" by grouping
    or_rules_count = 0
    for r in rules:
        if _has_or_logic(r):
            or_rules_count += 1
            groups = _get_or_groups(r)
            for group in groups:
                if len(group) > 1:
                    # Group of N conditions generates 1 test instead of N
                    or_group_savings += len(group) - 1

    # Find overlapping rule pairs (rules sharing fields)
    field_to_rules: dict[str, list[str]] = defaultdict(list)
    for r in rules:
        for c in r.conditions:
            field_to_rules[c.field].append(r.rule_id)
    overlap_pairs = set()
    for field, rule_ids in field_to_rules.items():
        if len(rule_ids) >= 2:
            for i in range(len(rule_ids)):
                for j in range(i + 1, len(rule_ids)):
                    overlap_pairs.add((rule_ids[i], rule_ids[j]))

    # Calculate counts
    positive = n_rules  # 1 per rule: all conditions satisfied (+ OR branch variants)
    # Negative: 1 per AND condition + 2 per between (below+above),
    # but OR groups collapse N conditions into 1 test
    negative = (total_conditions - or_group_savings) + between_conditions
    # Standard numeric conditions get 3 boundary values (below, at, above)
    # Between conditions get 4 (below-lower, at-lower, at-upper, above-upper)
    boundary = (numeric_conditions - between_conditions) * 3 + between_conditions * 4
    edge = max(numeric_conditions * 2, n_rules)  # extreme high + low per numeric, at least 1 per rule
    interaction = min(len(overlap_pairs), max(10, n_rules // 5))  # cap at reasonable number

    total = positive + negative + boundary + edge + interaction

    return {
        "positive": positive,
        "negative": negative,
        "boundary": boundary,
        "edge": edge,
        "interaction": interaction,
        "total": total,
        "rationale": {
            "rules": n_rules,
            "total_conditions": total_conditions,
            "numeric_conditions": numeric_conditions,
            "between_conditions": between_conditions,
            "enum_conditions": enum_conditions,
            "or_rules": or_rules_count,
            "or_group_savings": or_group_savings,
            "overlapping_rule_pairs": len(overlap_pairs),
            "explanation": (
                f"{n_rules} rules with {total_conditions} conditions "
                f"({numeric_conditions} numeric incl. {between_conditions} between, {enum_conditions} enum"
                f"{f', {or_rules_count} rules with OR logic saving {or_group_savings} negative tests' if or_group_savings else ''}). "
                f"{len(overlap_pairs)} rule pairs share fields. "
                f"Recommended {total} total test cases for comprehensive coverage."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Value generators — produce concrete input values for test cases
# ---------------------------------------------------------------------------

def _satisfying_value(cond: Condition) -> Any:
    """Generate a value that satisfies a condition."""
    meta = _get_field_meta(cond.field)
    v = cond.value
    op = cond.operator

    # Handle list-based operators FIRST (before the _is_numeric guard)
    if op == "between":
        if isinstance(v, (list, tuple)) and len(v) == 2:
            lo, hi = v
            if _is_numeric(lo) and _is_numeric(hi):
                mid = (lo + hi) / 2
                if isinstance(lo, int) and isinstance(hi, int):
                    return int(mid)
                return mid
            return lo
        return meta["default"]

    if op == "in":
        if isinstance(v, (list, tuple)) and v:
            return v[0]
        return v if v is not None else meta["default"]

    if op == "not_in":
        default = meta["default"]
        if isinstance(v, (list, tuple)) and default in v:
            step = meta.get("step", 1)
            for offset in range(1, 100):
                candidate = default + offset * step
                if candidate not in v and candidate <= meta.get("max", 1e9):
                    return candidate
                candidate = default - offset * step
                if candidate not in v and candidate >= meta.get("min", -1e9):
                    return candidate
        return default

    # String/enum conditions
    if isinstance(v, str) and not _is_numeric(v):
        return v

    # Non-numeric, non-list values — use default
    if not _is_numeric(v):
        return meta["default"]

    # Numeric scalar comparisons
    step = meta.get("step", 1)
    if op == ">=":
        return v
    elif op == ">":
        return v + step
    elif op == "<=":
        return v
    elif op == "<":
        return v - step
    elif op == "==":
        return v
    elif op == "!=":
        return v + step if _is_numeric(v) else meta["default"]
    return meta["default"]


def _violating_value(cond: Condition) -> Any:
    """Generate a value that violates a condition."""
    meta = _get_field_meta(cond.field)
    v = cond.value
    op = cond.operator
    step = meta.get("step", 1)

    # Handle list-based operators FIRST (before the _is_numeric guard)
    if op == "between":
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return v[1] + step  # Above range (below-range covered by boundary tests)
        return meta.get("max", 999999)

    if op == "in":
        if isinstance(v, (list, tuple)) and v:
            if all(_is_numeric(x) for x in v):
                return max(v) + step
            else:
                return "INVALID_VALUE"
        return meta.get("max", 999999)

    if op == "not_in":
        if isinstance(v, (list, tuple)) and v:
            return v[0]  # Return something that IS in the list
        return v

    # String/enum conditions
    if isinstance(v, str) and not _is_numeric(v):
        normalized = cond.field.lower().strip().replace(" ", "_").replace("-", "_")
        if normalized in ENUM_FIELD_VALUES:
            others = [x for x in ENUM_FIELD_VALUES[normalized] if x.lower() != v.lower()]
            return others[0] if others else "INVALID"
        for key, vals in ENUM_FIELD_VALUES.items():
            if key in normalized or normalized in key:
                others = [x for x in vals if x.lower() != v.lower()]
                return others[0] if others else "INVALID"
        return "INVALID_VALUE"

    # Non-numeric, non-list values — use default
    if not _is_numeric(v):
        return meta["default"]

    # Numeric scalar comparisons
    if op == ">=":
        return v - step
    elif op == ">":
        return v
    elif op == "<=":
        return v + step
    elif op == "<":
        return v
    elif op == "==":
        return v + step
    elif op == "!=":
        return v  # Exact value violates !=
    return meta.get("max", 999999)


def _boundary_values(cond: Condition) -> list[tuple[Any, str, bool]]:
    """Generate boundary values: (value, label, satisfies_condition).

    Returns list of (value, human_label, expected_pass).
    """
    op = cond.operator
    v = cond.value
    meta = _get_field_meta(cond.field)
    step = meta.get("step", 1)
    results = []

    # Handle between first — cond.value is a list, not a number
    if op == "between":
        if isinstance(v, (list, tuple)) and len(v) == 2:
            lo, hi = v
            if _is_numeric(lo) and _is_numeric(hi):
                results.append((lo - step, f"below range ({lo})", False))
                results.append((lo, f"at lower bound ({lo})", True))
                results.append((hi, f"at upper bound ({hi})", True))
                results.append((hi + step, f"above range ({hi})", False))
        return results

    # All other operators require a numeric scalar value
    if not _is_numeric(v):
        return []

    if op == ">=":
        results.append((v - step, f"just below {v}", False))
        results.append((v, f"exactly at {v}", True))
        results.append((v + step, f"just above {v}", True))
    elif op == ">":
        results.append((v, f"exactly at {v}", False))
        results.append((v + step, f"just above {v}", True))
    elif op == "<=":
        results.append((v - step, f"just below {v}", True))
        results.append((v, f"exactly at {v}", True))
        results.append((v + step, f"just above {v}", False))
    elif op == "<":
        results.append((v - step, f"just below {v}", True))
        results.append((v, f"exactly at {v}", False))
    elif op == "==":
        results.append((v - step, f"just below {v}", False))
        results.append((v, f"exactly at {v}", True))
        results.append((v + step, f"just above {v}", False))

    return results


def _edge_values(cond: Condition) -> list[tuple[Any, str]]:
    """Generate edge/extreme values for a condition."""
    # Skip edge values for string/enum fields — they don't have numeric extremes
    if isinstance(cond.value, str) and not _is_numeric(cond.value):
        if _is_enum_field(cond.field):
            # For enums, edge case = an invalid/unexpected value
            return [("UNKNOWN_VALUE", "invalid enum value")]
        return [("", "empty string"), (None, "null/missing")]

    meta = _get_field_meta(cond.field)
    results = []

    if _is_numeric(cond.value) or meta["type"] in ("int", "float"):
        results.append((meta["min"], f"minimum possible ({meta['min']})"))
        results.append((meta["max"], f"maximum possible ({meta['max']})"))
        if meta["min"] <= 0:
            results.append((0, "zero"))
        if meta["type"] == "int" and meta["min"] >= 0:
            results.append((-1, "negative (invalid)"))

    return results


def _build_input_values(rule: RuleDefinition, overrides: dict | None = None) -> dict:
    """Build a complete input value set that satisfies all conditions of a rule.

    When multiple conditions reference the same field (e.g., > 30 AND <= 60),
    finds the intersection range and picks the midpoint. Single conditions
    use the standard satisfying value.
    """
    # Group conditions by field
    field_conds: dict[str, list[Condition]] = defaultdict(list)
    for cond in rule.conditions:
        field_conds[cond.field].append(cond)

    inputs = {}
    for field, conds in field_conds.items():
        if len(conds) == 1:
            inputs[field] = _satisfying_value(conds[0])
        else:
            # Multiple conditions on same field — find intersection range
            ranges = [_get_condition_range(c) for c in conds]
            valid_ranges = [r for r in ranges if r is not None]

            if len(valid_ranges) >= 2:
                # Intersect all ranges
                lo = max(r[0] for r in valid_ranges)
                hi = min(r[1] for r in valid_ranges)
                if lo <= hi:
                    meta = _get_field_meta(field)
                    mid = (lo + hi) / 2
                    inputs[field] = int(mid) if meta.get("type") == "int" else mid
                else:
                    # Impossible intersection — use first condition's value
                    inputs[field] = _satisfying_value(conds[0])
            else:
                # Not all conditions have numeric ranges — use last satisfying value
                for cond in conds:
                    inputs[field] = _satisfying_value(cond)

    if overrides:
        inputs.update(overrides)

    return inputs


def _build_filters(conditions: list[tuple[Condition, str]], input_values: dict, keep_range_operators: bool = True) -> list[dict]:
    """Build filter conditions from resolved conditions and input values.

    Args:
        conditions: Resolved conditions with JSON paths.
        input_values: The concrete input values for this test case.
        keep_range_operators: If True (default for positive tests), keep between/in/not_in
            with their original range values for customer matching.
            If False (for negative/boundary tests where a value is overridden),
            check whether the input value is INSIDE or OUTSIDE the original range
            and adjust the filter accordingly.
    """
    filters = []
    for cond, path in conditions:
        input_val = input_values.get(cond.field)

        if cond.operator == "between" and isinstance(cond.value, (list, tuple)) and len(cond.value) == 2:
            lo, hi = cond.value
            # Check if the test input is inside or outside the range
            if keep_range_operators and _is_numeric(input_val) and _is_numeric(lo) and lo <= input_val <= hi:
                # Input is within range — use original between for customer matching
                filter_val = cond.value
                desc = f"{cond.field} between {lo} and {hi}"
            elif _is_numeric(input_val):
                # Input is outside range (negative/boundary test) — use point filter
                # to find customers matching the violating value
                if input_val < lo:
                    filter_val = input_val
                    desc = f"{cond.field} <= {input_val}"
                    filters.append(FilterCondition(
                        field_name=cond.field, json_path=path,
                        operator="<=", value=filter_val, description=desc,
                    ).to_dict())
                    continue
                else:
                    filter_val = input_val
                    desc = f"{cond.field} >= {input_val}"
                    filters.append(FilterCondition(
                        field_name=cond.field, json_path=path,
                        operator=">=", value=filter_val, description=desc,
                    ).to_dict())
                    continue
            else:
                filter_val = cond.value
                desc = f"{cond.field} between {lo} and {hi}"
        elif cond.operator in ("in", "not_in") and isinstance(cond.value, (list, tuple)):
            filter_val = cond.value
            desc = f"{cond.field} {cond.operator} [{', '.join(str(v) for v in cond.value)}]"
        else:
            filter_val = input_val if input_val is not None else cond.value
            desc = f"{cond.field} {cond.operator} {filter_val}"

        filters.append(FilterCondition(
            field_name=cond.field,
            json_path=path,
            operator=cond.operator,
            value=filter_val,
            description=desc,
        ).to_dict())
    return filters


def _extract_expected_outcome(rule: RuleDefinition, satisfied: bool) -> dict:
    """Determine expected outcome based on whether rule conditions are met."""
    outcome = {"decision": "UNKNOWN", "applied_rules": [], "flags": []}

    if not satisfied:
        outcome["decision"] = "RULE_NOT_TRIGGERED"
        outcome["reason"] = f"Rule {rule.rule_id} ({rule.rule_name}) should NOT fire"
        return outcome

    for action in rule.actions:
        if action.action_type == "REJECT":
            outcome["decision"] = "REJECTED"
            outcome["reject_reason"] = action.description
        elif action.action_type == "SET":
            if action.target_field in ("decision_status", "decision"):
                outcome["decision"] = str(action.value)
            else:
                outcome[action.target_field] = action.value
        elif action.action_type == "FLAG":
            outcome["flags"].append(action.value or action.description)
            if outcome["decision"] == "UNKNOWN":
                outcome["decision"] = "FLAGGED_FOR_REVIEW"
        elif action.action_type == "ADJUST":
            outcome[f"adjust_{action.target_field}"] = action.value
            outcome[f"adjust_desc_{action.target_field}"] = action.description

    # Add rule_id once (not per action)
    if rule.actions:
        outcome["applied_rules"].append(rule.rule_id)

    if outcome["decision"] == "UNKNOWN" and rule.actions:
        outcome["decision"] = "MODIFIED"

    outcome["rule_name"] = rule.rule_name
    outcome["rule_type"] = rule.rule_type.value if hasattr(rule.rule_type, "value") else str(rule.rule_type)
    return outcome


def _invert_operator(op: str) -> str:
    inversions = {
        ">=": "<", "<=": ">", ">": "<=", "<": ">=",
        "==": "!=", "!=": "==",
        "in": "not_in", "not_in": "in",
        "between": "not_between",
    }
    return inversions.get(op, op)


def _has_or_logic(rule: RuleDefinition) -> bool:
    """Check if a rule has any OR-chained conditions."""
    return any(c.logic.upper() == "OR" for c in rule.conditions)


def _get_or_groups(rule: RuleDefinition) -> list[list[int]]:
    """Partition conditions into AND/OR groups.

    Returns list of groups. Conditions within a group are OR'd together,
    and groups are AND'd. E.g., [A AND B OR C AND D] → [[0], [1, 2], [3]]

    IMPORTANT: Indices are into rule.conditions, NOT resolved_conds.
    Use _build_resolved_index_map() to translate when working with resolved_conds.
    """
    if not rule.conditions:
        return []
    groups: list[list[int]] = [[0]]
    for i in range(1, len(rule.conditions)):
        prev = rule.conditions[i - 1]
        if prev.logic.upper() == "OR":
            # This condition is OR'd with the previous → same group
            groups[-1].append(i)
        else:
            # AND → new group
            groups.append([i])
    return groups


def _build_resolved_index_map(
    rule: RuleDefinition,
    resolved_conds: list[tuple[Condition, str]],
) -> tuple[dict[int, int], dict[int, int]]:
    """Build bidirectional mapping between resolved_conds and rule.conditions indices.

    Returns:
        (resolved_to_orig, orig_to_resolved)
        - resolved_to_orig: resolved_conds index → rule.conditions index
        - orig_to_resolved: rule.conditions index → resolved_conds index
    """
    resolved_to_orig: dict[int, int] = {}
    orig_to_resolved: dict[int, int] = {}

    for ri, (cond, _path) in enumerate(resolved_conds):
        for oi, orig_cond in enumerate(rule.conditions):
            if cond is orig_cond and oi not in orig_to_resolved.values():
                resolved_to_orig[ri] = oi
                orig_to_resolved[oi] = ri
                break

    return resolved_to_orig, orig_to_resolved


def _rule_fires_with_or(rule: RuleDefinition, input_values: dict) -> bool:
    """Check if a rule fires given input values, respecting OR/AND logic.

    A rule fires when ALL AND-groups are satisfied. Within each AND-group,
    at least ONE condition must be satisfied (OR semantics).
    """
    or_groups = _get_or_groups(rule)
    if not or_groups:
        return False

    for group in or_groups:
        # At least one condition in this group must be satisfied
        group_satisfied = False
        for ci in group:
            if ci >= len(rule.conditions):
                continue
            cond = rule.conditions[ci]
            val = input_values.get(cond.field)
            if val is not None and _check_satisfies(cond, val):
                group_satisfied = True
                break
        if not group_satisfied:
            return False

    return True


# ---------------------------------------------------------------------------
# Per-category generators
# ---------------------------------------------------------------------------

def _gen_positive(
    rule: RuleDefinition,
    resolved_conds: list[tuple[Condition, str]],
    counter: int,
) -> list[GeneratedTestCase]:
    """Positive cases: all conditions satisfied → rule fires.

    For rules with OR logic, generates additional positive tests — one per
    OR branch — to verify the rule fires when only one branch is satisfied.
    """
    cases = []

    # Standard positive: satisfy everything
    inputs = _build_input_values(rule)
    filters = _build_filters(resolved_conds, inputs)
    expected = _extract_expected_outcome(rule, satisfied=True)

    cases.append(GeneratedTestCase(
        test_case_id=f"TC-{rule.rule_id}-POS-{counter:03d}",
        description=f"All conditions satisfied → {rule.rule_name}",
        source_rule_ids=[rule.rule_id],
        category=TestCaseCategory.POSITIVE,
        input_values=inputs,
        filter_logic=filters,
        expected_outcome=expected,
        rationale=f"Verify rule fires when all {len(rule.conditions)} conditions are met",
    ))

    # OR-branch positive variants: satisfy only one branch of each OR group
    if _has_or_logic(rule):
        or_groups = _get_or_groups(rule)
        for gi, group in enumerate(or_groups):
            if len(group) <= 1:
                continue
            # For each branch in the OR group, generate a test that satisfies
            # ONLY that branch (by violating all other branches in the group)
            for branch_idx in group:
                if branch_idx >= len(rule.conditions):
                    continue
                branch_cond = rule.conditions[branch_idx]
                overrides = {}
                other_branches = [ci for ci in group if ci != branch_idx and ci < len(rule.conditions)]
                for other_ci in other_branches:
                    other_cond = rule.conditions[other_ci]
                    # Only override if it's the same field — otherwise both are independently satisfied
                    if other_cond.field == branch_cond.field:
                        overrides[other_cond.field] = _satisfying_value(branch_cond)

                if not overrides:
                    continue  # No same-field OR branches to differentiate

                variant_inputs = _build_input_values(rule, overrides=overrides)
                variant_filters = _build_filters(resolved_conds, variant_inputs)

                counter += 1
                cases.append(GeneratedTestCase(
                    test_case_id=f"TC-{rule.rule_id}-POS-{counter:03d}",
                    description=(
                        f"OR branch: {branch_cond.field} {branch_cond.operator} {branch_cond.value} "
                        f"satisfied → {rule.rule_name}"
                    ),
                    source_rule_ids=[rule.rule_id],
                    category=TestCaseCategory.POSITIVE,
                    input_values=variant_inputs,
                    filter_logic=variant_filters,
                    expected_outcome=_extract_expected_outcome(rule, satisfied=True),
                    rationale=(
                        f"OR branch test: verify rule fires when only "
                        f"{branch_cond.field} {branch_cond.operator} {branch_cond.value} is satisfied"
                    ),
                ))

    return cases


def _gen_negative(
    rule: RuleDefinition,
    resolved_conds: list[tuple[Condition, str]],
    start_counter: int,
) -> list[GeneratedTestCase]:
    """One negative case per condition: violate exactly one condition at a time.

    For 'between' conditions, generates TWO cases: below-range AND above-range.

    OR logic awareness: if conditions are OR'd (e.g., tenure >= 12 OR tenure >= 24),
    violating just one isn't enough — the rule still fires via the other OR branch.
    For OR groups, we generate a single negative test that violates ALL conditions
    in the group simultaneously.
    """
    cases = []
    counter = start_counter

    # Build index mapping: resolved_conds indices ↔ rule.conditions indices
    resolved_to_orig, orig_to_resolved = _build_resolved_index_map(rule, resolved_conds)

    # Identify OR groups so we know which conditions must be violated together
    or_groups = _get_or_groups(rule)
    # Map original condition index → group index
    cond_to_group: dict[int, int] = {}
    or_group_indices: set[int] = set()  # groups with >1 member
    for gi, group in enumerate(or_groups):
        for ci in group:
            cond_to_group[ci] = gi
        if len(group) > 1:
            or_group_indices.add(gi)

    # Track which OR groups we've already generated negative tests for
    processed_or_groups: set[int] = set()

    for idx, (cond, path) in enumerate(resolved_conds):
        # Map resolved index back to original rule.conditions index
        orig_idx = resolved_to_orig.get(idx, -1)
        gi = cond_to_group.get(orig_idx)

        # If this condition is part of an OR group, handle the whole group at once
        if gi is not None and gi in or_group_indices:
            if gi in processed_or_groups:
                continue  # Already generated negative test for this OR group
            processed_or_groups.add(gi)

            # Violate ALL conditions in the OR group simultaneously
            # Map OR group's original indices → resolved_conds entries
            group_conds = []
            for ci in or_groups[gi]:
                ri = orig_to_resolved.get(ci)
                if ri is not None and ri < len(resolved_conds):
                    group_conds.append((resolved_conds[ri], ci))
            overrides = {}
            violated_parts = []
            for (gc, gp), ci in group_conds:
                overrides[gc.field] = _violating_value(gc)
                violated_parts.append(f"{gc.field} {gc.operator} {gc.value}")

            inputs = _build_input_values(rule, overrides=overrides)
            filters = _build_filters(resolved_conds, inputs, keep_range_operators=False)
            expected = _extract_expected_outcome(rule, satisfied=False)
            expected["violated_condition"] = " OR ".join(violated_parts)
            expected["or_group"] = True

            counter += 1
            cases.append(GeneratedTestCase(
                test_case_id=f"TC-{rule.rule_id}-NEG-{counter:03d}",
                description=(
                    f"Violates OR group ({' OR '.join(violated_parts)}) "
                    f"→ {rule.rule_name} should NOT fire"
                ),
                source_rule_ids=[rule.rule_id],
                category=TestCaseCategory.NEGATIVE,
                input_values=inputs,
                filter_logic=filters,
                expected_outcome=expected,
                rationale=(
                    f"OR group: all {len(group_conds)} conditions must be violated "
                    f"simultaneously to prevent rule from firing"
                ),
            ))
            continue
        meta = _get_field_meta(cond.field)
        step = meta.get("step", 1)

        # For 'between', generate both below-range and above-range violations
        if cond.operator == "between" and isinstance(cond.value, (list, tuple)) and len(cond.value) == 2:
            lo, hi = cond.value
            for violation_val, label in [(lo - step, f"below range ({lo})"), (hi + step, f"above range ({hi})")]:
                inputs = _build_input_values(rule, overrides={cond.field: violation_val})
                filters = _build_filters(resolved_conds, inputs, keep_range_operators=False)
                expected = _extract_expected_outcome(rule, satisfied=False)
                expected["violated_condition"] = f"{cond.field} between {cond.value}"

                counter += 1
                cases.append(GeneratedTestCase(
                    test_case_id=f"TC-{rule.rule_id}-NEG-{counter:03d}",
                    description=(
                        f"Violates '{cond.field} between {cond.value}' "
                        f"(set to {violation_val}, {label}) → {rule.rule_name} should NOT fire"
                    ),
                    source_rule_ids=[rule.rule_id],
                    category=TestCaseCategory.NEGATIVE,
                    input_values=inputs,
                    filter_logic=filters,
                    expected_outcome=expected,
                    rationale=f"Isolate condition {idx+1}/{len(resolved_conds)}: {cond.field}={violation_val} is {label}, outside between [{lo}, {hi}]",
                ))
        else:
            # Standard: single violating value
            inputs = _build_input_values(rule, overrides={cond.field: _violating_value(cond)})
            filters = _build_filters(resolved_conds, inputs, keep_range_operators=False)
            expected = _extract_expected_outcome(rule, satisfied=False)
            expected["violated_condition"] = f"{cond.field} {cond.operator} {cond.value}"

            counter += 1
            cases.append(GeneratedTestCase(
                test_case_id=f"TC-{rule.rule_id}-NEG-{counter:03d}",
                description=(
                    f"Violates '{cond.field} {cond.operator} {cond.value}' "
                    f"(set to {inputs[cond.field]}) → {rule.rule_name} should NOT fire"
                ),
                source_rule_ids=[rule.rule_id],
                category=TestCaseCategory.NEGATIVE,
                input_values=inputs,
                filter_logic=filters,
                expected_outcome=expected,
                rationale=f"Isolate condition {idx+1}/{len(resolved_conds)}: verify rule doesn't fire when {cond.field} violates threshold",
            ))

    return cases


def _gen_boundary(
    rule: RuleDefinition,
    resolved_conds: list[tuple[Condition, str]],
    start_counter: int,
) -> list[GeneratedTestCase]:
    """Boundary cases for every numeric condition: at, above, below threshold.

    OR-aware: if a boundary value violates one condition but the rule still fires
    via another OR branch, should_pass is corrected to True.
    """
    cases = []
    counter = start_counter
    has_or = _has_or_logic(rule)

    for cond, path in resolved_conds:
        boundary_vals = _boundary_values(cond)
        if not boundary_vals:
            continue

        for bval, label, should_pass in boundary_vals:
            inputs = _build_input_values(rule, overrides={cond.field: bval})

            # OR-aware correction: if this condition fails but the rule still
            # fires via another OR branch, the test should expect PASS
            if has_or and not should_pass:
                if _rule_fires_with_or(rule, inputs):
                    should_pass = True

            filters = _build_filters(resolved_conds, inputs, keep_range_operators=False)
            expected = _extract_expected_outcome(rule, satisfied=should_pass)
            if not should_pass:
                expected["violated_condition"] = f"{cond.field} {cond.operator} {cond.value}"

            counter += 1
            pass_label = "PASS" if should_pass else "FAIL"
            cases.append(GeneratedTestCase(
                test_case_id=f"TC-{rule.rule_id}-BND-{counter:03d}",
                description=f"Boundary: {cond.field} {label} → {pass_label}",
                source_rule_ids=[rule.rule_id],
                category=TestCaseCategory.BOUNDARY,
                input_values=inputs,
                filter_logic=filters,
                expected_outcome=expected,
                rationale=f"Boundary test: {cond.field}={bval} vs threshold {cond.operator} {cond.value}",
            ))

    return cases


def _gen_edge(
    rule: RuleDefinition,
    resolved_conds: list[tuple[Condition, str]],
    start_counter: int,
) -> list[GeneratedTestCase]:
    """Edge cases: extreme values, zeros, negatives for each numeric condition.

    OR-aware: if an extreme value violates one condition but the rule still fires
    via another OR branch, satisfies is corrected to True.
    """
    cases = []
    counter = start_counter
    has_or = _has_or_logic(rule)

    for cond, path in resolved_conds:
        edge_vals = _edge_values(cond)
        if not edge_vals:
            continue

        for eval_val, label in edge_vals:
            inputs = _build_input_values(rule, overrides={cond.field: eval_val})
            filters = _build_filters(resolved_conds, inputs, keep_range_operators=False)

            # Determine if the extreme value satisfies the condition
            satisfies = _check_satisfies(cond, eval_val)

            # OR-aware correction: if this condition fails but the rule still
            # fires via another OR branch, the test should expect PASS
            if has_or and not satisfies:
                if _rule_fires_with_or(rule, inputs):
                    satisfies = True

            expected = _extract_expected_outcome(rule, satisfied=satisfies)
            if not satisfies:
                expected["violated_condition"] = f"{cond.field} {cond.operator} {cond.value}"
            expected["edge_type"] = label

            counter += 1
            cases.append(GeneratedTestCase(
                test_case_id=f"TC-{rule.rule_id}-EDGE-{counter:03d}",
                description=f"Edge: {cond.field} at {label}",
                source_rule_ids=[rule.rule_id],
                category=TestCaseCategory.EDGE,
                input_values=inputs,
                filter_logic=filters,
                expected_outcome=expected,
                rationale=f"Extreme value test: {cond.field}={eval_val} to verify handling of {label}",
            ))

    return cases


def _get_condition_range(cond: Condition) -> tuple[float, float] | None:
    """Extract the numeric range a condition accepts. Returns (lo, hi) or None."""
    v = cond.value
    op = cond.operator
    meta = _get_field_meta(cond.field)

    if op == "between" and isinstance(v, (list, tuple)) and len(v) == 2:
        return (float(v[0]), float(v[1]))
    if not _is_numeric(v):
        return None
    if op == "==":
        return (float(v), float(v))  # Exact match: range is [v, v]
    if op == ">=":
        return (float(v), float(meta.get("max", 1e9)))
    if op == ">":
        return (float(v) + meta.get("step", 1), float(meta.get("max", 1e9)))
    if op == "<=":
        return (float(meta.get("min", -1e9)), float(v))
    if op == "<":
        return (float(meta.get("min", -1e9)), float(v) - meta.get("step", 1))
    return None


def _effective_field_range(conds: list[Condition]) -> tuple[float, float] | None:
    """Get the effective range for a field with possibly multiple conditions.

    Intersects all condition ranges (AND semantics).
    E.g., '> 30 AND <= 60' → (31, 60)
    """
    ranges = [_get_condition_range(c) for c in conds]
    valid = [r for r in ranges if r is not None]
    if not valid:
        return None
    lo = max(r[0] for r in valid)
    hi = min(r[1] for r in valid)
    if lo <= hi:
        return (lo, hi)
    return None  # Impossible intersection


def _ranges_overlap(r1: tuple[float, float], r2: tuple[float, float]) -> tuple[float, float] | None:
    """Return the overlap of two ranges, or None if disjoint."""
    lo = max(r1[0], r2[0])
    hi = min(r1[1], r2[1])
    if lo <= hi:
        return (lo, hi)
    return None


def _gen_interactions(
    resolved_rules: list[tuple[RuleDefinition, list[tuple[Condition, str]]]],
    max_count: int,
    start_counter: int,
) -> list[GeneratedTestCase]:
    """Interaction cases: inputs that trigger multiple rules simultaneously.

    Finds rule pairs that share fields. For each pair:
    - If conditions on shared fields are compatible (overlapping ranges),
      pick a value that satisfies both → test co-triggering or conflict.
    - Skips trivial interactions:
      - Self-pairs (same rule paired with itself)
      - Tiered thresholds: rules that are mutually exclusive on their ONLY
        shared field (designed as tiers, e.g., >5 reject, 4-5 reduce)
    """
    cases = []
    counter = start_counter

    # Build field → rules index (deduplicated per rule)
    field_rules: dict[str, list[int]] = defaultdict(list)
    for idx, (rule, conds) in enumerate(resolved_rules):
        seen_fields_for_rule: set[str] = set()
        for cond, _ in conds:
            if cond.field not in seen_fields_for_rule:
                field_rules[cond.field].append(idx)
                seen_fields_for_rule.add(cond.field)

    # Find overlapping pairs (skip self-pairs)
    seen_pairs = set()
    pairs = []
    for field, indices in field_rules.items():
        if len(indices) < 2:
            continue
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                if indices[i] == indices[j]:
                    continue  # Skip self-pairs
                pair = (min(indices[i], indices[j]), max(indices[i], indices[j]))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    pairs.append(pair)

    # Sort by potential conflict interest (different action types = more interesting)
    def conflict_score(pair):
        r1 = resolved_rules[pair[0]][0]
        r2 = resolved_rules[pair[1]][0]
        a1 = {a.action_type for a in r1.actions}
        a2 = {a.action_type for a in r2.actions}
        # Bonus for rules with multiple shared fields (cross-dimensional interactions)
        conds_a_fields = {c.field for c, _ in resolved_rules[pair[0]][1]}
        conds_b_fields = {c.field for c, _ in resolved_rules[pair[1]][1]}
        shared_count = len(conds_a_fields & conds_b_fields)
        return len(a1.symmetric_difference(a2)) + shared_count

    pairs.sort(key=conflict_score, reverse=True)

    for idx_a, idx_b in pairs[:max_count]:
        rule_a, conds_a = resolved_rules[idx_a]
        rule_b, conds_b = resolved_rules[idx_b]

        # Determine shared fields and check compatibility
        # Use lists to handle multiple conditions per field per rule
        conds_a_by_field: dict[str, list[Condition]] = defaultdict(list)
        conds_b_by_field: dict[str, list[Condition]] = defaultdict(list)
        for c, _ in conds_a:
            conds_a_by_field[c.field].append(c)
        for c, _ in conds_b:
            conds_b_by_field[c.field].append(c)
        fields_a = set(conds_a_by_field.keys())
        fields_b = set(conds_b_by_field.keys())
        shared = fields_a & fields_b

        # Check if shared field conditions are compatible (overlapping ranges)
        # For multi-condition fields, check per-condition pairwise overlap to handle
        # OR logic correctly (e.g., bureau_score == 0 OR bureau_score == "" should
        # check each condition's range independently, not intersect them)
        mutually_exclusive_fields = []
        compatible = True
        for field in shared:
            a_ranges = [_get_condition_range(c) for c in conds_a_by_field[field]]
            b_ranges = [_get_condition_range(c) for c in conds_b_by_field[field]]
            a_valid = [r for r in a_ranges if r is not None]
            b_valid = [r for r in b_ranges if r is not None]
            if a_valid and b_valid:
                # Check if ANY condition range from A overlaps with ANY from B
                any_overlap = False
                for ra in a_valid:
                    for rb in b_valid:
                        if _ranges_overlap(ra, rb) is not None:
                            any_overlap = True
                            break
                    if any_overlap:
                        break
                if not any_overlap:
                    compatible = False
                    mutually_exclusive_fields.append(field)

        # Skip trivial tiered-threshold interactions: if rules are mutually exclusive
        # on their ONLY shared field, they're designed as tiers — not interesting to test
        if not compatible and len(shared) == len(mutually_exclusive_fields):
            # ALL shared fields are mutually exclusive — these rules can never co-fire
            # Only worth showing if they have multiple shared fields (complex partitioning)
            if len(shared) <= 1:
                logger.debug(
                    "Skipping tiered-threshold interaction: %s vs %s (exclusive on %s)",
                    rule_a.rule_id, rule_b.rule_id, ", ".join(mutually_exclusive_fields),
                )
                continue

        exp_a = _extract_expected_outcome(rule_a, satisfied=True)
        exp_b = _extract_expected_outcome(rule_b, satisfied=True)

        if compatible:
            # Ranges overlap — build a single input that triggers BOTH rules
            inputs = _build_input_values(rule_a)
            # For fields only in rule B, add their satisfying values
            for field, b_conds in conds_b_by_field.items():
                if field in shared:
                    # Shared field: find pairwise overlap between any condition range
                    # from rule A and any condition range from rule B
                    a_ranges = [_get_condition_range(c) for c in conds_a_by_field[field]]
                    b_ranges = [_get_condition_range(c) for c in b_conds]
                    a_valid = [r for r in a_ranges if r is not None]
                    b_valid = [r for r in b_ranges if r is not None]
                    best_overlap = None
                    for ra in a_valid:
                        for rb in b_valid:
                            overlap = _ranges_overlap(ra, rb)
                            if overlap:
                                # Prefer wider overlap (more room for test value)
                                if best_overlap is None or (overlap[1] - overlap[0]) > (best_overlap[1] - best_overlap[0]):
                                    best_overlap = overlap
                    if best_overlap:
                        mid = (best_overlap[0] + best_overlap[1]) / 2
                        meta = _get_field_meta(field)
                        inputs[field] = int(mid) if meta.get("type") == "int" else mid
                        continue
                    # Fallback: keep rule A's value
                else:
                    # Non-shared field: use rule B's satisfying value
                    for cond in b_conds:
                        inputs[field] = _satisfying_value(cond)

            # Verify both rules are actually satisfied (OR-aware)
            if _has_or_logic(rule_a):
                a_satisfied = _rule_fires_with_or(rule_a, inputs)
            else:
                a_satisfied = all(_check_satisfies(c, inputs.get(c.field)) for c, _ in conds_a)
            if _has_or_logic(rule_b):
                b_satisfied = _rule_fires_with_or(rule_b, inputs)
            else:
                b_satisfied = all(_check_satisfies(c, inputs.get(c.field)) for c, _ in conds_b)

            # Build filters — deduplicate shared field conditions, use the input value
            seen_filter_fields = set()
            deduped_conds = []
            for cond, path in conds_a:
                deduped_conds.append((cond, path))
                seen_filter_fields.add(cond.field)
            for cond, path in conds_b:
                if cond.field not in seen_filter_fields:
                    deduped_conds.append((cond, path))
                    seen_filter_fields.add(cond.field)
            filters = _build_filters(deduped_conds, inputs)

            is_conflict = (
                a_satisfied and b_satisfied and (
                    (exp_a.get("decision") == "REJECTED") != (exp_b.get("decision") == "REJECTED")
                )
            )

            decision = "CONFLICT" if is_conflict else "BOTH_TRIGGERED"
            if not a_satisfied or not b_satisfied:
                decision = "PARTIAL_TRIGGER"

            expected = {
                "decision": decision,
                "rule_a": f"{rule_a.rule_id} ({rule_a.rule_name}) → {exp_a.get('decision')}",
                "rule_b": f"{rule_b.rule_id} ({rule_b.rule_name}) → {exp_b.get('decision')}",
                "rule_a_fires": a_satisfied,
                "rule_b_fires": b_satisfied,
                "shared_fields": list(shared),
                "applied_rules": [rule_a.rule_id, rule_b.rule_id],
            }

            counter += 1
            label = "CONFLICTING" if is_conflict else "co-triggered"
            cases.append(GeneratedTestCase(
                test_case_id=f"TC-INT-{counter:03d}",
                description=(
                    f"Interaction ({label}): {rule_a.rule_name} + {rule_b.rule_name} "
                    f"(shared: {', '.join(shared)})"
                ),
                source_rule_ids=[rule_a.rule_id, rule_b.rule_id],
                category=TestCaseCategory.INTERACTION,
                input_values=inputs,
                filter_logic=filters,
                expected_outcome=expected,
                rationale=(
                    f"{'Conflict' if is_conflict else 'Co-trigger'}: "
                    f"both rules share {', '.join(shared)} with overlapping ranges. "
                    f"Rule A fires={a_satisfied} → {exp_a.get('decision')}, "
                    f"Rule B fires={b_satisfied} → {exp_b.get('decision')}"
                ),
            ))
        else:
            # Mutually exclusive — rules can NEVER fire simultaneously
            # Generate one test case showing the boundary between the two rules
            inputs_a = _build_input_values(rule_a)

            # Use rule A's value as the test input (triggers A, not B)
            filters_a = _build_filters(conds_a, inputs_a)

            counter += 1
            expected = {
                "decision": "MUTUALLY_EXCLUSIVE",
                "rule_a": f"{rule_a.rule_id} ({rule_a.rule_name}) → {exp_a.get('decision')}",
                "rule_b": f"{rule_b.rule_id} ({rule_b.rule_name}) → {exp_b.get('decision')}",
                "rule_a_fires": True,
                "rule_b_fires": False,
                "exclusive_fields": mutually_exclusive_fields,
                "shared_fields": list(shared),
                "explanation": (
                    f"Rules cannot fire simultaneously: "
                    f"{', '.join(mutually_exclusive_fields)} has disjoint ranges. "
                    f"Testing with Rule A's range."
                ),
                "applied_rules": [rule_a.rule_id],
            }

            # Build description showing the disjoint ranges
            range_desc_parts = []
            for field in mutually_exclusive_fields:
                ca_list = conds_a_by_field[field]
                cb_list = conds_b_by_field[field]
                a_desc = " AND ".join(f"{c.operator} {c.value}" for c in ca_list)
                b_desc = " AND ".join(f"{c.operator} {c.value}" for c in cb_list)
                range_desc_parts.append(
                    f"{field}: Rule A needs {a_desc}, Rule B needs {b_desc}"
                )

            cases.append(GeneratedTestCase(
                test_case_id=f"TC-INT-{counter:03d}",
                description=(
                    f"Mutually exclusive: {rule_a.rule_name} vs {rule_b.rule_name} "
                    f"(disjoint: {', '.join(mutually_exclusive_fields)})"
                ),
                source_rule_ids=[rule_a.rule_id, rule_b.rule_id],
                category=TestCaseCategory.INTERACTION,
                input_values=inputs_a,
                filter_logic=filters_a,
                expected_outcome=expected,
                rationale=(
                    f"Mutually exclusive rules: {'; '.join(range_desc_parts)}. "
                    f"These rules partition the input space — only one can fire at a time. "
                    f"Input satisfies Rule A → {exp_a.get('decision')}"
                ),
            ))

    return cases


def _check_satisfies(cond: Condition, value: Any) -> bool:
    """Check if a value satisfies a condition."""
    op = cond.operator
    v = cond.value

    # Handle list-based operators first (work for both numeric and string)
    if op == "in":
        if isinstance(v, (list, tuple)):
            return value in v
        return value == v
    elif op == "not_in":
        if isinstance(v, (list, tuple)):
            return value not in v
        return value != v
    elif op == "between":
        if isinstance(v, (list, tuple)) and len(v) == 2:
            if _is_numeric(value) and _is_numeric(v[0]) and _is_numeric(v[1]):
                return v[0] <= value <= v[1]
        return False

    # String/non-numeric comparisons
    if not _is_numeric(value) or not _is_numeric(v):
        if op == "==":
            return value == v
        elif op == "!=":
            return value != v
        return False

    # Numeric comparisons
    if op == ">=":
        return value >= v
    elif op == ">":
        return value > v
    elif op == "<=":
        return value <= v
    elif op == "<":
        return value < v
    elif op == "==":
        return value == v
    elif op == "!=":
        return value != v
    return False


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

def generate_test_cases(
    rules: list[RuleDefinition],
    rule_set_id: str | None = None,
    positive_count: int | None = None,
    negative_count: int | None = None,
    boundary_count: int | None = None,
    edge_count: int | None = None,
    interaction_count: int | None = None,
) -> TestCaseSuiteOutput:
    """Generate comprehensive test cases from rules.

    If counts are None, auto-suggests based on rule complexity.
    If counts are provided, uses them as maximums per category.
    """
    if not rules:
        return TestCaseSuiteOutput(
            rule_set_id=rule_set_id, total_cases=0, cases_by_category={},
            suggested_counts=suggest_counts([]),
        )

    # Auto-suggest if no counts provided
    suggested = suggest_counts(rules)

    # Use suggested counts as defaults, override with explicit counts
    max_positive = positive_count if positive_count is not None else suggested["positive"]
    max_negative = negative_count if negative_count is not None else suggested["negative"]
    max_boundary = boundary_count if boundary_count is not None else suggested["boundary"]
    max_edge = edge_count if edge_count is not None else suggested["edge"]
    max_interaction = interaction_count if interaction_count is not None else suggested["interaction"]

    # Resolve all rule conditions to JSON paths
    resolved_rules: list[tuple[RuleDefinition, list[tuple[Condition, str]]]] = []
    unresolved_fields: set[str] = set()

    for rule in rules:
        resolved_conditions = []
        for cond in rule.conditions:
            path = resolve_field_path(cond.field)
            if path:
                resolved_conditions.append((cond, path))
            else:
                unresolved_fields.add(cond.field)
                logger.warning("Could not resolve field '%s' for rule %s", cond.field, rule.rule_id)
        if resolved_conditions:
            resolved_rules.append((rule, resolved_conditions))

    if not resolved_rules:
        return TestCaseSuiteOutput(
            rule_set_id=rule_set_id, total_cases=0, cases_by_category={},
            suggested_counts=suggested,
        )

    logger.info(
        "Generating test cases for %d rules (%d resolved, %d unresolved fields)",
        len(rules), len(resolved_rules), len(unresolved_fields),
    )

    all_cases: list[GeneratedTestCase] = []
    rules_covered: set[str] = set()
    conditions_covered: set[str] = set()

    # --- POSITIVE: 1 per rule (up to max_positive) ---
    pos_counter = 0
    for rule, conds in resolved_rules:
        if pos_counter >= max_positive:
            break
        pos_counter += 1
        cases = _gen_positive(rule, conds, pos_counter)
        all_cases.extend(cases)
        rules_covered.add(rule.rule_id)

    # --- NEGATIVE: 1 per condition per rule (up to max_negative) ---
    neg_total = 0
    for rule, conds in resolved_rules:
        if neg_total >= max_negative:
            break
        remaining = max_negative - neg_total
        cases = _gen_negative(rule, conds, neg_total)
        # Trim to remaining budget
        cases = cases[:remaining]
        all_cases.extend(cases)
        neg_total += len(cases)
        for c in cases:
            conditions_covered.add(f"{rule.rule_id}:{c.expected_outcome.get('violated_condition', '')}")

    # --- BOUNDARY: per numeric condition (up to max_boundary) ---
    bnd_total = 0
    for rule, conds in resolved_rules:
        if bnd_total >= max_boundary:
            break
        remaining = max_boundary - bnd_total
        cases = _gen_boundary(rule, conds, bnd_total)
        cases = cases[:remaining]
        all_cases.extend(cases)
        bnd_total += len(cases)

    # --- EDGE: per numeric condition (up to max_edge) ---
    edge_total = 0
    for rule, conds in resolved_rules:
        if edge_total >= max_edge:
            break
        remaining = max_edge - edge_total
        cases = _gen_edge(rule, conds, edge_total)
        cases = cases[:remaining]
        all_cases.extend(cases)
        edge_total += len(cases)

    # --- INTERACTION: overlapping/conflicting rules ---
    interaction_cases = _gen_interactions(resolved_rules, max_interaction, 0)
    all_cases.extend(interaction_cases)

    # Build category counts
    cats: dict[str, int] = {}
    for tc in all_cases:
        cats[tc.category.value] = cats.get(tc.category.value, 0) + 1

    # Coverage statistics
    total_conditions_count = sum(len(r.conditions) for r in rules)
    resolved_conditions_count = sum(len(conds) for _, conds in resolved_rules)
    coverage = {
        "total_rules": len(rules),
        "rules_with_test_cases": len(rules_covered),
        "rules_skipped": len(rules) - len(resolved_rules),
        "rule_coverage_pct": round(len(rules_covered) / len(rules) * 100, 1) if rules else 0,
        "total_conditions": total_conditions_count,
        "resolved_conditions": resolved_conditions_count,
        "conditions_tested_negative": len(conditions_covered),
        "field_resolution_rate": round(
            resolved_conditions_count / total_conditions_count * 100, 1
        ) if total_conditions_count else 100.0,
        "unresolved_fields": sorted(unresolved_fields),
        "unresolved_field_count": len(unresolved_fields),
    }

    if unresolved_fields:
        logger.warning(
            "Field registry gaps: %d unresolved fields (%s). "
            "These conditions are excluded from test generation. "
            "Add mappings to FIELD_REGISTRY in field_registry.py to fix.",
            len(unresolved_fields),
            ", ".join(sorted(unresolved_fields)),
        )

    logger.info(
        "Generated %d test cases: %s (coverage: %d/%d rules = %.1f%%)",
        len(all_cases),
        ", ".join(f"{k}={v}" for k, v in cats.items()),
        len(rules_covered), len(rules), coverage["rule_coverage_pct"],
    )

    # Sort: by category order (POSITIVE → NEGATIVE → BOUNDARY → EDGE → INTERACTION),
    # then by test_case_id within each category for clean sequential output
    category_order = {
        TestCaseCategory.POSITIVE: 0,
        TestCaseCategory.NEGATIVE: 1,
        TestCaseCategory.BOUNDARY: 2,
        TestCaseCategory.EDGE: 3,
        TestCaseCategory.INTERACTION: 4,
    }
    all_cases.sort(key=lambda tc: (category_order.get(tc.category, 99), tc.test_case_id))

    return TestCaseSuiteOutput(
        rule_set_id=rule_set_id,
        total_cases=len(all_cases),
        cases_by_category=cats,
        test_cases=all_cases,
        coverage_stats=coverage,
        suggested_counts=suggested,
    )
