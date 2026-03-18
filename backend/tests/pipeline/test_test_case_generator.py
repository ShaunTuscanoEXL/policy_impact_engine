"""Tests for the test case generation engine."""

import pytest
import pandas as pd

from app.schemas.rule import RuleDefinition, Condition, Action
from app.pipeline.rule_compiler import compile_rules
from app.pipeline.test_case_generator import (
    generate_test_cases,
    TestCaseCategory,
    TestCaseSuiteOutput,
    GeneratedTestCase,
)
from app.simulation.baseline import apply_baseline


def _make_rule(
    rule_id: str,
    conditions: list[dict],
    actions: list[dict],
    priority: int = 0,
) -> RuleDefinition:
    """Helper to create a RuleDefinition from simple dicts."""
    return RuleDefinition(
        rule_id=rule_id,
        rule_name=f"Test Rule {rule_id}",
        description=f"Test rule {rule_id}",
        rule_type="ELIGIBILITY",
        conditions=[Condition(**c) for c in conditions],
        actions=[Action(**a) for a in actions],
        priority=priority,
    )


# Standard REJECT action for testing
REJECT_ACTION = {
    "action_type": "REJECT",
    "target_field": "decision_status",
    "value": "REJECTED",
    "description": "Reject applicant",
}


def _simple_bureau_rule() -> RuleDefinition:
    """A single rule: bureau_score >= 700 -> REJECT."""
    return _make_rule(
        rule_id="R001",
        conditions=[{"field": "bureau_score", "operator": ">=", "value": 700}],
        actions=[REJECT_ACTION],
    )


def _run_generation(rules: list[RuleDefinition]) -> TestCaseSuiteOutput:
    """Compile rules and generate the full test-case suite."""
    compiled = compile_rules(rules)
    return generate_test_cases(compiled, rules)


def _cases_of(suite: TestCaseSuiteOutput, cat: TestCaseCategory) -> list[GeneratedTestCase]:
    """Return only cases matching the given category."""
    return [tc for tc in suite.test_cases if tc.category == cat]


# -----------------------------------------------------------------------
# 1. Positive cases
# -----------------------------------------------------------------------
class TestGeneratePositiveCases:
    def test_at_least_one_positive_case(self):
        suite = _run_generation([_simple_bureau_rule()])
        positives = _cases_of(suite, TestCaseCategory.POSITIVE)
        assert len(positives) >= 1

    def test_positive_case_satisfies_condition(self):
        suite = _run_generation([_simple_bureau_rule()])
        positives = _cases_of(suite, TestCaseCategory.POSITIVE)
        # The positive case should have bureau_score >= 700
        for tc in positives:
            assert tc.inputs["bureau_score"] >= 700

    def test_positive_case_has_decision(self):
        suite = _run_generation([_simple_bureau_rule()])
        positives = _cases_of(suite, TestCaseCategory.POSITIVE)
        for tc in positives:
            assert "decision" in tc.expected_outcome
            assert tc.expected_outcome["decision"] != ""


# -----------------------------------------------------------------------
# 2. Negative cases
# -----------------------------------------------------------------------
class TestGenerateNegativeCases:
    def test_at_least_one_negative_case(self):
        suite = _run_generation([_simple_bureau_rule()])
        negatives = _cases_of(suite, TestCaseCategory.NEGATIVE)
        assert len(negatives) >= 1

    def test_negative_case_violates_condition(self):
        suite = _run_generation([_simple_bureau_rule()])
        negatives = _cases_of(suite, TestCaseCategory.NEGATIVE)
        # At least one negative case should have bureau_score < 700
        violated = [tc for tc in negatives if tc.inputs["bureau_score"] < 700]
        assert len(violated) >= 1


