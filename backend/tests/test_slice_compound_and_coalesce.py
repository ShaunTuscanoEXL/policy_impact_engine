"""Regression: when the LLM splits a compound AND rule into N rules with
the same SET action, _coalesce_compound_and_rules merges them back.

The Repeat Customer BRD case that prompted this:
    "A repeat customer is 'Good' if ALL the following are satisfied:
       - repeat_type = REPEAT
       - debt_to_income_ratio <= 0.20
       - net_monthly_surplus > 0
       - salary_credit_consistency_6m > 0.75
       - overdue_accounts = 0"

The LLM emitted 5 separate rules each with one condition and
`SET good_customer_flag = True`. The engine treats N independent rules
as OR — any one firing sets the flag — which inverts the BRD's
semantics. The coalescer merges them into one rule with 5 AND
conditions and a single SET action, so the flag is only set when ALL
hold.
"""
from __future__ import annotations

import pytest

from app.pipeline.rule_extractor import _coalesce_compound_and_rules
from app.schemas.rule import Action, Condition, RuleDefinition, RuleTypeEnum


def _cond(field, op, value):
    return Condition(field=field, operator=op, value=value, logic="AND")


def _set_action(target, value):
    return Action(
        action_type="SET",
        target_field=target,
        value=value,
        description=f"set {target}",
    )


def _rule(rid, cond, action, *, source="Section 2", confidence=0.95):
    return RuleDefinition(
        rule_id=rid,
        rule_name=f"Rule {rid}",
        description="",
        rule_type=RuleTypeEnum.ELIGIBILITY,
        conditions=[cond],
        actions=[action],
        priority=0,
        source_section=source,
        confidence=confidence,
    )


# ── The actual Repeat Customer BRD pattern ─────────────────────────────


def test_good_customer_flag_split_coalesces_into_one_AND_rule():
    """The exact pattern that prompted this fix — 5 rules each setting
    good_customer_flag=True become 1 rule with 5 AND conditions."""
    rules = [
        _rule("R1", _cond("repeat_type", "==", "REPEAT"),
              _set_action("good_customer_flag", True)),
        _rule("R2", _cond("dti_ratio", "<=", 0.20),
              _set_action("good_customer_flag", True)),
        _rule("R3", _cond("net_monthly_surplus", ">", 0),
              _set_action("good_customer_flag", True)),
        _rule("R4", _cond("salary_credit_consistency_6m", ">", 0.75),
              _set_action("good_customer_flag", True)),
        _rule("R5", _cond("overdue_accounts", "==", 0),
              _set_action("good_customer_flag", True)),
    ]
    out = _coalesce_compound_and_rules(rules)
    assert len(out) == 1, (
        f"Expected 5 rules to coalesce into 1 compound AND rule, got {len(out)}"
    )
    merged = out[0]
    assert len(merged.conditions) == 5
    # Every condition must use logic=AND (the whole point of the coalesce)
    for c in merged.conditions:
        assert (c.logic or "AND").upper() == "AND"
    # All 5 original fields preserved
    fields = {c.field for c in merged.conditions}
    assert fields == {
        "repeat_type", "dti_ratio", "net_monthly_surplus",
        "salary_credit_consistency_6m", "overdue_accounts",
    }
    # Exactly one SET action
    assert len(merged.actions) == 1
    assert merged.actions[0].target_field == "good_customer_flag"
    assert merged.actions[0].value is True


# ── Cases that must NOT coalesce (conservative heuristic) ──────────────


def test_does_not_coalesce_rules_writing_different_values_to_same_target():
    """RULE-013 SET max_tenure_months=72 (segment A) vs RULE-014 SET
    max_tenure_months=60 (segment B) — same target, different values,
    independent rules. MUST NOT collapse."""
    rules = [
        _rule("R-A", _cond("customer_segment", "==", "SEGMENT_A"),
              _set_action("max_tenure_months", 72)),
        _rule("R-B", _cond("customer_segment", "==", "SEGMENT_B"),
              _set_action("max_tenure_months", 60)),
    ]
    out = _coalesce_compound_and_rules(rules)
    assert len(out) == 2, (
        f"Tier rules with different values must stay independent, got {len(out)}"
    )


