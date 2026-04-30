"""Pin the tier-rule fan-out post-processor in the rule extractor.

Born of a real-world bug: the LLM read a tiered pricing table from a
BRD and emitted ONE rule with four OR'd `bureau_score` conditions and
four `SET interest_rate` actions. The engine would happily fire all
four SET actions on every matched loan and just keep the last value
(0.0999), defeating the entire tier scheme.

These tests pin _fan_out_tiers so:
  - The classic 4-tier interest-rate rule is split into 4 rules
  - Conditions and actions are paired 1:1 in original order
  - Non-tiered rules pass through untouched
  - Edge cases (mismatched counts, mixed action types, AND logic
    between conditions, duplicate values) are NOT split
"""
from __future__ import annotations

from app.pipeline.rule_extractor import _fan_out_tiers
from app.schemas.rule import Action, Condition, RuleDefinition, RuleTypeEnum


def _r(
    *,
    rule_id="RULE-001",
    name="X",
    rule_type=RuleTypeEnum.PRICING,
    conditions,
    actions,
):
    return RuleDefinition(
        rule_id=rule_id,
        rule_name=name,
        description="",
        rule_type=rule_type,
        conditions=conditions,
        actions=actions,
    )


def test_classic_tiered_interest_rate_splits_into_four():
    """The exact shape that prompted the fix."""
    rule = _r(
        rule_id="RULE-002",
        name="Tiered Interest Rate by Bureau Score",
        conditions=[
            Condition(field="bureau_score", operator="between", value=[680, 719], logic="OR"),
            Condition(field="bureau_score", operator="between", value=[720, 749], logic="OR"),
            Condition(field="bureau_score", operator="between", value=[750, 799], logic="OR"),
            Condition(field="bureau_score", operator=">=",      value=800,        logic="OR"),
        ],
        actions=[
            Action(action_type="SET", target_field="interest_rate", value=0.1699, description="16.99% for 680-719"),
            Action(action_type="SET", target_field="interest_rate", value=0.1499, description="14.99% for 720-749"),
            Action(action_type="SET", target_field="interest_rate", value=0.1249, description="12.49% for 750-799"),
            Action(action_type="SET", target_field="interest_rate", value=0.0999, description="9.99% for 800+"),
        ],
    )
    out = _fan_out_tiers([rule])

    assert len(out) == 4, "Should fan out to 4 tier rules"
    # Each new rule has exactly one condition + one action paired in order
    expected_pairs = [
        ([680, 719], 0.1699),
        ([720, 749], 0.1499),
        ([750, 799], 0.1249),
        (800,        0.0999),
    ]
    for i, (cond_value, action_value) in enumerate(expected_pairs):
        r = out[i]
        assert len(r.conditions) == 1
        assert len(r.actions) == 1
        assert r.conditions[0].field == "bureau_score"
        assert r.conditions[0].value == cond_value
        assert r.actions[0].target_field == "interest_rate"
        assert r.actions[0].value == action_value
        # Tier ID suffix
        assert r.rule_id == f"RULE-002-T{i + 1}"
        # Condition logic is AND (it's standalone now)
        assert r.conditions[0].logic == "AND"


def test_non_tiered_single_condition_single_action_passes_through():
    rule = _r(
        rule_id="RULE-001",
        name="DTI Cap",
        rule_type=RuleTypeEnum.ELIGIBILITY,
        conditions=[Condition(field="dti_ratio", operator=">", value=0.43, logic="AND")],
        actions=[Action(action_type="REJECT", target_field="decision_status",
                        value="REJECTED", description="High DTI")],
    )
    out = _fan_out_tiers([rule])
    assert len(out) == 1
    assert out[0] is rule  # unchanged


