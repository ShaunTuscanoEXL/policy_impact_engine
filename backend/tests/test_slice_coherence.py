"""Phase B — BRD coherence validator (dependency graph analysis)."""
from __future__ import annotations

from app.pipeline.coherence import analyze_coherence
from app.schemas.rule import Action, Condition, RuleDefinition, RuleTypeEnum


def _rule(rid, conditions, actions, rtype="ELIGIBILITY"):
    return RuleDefinition(
        rule_id=rid, rule_name=rid, description="",
        rule_type=RuleTypeEnum(rtype),
        conditions=conditions, actions=actions,
        priority=0, source_section="", confidence=0.95,
    )


def _cond(field, op, value):
    return Condition(field=field, operator=op, value=value, logic="AND")


def _set(target, value):
    return Action(action_type="SET", target_field=target, value=value, description="")


def _adjust(target, value):
    return Action(action_type="ADJUST", target_field=target, value=value, description="")


def _reject():
    return Action(action_type="REJECT", target_field="decision_status",
                  value="REJECTED", description="")


def _kinds(report):
    return {i.kind for i in report.issues}


# ── Unreferenced eligibility (the user's exact concern) ────────────────


def test_unreferenced_eligibility_flagged():
    """customer_classification=GOOD is set but nothing gates on it — the
    'Good Customer' definition that does nothing downstream."""
    rules = [
        _rule("R1",
              [_cond("repeat_type", "==", "REPEAT"),
               _cond("dti_ratio", "<=", 0.2)],
              [_set("customer_classification", "GOOD")]),
        # segmentation that SHOULD have been gated by GOOD but isn't
        _rule("R2",
              [_cond("credit_risk_band", "==", "LOW")],
              [_set("customer_segment", "SEGMENT_A")]),
        _rule("R3",
              [_cond("customer_segment", "==", "SEGMENT_A")],
              [_adjust("interest_rate", -0.025)]),
    ]
    report = analyze_coherence(rules)
    assert "unreferenced_eligibility" in _kinds(report)
    issue = next(i for i in report.issues if i.kind == "unreferenced_eligibility")
    assert issue.field == "customer_classification"
    assert "R1" in issue.rule_ids


def test_eligibility_that_is_referenced_is_not_flagged():
    """When a downstream rule DOES gate on the classification, no issue."""
    rules = [
        _rule("R1",
              [_cond("repeat_type", "==", "REPEAT")],
              [_set("customer_classification", "GOOD")]),
        _rule("R2",
              [_cond("customer_classification", "==", "GOOD"),
               _cond("credit_risk_band", "==", "LOW")],
              [_set("customer_segment", "SEGMENT_A")]),
        # consume customer_segment so it isn't itself an orphan
        _rule("R3",
              [_cond("customer_segment", "==", "SEGMENT_A")],
              [_adjust("interest_rate", -0.025)]),
    ]
    report = analyze_coherence(rules)
    assert "unreferenced_eligibility" not in _kinds(report)


# ── Dead consumers ─────────────────────────────────────────────────────


def test_dead_consumer_flagged():
    """A rule conditions on a field nothing produces and isn't a known
    raw loan field → can never fire."""
    rules = [
        _rule("R1",
              [_cond("made_up_derived_field", "==", "X")],
              [_adjust("interest_rate", -0.01)]),
    ]
    report = analyze_coherence(rules)
    assert "dead_consumer" in _kinds(report)
    issue = next(i for i in report.issues if i.kind == "dead_consumer")
    assert issue.field == "made_up_derived_field"


def test_known_raw_field_consumer_not_flagged():
    """Conditioning on bureau_score (a real loan field) with no producer
    is NORMAL — must not be flagged as dead."""
    rules = [
        _rule("R1", [_cond("bureau_score", "<", 680)], [_reject()]),
    ]
    report = analyze_coherence(rules)
    assert "dead_consumer" not in _kinds(report)


def test_produced_field_consumer_not_flagged():
    """Consuming a field that another rule produces is the healthy chain
    case — no dead-consumer issue (Phase A makes it fire)."""
    rules = [
        _rule("R1", [_cond("credit_risk_band", "==", "LOW")],
              [_set("customer_segment", "A")]),
        _rule("R2", [_cond("customer_segment", "==", "A")],
              [_adjust("interest_rate", -0.01)]),
    ]
    report = analyze_coherence(rules)
    assert "dead_consumer" not in _kinds(report)


# ── Terminal targets don't count as orphans ────────────────────────────


def test_terminal_output_without_consumer_not_flagged():
    """SET interest_rate / decision_status without a consumer is a final
    output, not an orphan classification."""
    rules = [
        _rule("R1", [_cond("bureau_score", ">=", 750)],
              [_set("interest_rate", 0.0999)]),
    ]
    report = analyze_coherence(rules)
    assert "orphan_producer" not in _kinds(report)
    assert "unreferenced_eligibility" not in _kinds(report)


# ── Cycle detection ────────────────────────────────────────────────────


def test_dependency_cycle_flagged():
    rules = [
        _rule("A", [_cond("y_flag", "==", True)], [_set("x_flag", True)]),
        _rule("B", [_cond("x_flag", "==", True)], [_set("y_flag", True)]),
    ]
    report = analyze_coherence(rules)
    assert "dependency_cycle" in _kinds(report)
    assert report.is_coherent is False  # cycle is an error


def test_no_cycle_is_coherent():
    rules = [
        _rule("A", [_cond("credit_risk_band", "==", "LOW")], [_set("seg", "A")]),
        _rule("B", [_cond("seg", "==", "A")], [_adjust("interest_rate", -0.01)]),
    ]
    report = analyze_coherence(rules)
    assert "dependency_cycle" not in _kinds(report)
    assert report.is_coherent is True


# ── Dependency edges exposed for the UI ─────────────────────────────────


def test_dependency_edges_reported():
    rules = [
        _rule("PROD", [_cond("credit_risk_band", "==", "LOW")], [_set("seg", "A")]),
        _rule("CONS", [_cond("seg", "==", "A")], [_adjust("interest_rate", -0.01)]),
    ]
    report = analyze_coherence(rules)
    assert ("PROD", "CONS", "seg") in report.dependency_edges


def test_empty_ruleset_is_coherent():
    report = analyze_coherence([])
    assert report.is_coherent is True
    assert report.issues == []
