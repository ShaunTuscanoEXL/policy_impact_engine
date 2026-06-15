"""Phase A — engine derived-field chaining.

Before this fix the engine evaluated rules over a read-only context and
in a flat subsystem order, so a rule that SET a derived field (e.g.
customer_segment) was invisible to a later rule that conditioned on it,
AND the producer could sort after the consumer. Multi-stage BRDs
(eligibility → classification → segment → pricing) silently never
executed past the first stage.

These tests lock in:
  - a derived value SET by one rule is readable by a later rule
  - producer-before-consumer ordering even when the producer's subsystem
    sorts LAST
  - gate short-circuit (REJECT terminates) is preserved
  - cycles fall back safely instead of hanging
"""
from __future__ import annotations

from app.runtime.rule_engine import (
    LoanContext,
    _compute_order,
    evaluate_snapshot,
)


def _rule(rid, subsystem, conditions, actions, priority=0):
    return {
        "id": rid, "rule_id": rid, "rule_name": rid,
        "subsystem": subsystem, "rule_type": "ELIGIBILITY",
        "priority": priority,
        "conditions": conditions, "actions": actions,
    }


def _cond(field, op, value):
    return {"field": field, "operator": op, "value": value, "logic": "AND"}


def _set(target, value):
    return {"action_type": "SET", "target_field": target, "value": value, "description": ""}


def _adjust(target, value):
    return {"action_type": "ADJUST", "target_field": target, "value": value, "description": ""}


def _reject():
    return {"action_type": "REJECT", "target_field": "decision_status", "value": "REJECTED", "description": ""}


# ── LoanContext overlay ────────────────────────────────────────────────


def test_context_overlay_reads_back_derived_value():
    ctx = LoanContext({"calculated_attributes": {"credit_risk_band": "LOW"}})
    assert ctx.get("credit_risk_band") == "LOW"      # raw
    assert ctx.get("customer_segment") is None        # not set yet
    ctx.set("customer_segment", "SEGMENT_A")
    assert ctx["customer_segment"] == "SEGMENT_A"     # overlay


def test_context_overlay_is_case_insensitive():
    ctx = LoanContext({})
    ctx.set("Customer Segment", "A")
    assert ctx.get("customer_segment") == "A"
    assert ctx.get("CUSTOMER SEGMENT") == "A"


def test_context_overlay_overrides_raw_payload():
    ctx = LoanContext({"calculated_attributes": {"credit_risk_band": "HIGH"}})
    assert ctx.get("credit_risk_band") == "HIGH"
    ctx.set("credit_risk_band", "LOW")
    assert ctx.get("credit_risk_band") == "LOW"  # overlay wins


# ── Chaining ───────────────────────────────────────────────────────────


def test_two_stage_chain_fires():
    """The Repeat Customer pattern: stage 1 SETs customer_segment from a
    raw field, stage 2 conditions on the derived customer_segment."""
    snapshot = [
        _rule("SEG-A", "SCORING_MODEL",
              [_cond("credit_risk_band", "==", "LOW")],
              [_set("customer_segment", "SEGMENT_A")]),
        _rule("PRICE-A", "RATE_MODIFIER",
              [_cond("customer_segment", "==", "SEGMENT_A")],
              [_adjust("interest_rate", -0.025)]),
    ]
    loan = {"calculated_attributes": {"credit_risk_band": "LOW"}}
    r = evaluate_snapshot(snapshot, loan)
    fired = {fr.rule_id for fr in r.fired_rules}
    assert "SEG-A" in fired
    assert "PRICE-A" in fired, "consumer of derived field should fire"


def test_three_stage_chain_fires():
    """eligibility → segment → pricing, all derived."""
    snapshot = [
        _rule("ELIG", "DTI_GATE",
              [_cond("repeat_type", "==", "REPEAT")],
              [_set("customer_classification", "GOOD")]),
        _rule("SEG", "SCORING_MODEL",
              [_cond("customer_classification", "==", "GOOD"),
               _cond("credit_risk_band", "==", "LOW")],
              [_set("customer_segment", "SEGMENT_A")]),
        _rule("PRICE", "RATE_MODIFIER",
              [_cond("customer_segment", "==", "SEGMENT_A")],
              [_adjust("interest_rate", -0.025)]),
    ]
    loan = {"repeat_type": "REPEAT", "calculated_attributes": {"credit_risk_band": "LOW"}}
    r = evaluate_snapshot(snapshot, loan)
    fired = {fr.rule_id for fr in r.fired_rules}
    assert fired == {"ELIG", "SEG", "PRICE"}, fired