def test_mismatched_counts_does_not_split():
    """3 conditions, 2 actions — can't pair 1:1, so leave alone."""
    rule = _r(
        conditions=[
            Condition(field="bureau_score", operator="between", value=[680, 719], logic="OR"),
            Condition(field="bureau_score", operator="between", value=[720, 749], logic="OR"),
            Condition(field="bureau_score", operator=">=",      value=800,        logic="OR"),
        ],
        actions=[
            Action(action_type="SET", target_field="interest_rate", value=0.1699, description="x"),
            Action(action_type="SET", target_field="interest_rate", value=0.1499, description="y"),
        ],
    )
    out = _fan_out_tiers([rule])
    assert len(out) == 1, "Counts don't match — should not split"


def test_actions_on_different_targets_does_not_split():
    """Two actions on different target_fields — not a tier table."""
    rule = _r(
        conditions=[
            Condition(field="bureau_score", operator="between", value=[680, 719], logic="OR"),
            Condition(field="bureau_score", operator="between", value=[720, 749], logic="OR"),
        ],
        actions=[
            Action(action_type="SET", target_field="interest_rate", value=0.1699, description="x"),
            Action(action_type="SET", target_field="eligible_amount", value=50000, description="y"),
        ],
    )
    out = _fan_out_tiers([rule])
    assert len(out) == 1


def test_REJECT_actions_are_not_tier_candidates():
    """REJECT isn't SET-style, so don't fan out even with multiple OR conditions."""
    rule = _r(
        conditions=[
            Condition(field="bureau_score", operator="<", value=580, logic="OR"),
            Condition(field="bureau_score", operator="<", value=620, logic="OR"),
        ],
        actions=[
            Action(action_type="REJECT", target_field="decision_status",
                   value="REJECTED", description="x"),
            Action(action_type="REJECT", target_field="decision_status",
                   value="REJECTED", description="y"),
        ],
    )
    out = _fan_out_tiers([rule])
    assert len(out) == 1


def test_AND_logic_between_conditions_does_not_split():
    """If conditions are AND'd, they're a compound predicate, not a tier table."""
    rule = _r(
        conditions=[
            Condition(field="bureau_score", operator=">=", value=680, logic="AND"),
            Condition(field="dti_ratio",    operator="<=", value=0.43, logic="AND"),
        ],
        actions=[
            Action(action_type="SET", target_field="interest_rate", value=0.1499, description="x"),
            Action(action_type="SET", target_field="interest_rate", value=0.1599, description="y"),
        ],
    )
    out = _fan_out_tiers([rule])
    assert len(out) == 1


def test_duplicate_action_values_do_not_split():
    """Same value across actions = not a real tier table."""
    rule = _r(
        conditions=[
            Condition(field="bureau_score", operator="between", value=[680, 719], logic="OR"),
            Condition(field="bureau_score", operator="between", value=[720, 749], logic="OR"),
        ],
        actions=[
            Action(action_type="SET", target_field="interest_rate", value=0.15, description="x"),
            Action(action_type="SET", target_field="interest_rate", value=0.15, description="y"),
        ],
    )
    out = _fan_out_tiers([rule])
    assert len(out) == 1


def test_mix_of_tiered_and_non_tiered_rules():
    tiered = _r(
        rule_id="RULE-002",
        conditions=[
            Condition(field="bureau_score", operator="between", value=[680, 719], logic="OR"),
            Condition(field="bureau_score", operator="between", value=[720, 749], logic="OR"),
        ],
        actions=[
            Action(action_type="SET", target_field="interest_rate", value=0.17, description="x"),
            Action(action_type="SET", target_field="interest_rate", value=0.15, description="y"),
        ],
    )
    plain = _r(
        rule_id="RULE-003",
        conditions=[Condition(field="dti_ratio", operator=">", value=0.43, logic="AND")],
        actions=[Action(action_type="REJECT", target_field="decision_status",
                        value="REJECTED", description="x")],
    )
    out = _fan_out_tiers([tiered, plain])
    assert len(out) == 3
    assert out[0].rule_id == "RULE-002-T1"
    assert out[1].rule_id == "RULE-002-T2"
    assert out[2] is plain