# -----------------------------------------------------------------------
# 3. Boundary cases
# -----------------------------------------------------------------------
class TestGenerateBoundaryCases:
    def test_boundary_cases_exist(self):
        suite = _run_generation([_simple_bureau_rule()])
        boundaries = _cases_of(suite, TestCaseCategory.BOUNDARY)
        assert len(boundaries) >= 1

    def test_boundary_values_around_threshold(self):
        suite = _run_generation([_simple_bureau_rule()])
        boundaries = _cases_of(suite, TestCaseCategory.BOUNDARY)
        scores = [tc.inputs["bureau_score"] for tc in boundaries]
        # For >= 700, boundary generator creates v-1, v, v+1 = 699, 700, 701
        assert 699 in scores
        assert 700 in scores
        assert 701 in scores


# -----------------------------------------------------------------------
# 4. Edge cases
# -----------------------------------------------------------------------
class TestGenerateEdgeCases:
    def test_edge_cases_exist(self):
        suite = _run_generation([_simple_bureau_rule()])
        edges = _cases_of(suite, TestCaseCategory.EDGE)
        assert len(edges) >= 1

    def test_edge_cases_contain_extremes(self):
        suite = _run_generation([_simple_bureau_rule()])
        edges = _cases_of(suite, TestCaseCategory.EDGE)
        scores = [tc.inputs["bureau_score"] for tc in edges]
        # Edge generator creates all-zeros (0) and extreme-highs (999)
        assert 0 in scores
        assert 999 in scores


# -----------------------------------------------------------------------
# 5. Interaction cases
# -----------------------------------------------------------------------
class TestGenerateInteractionCases:
    def test_interaction_case_exists_for_shared_field(self):
        rule1 = _make_rule(
            rule_id="R001",
            conditions=[{"field": "bureau_score", "operator": ">=", "value": 700}],
            actions=[REJECT_ACTION],
        )
        rule2 = _make_rule(
            rule_id="R002",
            conditions=[{"field": "bureau_score", "operator": ">=", "value": 750}],
            actions=[REJECT_ACTION],
            priority=1,
        )
        suite = _run_generation([rule1, rule2])
        interactions = _cases_of(suite, TestCaseCategory.INTERACTION)
        assert len(interactions) >= 1

    def test_interaction_case_references_both_rules(self):
        rule1 = _make_rule(
            rule_id="R001",
            conditions=[{"field": "bureau_score", "operator": ">=", "value": 700}],
            actions=[REJECT_ACTION],
        )
        rule2 = _make_rule(
            rule_id="R002",
            conditions=[{"field": "bureau_score", "operator": ">=", "value": 750}],
            actions=[REJECT_ACTION],
            priority=1,
        )
        suite = _run_generation([rule1, rule2])
        interactions = _cases_of(suite, TestCaseCategory.INTERACTION)
        for tc in interactions:
            assert len(tc.source_rule_ids) == 2


# -----------------------------------------------------------------------
# 6. Expected outcome consistency
# -----------------------------------------------------------------------
class TestExpectedOutcomeConsistency:
    def test_outcome_matches_manual_evaluation(self):
        rule_def = _simple_bureau_rule()
        rules = [rule_def]
        compiled = compile_rules(rules)
        suite = generate_test_cases(compiled, rules)

        # Pick the first positive case
        positives = _cases_of(suite, TestCaseCategory.POSITIVE)
        assert len(positives) >= 1
        tc = positives[0]

        # Manually reproduce the outcome
        df = pd.DataFrame([tc.inputs])
        for col, default in {
            "bureau_score": 750, "monthly_income": 60000,
            "desired_amount": 200000, "dti_ratio": 0.30,
        }.items():
            if col not in df.columns:
                df[col] = default

        df = apply_baseline(df)
        df["sim_decision"] = df["baseline_decision"]
        df["sim_eligible_amount"] = df["baseline_eligible_amount"]
        df["sim_interest_rate"] = df["baseline_interest_rate"]

        for rule in sorted(compiled, key=lambda r: r.priority):
            mask = rule.evaluate(df)
            if mask.any():
                df = rule.apply(df, mask)

        row = df.iloc[0]
        assert tc.expected_outcome["decision"] == str(row["sim_decision"])
        assert tc.expected_outcome["eligible_amount"] == pytest.approx(
            float(row["sim_eligible_amount"]), abs=0.01
        )
        assert tc.expected_outcome["interest_rate"] == pytest.approx(
            float(row["sim_interest_rate"]), abs=0.001
        )


