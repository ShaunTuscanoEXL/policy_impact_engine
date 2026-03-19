"""Test case generator for loan DB matching.

Generates test cases from extracted rules by:
1. Mapping rule conditions to JSON paths in loan record request_payload
2. Building filter conditions for each test case category
3. NOT running simulation — just creates filter logic for DB querying
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from app.schemas.rule import RuleDefinition, Condition
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
    field_name: str  # Original rule field name
    json_path: str  # Resolved path in request_payload
    operator: str  # >=, <=, ==, !=, >, <
    value: any  # Threshold value
    description: str = ""  # Human-readable description

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "json_path": self.json_path,
            "operator": self.operator,
            "value": self.value,
            "description": self.description,
        }

    def to_human_readable(self) -> str:
        return f"{self.field_name} {self.operator} {self.value}"


@dataclass
class GeneratedTestCase:
    test_case_id: str
    description: str
    source_rule_ids: list[str]
    filter_logic: list[dict]  # List of FilterCondition dicts
    expected_outcome: dict  # What we expect from rules (APPROVED/REJECTED/etc.)
    category: TestCaseCategory

    def filter_description(self) -> str:
        """Human-readable description of all filters."""
        parts = [f["description"] or f"{f['field_name']} {f['operator']} {f['value']}" for f in self.filter_logic]
        return " AND ".join(parts)


@dataclass
class TestCaseSuiteOutput:
    rule_set_id: str | None
    total_cases: int
    cases_by_category: dict
    test_cases: list[GeneratedTestCase] = field(default_factory=list)


def generate_test_cases(
    rules: list[RuleDefinition],
    rule_set_id: str | None = None,
    positive_count: int = 3,
    negative_count: int = 3,
    boundary_count: int = 5,
    edge_count: int = 3,
    interaction_count: int = 2,
) -> TestCaseSuiteOutput:
    """Generate test cases from rules with configurable counts per category."""
    if not rules:
        return TestCaseSuiteOutput(rule_set_id=rule_set_id, total_cases=0, cases_by_category={})

    all_cases: list[GeneratedTestCase] = []
    case_counter = 0

    # Resolve all rule conditions to JSON paths
    resolved_rules = []
    for rule in rules:
        resolved_conditions = []
        for cond in rule.conditions:
            path = resolve_field_path(cond.field)
            if path:
                resolved_conditions.append((cond, path))
            else:
                logger.warning(f"Could not resolve field '{cond.field}' for rule {rule.rule_id}")
        if resolved_conditions:
            resolved_rules.append((rule, resolved_conditions))

    if not resolved_rules:
        return TestCaseSuiteOutput(rule_set_id=rule_set_id, total_cases=0, cases_by_category={})

    # Generate POSITIVE cases — all conditions satisfied
    for i in range(min(positive_count, len(resolved_rules))):
        rule, conditions = resolved_rules[i % len(resolved_rules)]
        case_counter += 1
        filters = []
        for cond, path in conditions:
            filters.append(FilterCondition(
                field_name=cond.field,
                json_path=path,
                operator=cond.operator,
                value=cond.value,
                description=f"{cond.field} {cond.operator} {cond.value}",
            ).to_dict())

        # Determine expected outcome from rule actions
        expected = _extract_expected_outcome(rule, satisfied=True)

        all_cases.append(GeneratedTestCase(
            test_case_id=f"TC-POS-{case_counter:03d}",
            description=f"All conditions satisfied for rule: {rule.rule_name}",
            source_rule_ids=[rule.rule_id],
            filter_logic=filters,
            expected_outcome=expected,
            category=TestCaseCategory.POSITIVE,
        ))

    # Generate NEGATIVE cases — one condition violated
    neg_counter = 0
    for rule, conditions in resolved_rules:
        for cond, path in conditions:
            if neg_counter >= negative_count:
                break
            neg_counter += 1
            case_counter += 1

            # Invert the operator for this condition
            inv_op, inv_val = _invert_condition(cond.operator, cond.value)
            filters = [FilterCondition(
                field_name=cond.field,
                json_path=path,
                operator=inv_op,
                value=inv_val,
                description=f"{cond.field} {inv_op} {inv_val} (violates {cond.operator} {cond.value})",
            ).to_dict()]

            expected = _extract_expected_outcome(rule, satisfied=False)

            all_cases.append(GeneratedTestCase(
                test_case_id=f"TC-NEG-{neg_counter:03d}",
                description=f"Violates condition '{cond.field} {cond.operator} {cond.value}' of rule: {rule.rule_name}",
                source_rule_ids=[rule.rule_id],
                filter_logic=filters,
                expected_outcome=expected,
                category=TestCaseCategory.NEGATIVE,
            ))
        if neg_counter >= negative_count:
            break

    # Generate BOUNDARY cases — values at exact thresholds
    bnd_counter = 0
    for rule, conditions in resolved_rules:
        for cond, path in conditions:
            if not isinstance(cond.value, (int, float)):
                continue
            if bnd_counter >= boundary_count:
                break

            # At threshold
            bnd_counter += 1
            case_counter += 1
            filters = [FilterCondition(
                field_name=cond.field,
                json_path=path,
                operator="==",
                value=cond.value,
                description=f"{cond.field} exactly at threshold {cond.value}",
            ).to_dict()]
            all_cases.append(GeneratedTestCase(
                test_case_id=f"TC-BND-{bnd_counter:03d}",
                description=f"Boundary: {cond.field} at exact threshold {cond.value}",
                source_rule_ids=[rule.rule_id],
                filter_logic=filters,
                expected_outcome=_extract_expected_outcome(rule, satisfied=True),
                category=TestCaseCategory.BOUNDARY,
            ))

            # Just below/above threshold
            if bnd_counter < boundary_count:
                bnd_counter += 1
                case_counter += 1
                delta = 1 if isinstance(cond.value, int) else 0.01
                near_val = cond.value - delta if cond.operator in (">=", ">") else cond.value + delta
                near_op = "<" if cond.operator in (">=", ">") else ">"
                filters = [FilterCondition(
                    field_name=cond.field,
                    json_path=path,
                    operator=near_op,
                    value=cond.value,
                    description=f"{cond.field} just {'below' if near_op == '<' else 'above'} threshold {cond.value}",
                ).to_dict()]
                all_cases.append(GeneratedTestCase(
                    test_case_id=f"TC-BND-{bnd_counter:03d}",
                    description=f"Boundary: {cond.field} near threshold {cond.value} (value ~{near_val})",
                    source_rule_ids=[rule.rule_id],
                    filter_logic=filters,
                    expected_outcome=_extract_expected_outcome(rule, satisfied=False),
                    category=TestCaseCategory.BOUNDARY,
                ))
        if bnd_counter >= boundary_count:
            break

    # Generate EDGE cases — extreme values
    edge_counter = 0
    for rule, conditions in resolved_rules:
        for cond, path in conditions:
            if not isinstance(cond.value, (int, float)):
                continue
            if edge_counter >= edge_count:
                break
            edge_counter += 1
            case_counter += 1

            # Use extreme low value (0 or near-zero)
            filters = [FilterCondition(
                field_name=cond.field,
                json_path=path,
                operator="<=",
                value=_get_extreme_low(cond.field),
                description=f"{cond.field} at extreme low value",
            ).to_dict()]
            all_cases.append(GeneratedTestCase(
                test_case_id=f"TC-EDGE-{edge_counter:03d}",
                description=f"Edge case: {cond.field} at extreme low",
                source_rule_ids=[rule.rule_id],
                filter_logic=filters,
                expected_outcome=_extract_expected_outcome(rule, satisfied=False),
                category=TestCaseCategory.EDGE,
            ))
        if edge_counter >= edge_count:
            break

    # Generate INTERACTION cases — cross-rule combinations
    int_counter = 0
    if len(resolved_rules) >= 2:
        for i in range(len(resolved_rules)):
            for j in range(i + 1, len(resolved_rules)):
                if int_counter >= interaction_count:
                    break
                rule_a, conds_a = resolved_rules[i]
                rule_b, conds_b = resolved_rules[j]

                # Check if they share any fields
                fields_a = {c.field for c, _ in conds_a}
                fields_b = {c.field for c, _ in conds_b}
                shared = fields_a & fields_b

                if shared:
                    int_counter += 1
                    case_counter += 1
                    # Combine all conditions from both rules
                    filters = []
                    for cond, path in conds_a + conds_b:
                        filters.append(FilterCondition(
                            field_name=cond.field,
                            json_path=path,
                            operator=cond.operator,
                            value=cond.value,
                            description=f"{cond.field} {cond.operator} {cond.value}",
                        ).to_dict())

                    all_cases.append(GeneratedTestCase(
                        test_case_id=f"TC-INT-{int_counter:03d}",
                        description=f"Interaction: rules {rule_a.rule_id} + {rule_b.rule_id} (shared: {', '.join(shared)})",
                        source_rule_ids=[rule_a.rule_id, rule_b.rule_id],
                        filter_logic=filters,
                        expected_outcome={"decision": "REQUIRES_ANALYSIS", "reason": "Multiple rules interact"},
                        category=TestCaseCategory.INTERACTION,
                    ))
            if int_counter >= interaction_count:
                break

    # Build category counts
    cats = {}
    for tc in all_cases:
        cats[tc.category.value] = cats.get(tc.category.value, 0) + 1

    return TestCaseSuiteOutput(
        rule_set_id=rule_set_id,
        total_cases=len(all_cases),
        cases_by_category=cats,
        test_cases=all_cases,
    )


def _extract_expected_outcome(rule: RuleDefinition, satisfied: bool) -> dict:
    """Extract expected outcome from rule actions."""
    outcome = {"decision": "UNKNOWN", "applied_rules": [], "flags": []}

    if not satisfied:
        # If condition is NOT met, the rule doesn't fire
        outcome["decision"] = "RULE_NOT_TRIGGERED"
        return outcome

    for action in rule.actions:
        if action.action_type == "REJECT":
            outcome["decision"] = "REJECTED"
            outcome["reject_reason"] = action.description
        elif action.action_type == "SET":
            if action.target_field == "decision_status":
                outcome["decision"] = action.value
            else:
                outcome[action.target_field] = action.value
        elif action.action_type == "FLAG":
            outcome["flags"].append(action.value)
        elif action.action_type == "ADJUST":
            outcome[action.target_field] = action.value
        outcome["applied_rules"].append(rule.rule_id)

    if outcome["decision"] == "UNKNOWN" and any(a.action_type != "FLAG" for a in rule.actions):
        outcome["decision"] = "MODIFIED"

    return outcome


def _invert_condition(operator: str, value) -> tuple[str, any]:
    """Invert a condition operator for negative test cases."""
    inversions = {
        ">=": "<",
        "<=": ">",
        ">": "<=",
        "<": ">=",
        "==": "!=",
        "!=": "==",
    }
    return inversions.get(operator, operator), value


def _get_extreme_low(field_name: str) -> int | float:
    """Get a sensible extreme low value for a field."""
    # Fields that should be 0 at extreme
    zero_fields = {"bureau_score", "monthly_income", "desired_amount", "age",
                   "employment_tenure_months", "account_vintage_months"}
    normalized = field_name.lower().replace(" ", "_")
    if normalized in zero_fields:
        return 0
    # Ratio fields
    if "ratio" in normalized or "score" in normalized or "index" in normalized:
        return 0.0
    return 0
