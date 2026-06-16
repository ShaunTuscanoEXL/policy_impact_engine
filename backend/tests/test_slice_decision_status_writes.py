"""Phase D — engine honors SET decision_status writes + direct top-level
field reads.

Surfaced by aligning the DTI-Regeneration BRD: its reject rules are
phrased "set decision_status = REJECTED" (a SET action, not a REJECT
action), and its scope flag dti_breach_regeneration is an app-set
top-level field. Two gaps blocked it:

  1. SET decision_status=REJECTED fired but left decision APPROVED — only
     action_type=REJECT was treated as terminal.
  2. The novel flag dti_breach_regeneration fuzzy-matched the registry's
     debt_to_income_ratio path ("dti" substring), so the engine read the
     wrong (missing) field and the rule never fired.
"""
from __future__ import annotations

from app.runtime.rule_engine import LoanContext, evaluate_snapshot


def _rule(rid, conditions, actions, subsystem="UNCLASSIFIED"):
    return {
        "id": rid, "rule_id": rid, "rule_name": rid,
        "subsystem": subsystem, "rule_type": "ELIGIBILITY", "priority": 0,
        "conditions": conditions, "actions": actions,
    }


def _c(field, op, value):
    return {"field": field, "operator": op, "value": value, "logic": "AND"}


def _set(target, value):
    return {"action_type": "SET", "target_field": target, "value": value, "description": ""}


# ── SET decision_status honored as a decision ──────────────────────────


def test_set_decision_status_rejected_is_terminal():
    snap = [_rule("R", [_c("desired_amount", ">", 60000)],
                  [_set("decision_status", "REJECTED")])]
    r = evaluate_snapshot(snap, {"desired_amount": 80000})
    assert r.decision == "REJECTED"
    assert r.terminal_rule_id == "R"


def test_set_decision_status_flagged_sets_flagged():
    snap = [_rule("R", [_c("desired_amount", ">", 60000)],
                  [_set("decision_status", "FLAGGED")])]
    r = evaluate_snapshot(snap, {"desired_amount": 80000})
    assert r.decision == "FLAGGED"


def test_set_decision_status_approved_with_conditions_maps_to_approved():
    """APPROVED_WITH_CONDITIONS isn't in the terminal vocabulary — the
    top-level decision stays APPROVED, but the precise label is recorded
    on the fired SET (and the context overlay)."""
    snap = [_rule("R", [_c("desired_amount", "<=", 60000)],
                  [_set("decision_status", "APPROVED_WITH_CONDITIONS")])]
    r = evaluate_snapshot(snap, {"desired_amount": 50000})
    assert r.decision == "APPROVED"
    statuses = [f.value for f in r.fired_rules if f.target_field == "decision_status"]
    assert statuses == ["APPROVED_WITH_CONDITIONS"]


def test_set_decision_status_rejected_short_circuits_later_rules():
    snap = [
        _rule("REJ", [_c("desired_amount", ">", 60000)],
              [_set("decision_status", "REJECTED")], subsystem="AMOUNT_CAP"),
        _rule("LATER", [_c("desired_amount", ">", 0)],
              [_set("some_flag", True)], subsystem="SCORING_MODEL"),
    ]
    r = evaluate_snapshot(snap, {"desired_amount": 80000})
    assert r.decision == "REJECTED"
    # LATER (rank after AMOUNT_CAP) must not have fired post-terminal
    assert "LATER" not in {f.rule_id for f in r.fired_rules}


# ── Top-level field precedence over fuzzy registry resolution ──────────


def test_top_level_flag_not_fuzzy_mismapped():
    """dti_breach_regeneration must read the real top-level flag, not
    fuzzy-resolve to debt_to_income_ratio."""
    ctx = LoanContext({"dti_breach_regeneration": True})
    assert ctx.get("dti_breach_regeneration") is True


def test_bool_scope_flag_condition_fires():
    snap = [_rule("R", [_c("dti_breach_regeneration", "==", True),
                        _c("desired_amount", ">", 60000)],
                  [_set("decision_status", "REJECTED")])]
    # In regeneration + over cap → reject
    r = evaluate_snapshot(snap, {"dti_breach_regeneration": True, "desired_amount": 80000})
    assert r.decision == "REJECTED"


def test_scope_flag_false_disables_rule():
    snap = [_rule("R", [_c("dti_breach_regeneration", "==", True),
                        _c("desired_amount", ">", 60000)],
                  [_set("decision_status", "REJECTED")])]
    # NOT in regeneration → gate must not fire even though amount is over cap
    r = evaluate_snapshot(snap, {"dti_breach_regeneration": False, "desired_amount": 80000})
    assert r.decision == "APPROVED"


def test_nested_registry_field_still_resolves():
    """The top-level precedence must NOT break normal nested registry
    resolution (bureau_score lives nested, not at the root)."""
    ctx = LoanContext({
        "borrower_credit_model": {"bureau_credits": {"bureau_score": 742}}
    })
    assert ctx.get("bureau_score") == 742


def test_overlay_still_beats_top_level():
    """A derived SET value (overlay) still wins over a raw top-level key
    of the same name."""
    ctx = LoanContext({"customer_segment": "RAW"})
    ctx.set("customer_segment", "DERIVED")
    assert ctx.get("customer_segment") == "DERIVED"