# -----------------------------------------------------------------------
# 7. Empty rules
# -----------------------------------------------------------------------
class TestEmptyRules:
    def test_empty_rules_produce_no_cases(self):
        suite = _run_generation([])
        assert suite.total_cases == 0
        assert len(suite.test_cases) == 0


# -----------------------------------------------------------------------
# 8. Multiple conditions
# -----------------------------------------------------------------------
class TestMultipleConditions:
    def _three_condition_rule(self) -> RuleDefinition:
        return _make_rule(
            rule_id="R100",
            conditions=[
                {"field": "bureau_score", "operator": ">=", "value": 700},
                {"field": "dti_ratio", "operator": "<=", "value": 0.40},
                {"field": "monthly_income", "operator": ">=", "value": 25000},
            ],
            actions=[REJECT_ACTION],
        )

    def test_positive_satisfies_all_conditions(self):
        rule = self._three_condition_rule()
        suite = _run_generation([rule])
        positives = _cases_of(suite, TestCaseCategory.POSITIVE)
        assert len(positives) >= 1
        for tc in positives:
            assert tc.inputs["bureau_score"] >= 700
            assert tc.inputs["dti_ratio"] <= 0.40
            assert tc.inputs["monthly_income"] >= 25000

    def test_negative_violates_one_condition_at_a_time(self):
        rule = self._three_condition_rule()
        suite = _run_generation([rule])
        negatives = _cases_of(suite, TestCaseCategory.NEGATIVE)
        # Should have one negative case per condition = 3
        assert len(negatives) >= 3

        violated_fields = set()
        for tc in negatives:
            if tc.inputs["bureau_score"] < 700:
                violated_fields.add("bureau_score")
            if tc.inputs["dti_ratio"] > 0.40:
                violated_fields.add("dti_ratio")
            if tc.inputs["monthly_income"] < 25000:
                violated_fields.add("monthly_income")
        # Each condition should have been violated individually
        assert "bureau_score" in violated_fields
        assert "dti_ratio" in violated_fields
        assert "monthly_income" in violated_fields

    def test_multiple_conditions_produce_extra_positive_variant(self):
        """Rules with >2 conditions should produce a second positive variant."""
        rule = self._three_condition_rule()
        suite = _run_generation([rule])
        positives = _cases_of(suite, TestCaseCategory.POSITIVE)
        assert len(positives) >= 2


# -----------------------------------------------------------------------
# 9. Suite output structure
# -----------------------------------------------------------------------
class TestSuiteOutputStructure:
    def test_total_cases_matches_list_length(self):
        suite = _run_generation([_simple_bureau_rule()])
        assert suite.total_cases == len(suite.test_cases)

    def test_cases_by_category_sums_to_total(self):
        suite = _run_generation([_simple_bureau_rule()])
        assert sum(suite.cases_by_category.values()) == suite.total_cases

    def test_cases_by_category_keys(self):
        suite = _run_generation([_simple_bureau_rule()])
        # Single-rule suite should have at least POSITIVE, NEGATIVE, BOUNDARY, EDGE
        assert "POSITIVE" in suite.cases_by_category
        assert "NEGATIVE" in suite.cases_by_category
        assert "BOUNDARY" in suite.cases_by_category
        assert "EDGE" in suite.cases_by_category

    def test_cases_by_category_counts_match(self):
        suite = _run_generation([_simple_bureau_rule()])
        for cat_name, count in suite.cases_by_category.items():
            actual = len([tc for tc in suite.test_cases if tc.category.value == cat_name])
            assert actual == count

    def test_suite_has_rule_set_id(self):
        suite = _run_generation([_simple_bureau_rule()])
        # rule_set_id defaults to None
        assert isinstance(suite, TestCaseSuiteOutput)
        assert suite.rule_set_id is None