def test_chain_does_not_fire_when_eligibility_fails():
    """If the upstream eligibility rule doesn't fire, the derived field
    stays unset and the whole chain correctly stops."""
    snapshot = [
        _rule("ELIG", "DTI_GATE",
              [_cond("repeat_type", "==", "REPEAT")],
              [_set("customer_classification", "GOOD")]),
        _rule("SEG", "SCORING_MODEL",
              [_cond("customer_classification", "==", "GOOD")],
              [_set("customer_segment", "SEGMENT_A")]),
    ]
    loan = {"repeat_type": "FIRST_TIME"}  # not REPEAT → ELIG doesn't fire
    r = evaluate_snapshot(snapshot, loan)
    fired = {fr.rule_id for fr in r.fired_rules}
    assert fired == set(), f"nothing should fire, got {fired}"


# ── Ordering ───────────────────────────────────────────────────────────


def test_producer_ordered_before_consumer_despite_subsystem_rank():
    """SCORING_MODEL (producer) sorts LAST by subsystem rank, AMOUNT_CAP
    (consumer) sorts earlier. Topo order must still place producer first."""
    snapshot = [
        _rule("CONSUMER", "AMOUNT_CAP",
              [_cond("customer_segment", "==", "A")],
              [_adjust("eligible_amount", 0.4)]),
        _rule("PRODUCER", "SCORING_MODEL",
              [_cond("credit_risk_band", "==", "LOW")],
              [_set("customer_segment", "A")]),
    ]
    order = _compute_order(snapshot)
    producer_idx = order.index(1)  # PRODUCER is snapshot[1]
    consumer_idx = order.index(0)  # CONSUMER is snapshot[0]
    assert producer_idx < consumer_idx


def test_independent_gates_keep_subsystem_order():
    """Rules with no producer/consumer edges retain the historical
    subsystem ordering (BUREAU_GATE before SCORING_MODEL)."""
    snapshot = [
        _rule("SCORE", "SCORING_MODEL", [_cond("g5_score", "<", 0.4)], [_set("flag1", True)]),
        _rule("BUREAU", "BUREAU_GATE", [_cond("bureau_score", "<", 680)], [_reject()]),
    ]
    order = _compute_order(snapshot)
    # BUREAU_GATE (rank 1) should come before SCORING_MODEL (rank 11)
    assert order.index(1) < order.index(0)


def test_gate_short_circuit_preserved():
    """A REJECT gate reading raw fields still fires first and terminates,
    even with a derived-field chain present."""
    snapshot = [
        _rule("REJ", "BUREAU_GATE",
              [_cond("bureau_score", "<", 680)], [_reject()]),
        _rule("SEG", "SCORING_MODEL",
              [_cond("credit_risk_band", "==", "LOW")],
              [_set("customer_segment", "A")]),
    ]
    loan = {
        "borrower_credit_model": {"bureau_credits": {"bureau_score": 600}},
        "calculated_attributes": {"credit_risk_band": "LOW"},
    }
    r = evaluate_snapshot(snapshot, loan)
    assert r.decision == "REJECTED"
    assert r.terminal_rule_id == "REJ"


def test_cycle_falls_back_without_hanging():
    """A produces X consumed by B; B produces Y consumed by A — a cycle.
    _compute_order must still return all rules (deterministic fallback),
    not hang or drop any."""
    snapshot = [
        _rule("A", "UNCLASSIFIED",
              [_cond("y_flag", "==", True)], [_set("x_flag", True)]),
        _rule("B", "UNCLASSIFIED",
              [_cond("x_flag", "==", True)], [_set("y_flag", True)]),
    ]
    order = _compute_order(snapshot)
    assert sorted(order) == [0, 1], "cycle must not drop rules"


def test_order_is_cached_and_stable():
    """Same snapshot ordered twice returns the same order (cache hit)."""
    snapshot = [
        _rule("SEG", "SCORING_MODEL",
              [_cond("credit_risk_band", "==", "LOW")],
              [_set("customer_segment", "A")]),
        _rule("PRICE", "RATE_MODIFIER",
              [_cond("customer_segment", "==", "A")],
              [_adjust("interest_rate", -0.01)]),
    ]
    o1 = _compute_order(snapshot)
    o2 = _compute_order(snapshot)
    assert o1 == o2