def test_does_not_coalesce_rules_with_different_action_types():
    """REJECT and FLAG actions are gates — even if they share a target
    they're legitimately independent. Only SET actions coalesce."""
    from app.schemas.rule import Action
    rule_reject = _rule("R-R", _cond("bureau_score", "<", 600),
                        Action(action_type="REJECT", target_field="decision_status",
                               value="REJECTED", description=""))
    rule_flag = _rule("R-F", _cond("inquiries_last_3m", ">", 5),
                      Action(action_type="FLAG", target_field="decision_status",
                             value="MANUAL_REVIEW", description=""))
    out = _coalesce_compound_and_rules([rule_reject, rule_flag])
    assert len(out) == 2


def test_does_not_coalesce_rules_from_different_sections():
    """Two SET rules with same target+value but from different BRD
    sections almost always describe different concepts — don't merge."""
    rules = [
        _rule("R1", _cond("repeat_type", "==", "REPEAT"),
              _set_action("eligibility_flag", True),
              source="Section 2 — Repeat Customers"),
        _rule("R2", _cond("employment_type", "==", "W2"),
              _set_action("eligibility_flag", True),
              source="Section 5 — Employment Verification"),
    ]
    out = _coalesce_compound_and_rules(rules)
    assert len(out) == 2


def test_does_not_coalesce_multi_condition_rules():
    """If the input rules already have multiple conditions, they're
    already compound — leave them alone."""
    multi = RuleDefinition(
        rule_id="R-MULTI", rule_name="x", description="",
        rule_type=RuleTypeEnum.ELIGIBILITY,
        conditions=[
            _cond("repeat_type", "==", "REPEAT"),
            _cond("dti_ratio", "<=", 0.2),
        ],
        actions=[_set_action("good_customer_flag", True)],
        priority=0, source_section="Section 2", confidence=0.95,
    )
    single = _rule("R-SINGLE", _cond("overdue_accounts", "==", 0),
                   _set_action("good_customer_flag", True))
    out = _coalesce_compound_and_rules([multi, single])
    # Multi-condition rule passes through; single one comes through too
    # (singletons in their group can't coalesce alone).
    assert len(out) == 2


def test_singleton_does_not_self_coalesce():
    """A single rule isn't a group — pass through unchanged."""
    rules = [_rule("R1", _cond("repeat_type", "==", "REPEAT"),
                   _set_action("good_customer_flag", True))]
    out = _coalesce_compound_and_rules(rules)
    assert len(out) == 1
    assert out[0].rule_id == "R1"  # untouched


def test_empty_input_passes_through():
    assert _coalesce_compound_and_rules([]) == []


def test_coalesced_rule_lowers_confidence_to_minimum_of_members():
    """Coalescing adds interpretive risk — confidence should reflect
    the LEAST-confident input."""
    rules = [
        _rule("R1", _cond("a", "==", 1), _set_action("flag", True), confidence=0.95),
        _rule("R2", _cond("b", "==", 2), _set_action("flag", True), confidence=0.72),
    ]
    out = _coalesce_compound_and_rules(rules)
    assert len(out) == 1
    assert out[0].confidence == 0.72


def test_coalesced_rule_records_original_ids_in_description():
    """Audit trail: the merged description must name every constituent
    rule_id so reviewers can trace back to the LLM's split."""
    rules = [
        _rule("R-A", _cond("a", "==", 1), _set_action("flag", True)),
        _rule("R-B", _cond("b", "==", 2), _set_action("flag", True)),
        _rule("R-C", _cond("c", "==", 3), _set_action("flag", True)),
    ]
    out = _coalesce_compound_and_rules(rules)
    assert len(out) == 1
    desc = out[0].description
    assert "R-A" in desc and "R-B" in desc and "R-C" in desc
    assert "3" in desc  # references the count of merged rules
