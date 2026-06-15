"""Phase C — scope/eligibility gate capture + flagged injection."""
from __future__ import annotations

from app.pipeline.rule_extractor import _inject_scope_gates
from app.schemas.rule import Action, Condition, RuleDefinition, RuleTypeEnum
from app.services.canonical_key import make_canonical_key, make_semantic_signature


def _rule(rid, conditions, applies_when=None, actions=None):
    return RuleDefinition(
        rule_id=rid, rule_name=rid, description="",
        rule_type=RuleTypeEnum.CAP,
        conditions=conditions,
        actions=actions or [Action(action_type="ADJUST", target_field="eligible_amount",
                                   value=0.4, description="")],
        priority=0, source_section="", confidence=0.95,
        applies_when=applies_when or [],
    )


def _c(field, op, value, origin="explicit"):
    return Condition(field=field, operator=op, value=value, logic="AND", origin=origin)


# ── Injection ──────────────────────────────────────────────────────────


def test_scope_gates_folded_into_conditions_with_origin():
    rules = [
        _rule("R10",
              conditions=[_c("customer_segment", "==", "SEGMENT_A")],
              applies_when=[_c("repeat_type", "==", "REPEAT", origin="scope"),
                            _c("customer_classification", "==", "GOOD", origin="scope")]),
    ]
    out = _inject_scope_gates(rules)
    r = out[0]
    assert len(r.conditions) == 3  # 1 explicit + 2 scope
    by_origin = {}
    for c in r.conditions:
        by_origin.setdefault(c.origin, []).append(c.field)
    assert by_origin["explicit"] == ["customer_segment"]
    assert set(by_origin["scope"]) == {"repeat_type", "customer_classification"}
    # All injected gates are AND-joined
    for c in r.conditions:
        assert (c.logic or "AND").upper() == "AND"
    # applies_when cleared after folding
    assert r.applies_when == []


def test_duplicate_scope_gate_is_not_double_injected():
    """If the rule already has the gate as an explicit condition, the
    scope copy is skipped."""
    rules = [
        _rule("R1",
              conditions=[_c("repeat_type", "==", "REPEAT")],
              applies_when=[_c("repeat_type", "==", "REPEAT", origin="scope")]),
    ]
    out = _inject_scope_gates(rules)
    assert len(out[0].conditions) == 1  # no duplicate


def test_universal_rule_without_applies_when_untouched():
    rules = [_rule("R1", conditions=[_c("bureau_score", "<", 680)])]
    out = _inject_scope_gates(rules)
    assert len(out[0].conditions) == 1
    assert out[0].conditions[0].origin == "explicit"


def test_empty_input():
    assert _inject_scope_gates([]) == []


# ── origin is metadata, not identity ───────────────────────────────────


def test_origin_does_not_change_canonical_key():
    """A scope-injected condition must NOT change the rule's canonical_key
    — identity is field+operator+value+action+target, not provenance."""
    base_conditions = [{"field": "customer_segment", "operator": "==", "value": "SEGMENT_A"}]
    actions = [{"action_type": "ADJUST", "target_field": "eligible_amount", "value": 0.4}]
    k_plain = make_canonical_key("AMOUNT_CAP", base_conditions, actions)

    with_origin = [{"field": "customer_segment", "operator": "==", "value": "SEGMENT_A",
                    "origin": "explicit"}]
    k_origin = make_canonical_key("AMOUNT_CAP", with_origin, actions)
    assert k_plain == k_origin


def test_origin_does_not_break_semantic_signature():
    conds = [{"field": "customer_segment", "operator": "==", "value": "A", "origin": "scope"}]
    acts = [{"action_type": "ADJUST", "target_field": "eligible_amount", "value": 0.4}]
    sig = make_semantic_signature(conds, acts)  # must not raise
    assert sig is not None


def test_condition_defaults_origin_to_explicit():
    """Existing condition dicts without an origin key still parse, default
    to explicit — back-compat with every pre-Slice-15 stored rule."""
    c = Condition(field="bureau_score", operator="<", value=680)
    assert c.origin == "explicit"
