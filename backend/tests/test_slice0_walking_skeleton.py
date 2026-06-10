"""Slice 0 — walking skeleton contract tests.

These cover the deterministic logic that doesn't need a database:
- canonical_key generation
- subsystem classification
- merge engine pair classification
- Python codegen produces ast-parseable output

Run with:  pytest backend/tests/test_slice0_walking_skeleton.py
"""
import ast
from datetime import datetime

from app.codegen import render_python
from app.models.merge import (
    MergeItemCategory,
    MergeItemSeverity,
    MergeSuggestedAction,
)
from app.models.rule import RuleType, Subsystem
from app.services.canonical_key import (
    action_class,
    make_canonical_key,
    make_semantic_signature,
    operator_class,
)
from app.services.merge_engine import classify_pair, diff_rule_sets
from app.services.rule_classifier import classify


# ── Canonical key + classifier ───────────────────────────────────────────

def test_operator_class_normalization():
    assert operator_class(">") == "GT"
    assert operator_class("gte") == "GT"
    assert operator_class("between") == "RANGE"
    assert operator_class(None) == "UNK"


def test_action_class_normalization():
    assert action_class("REJECT") == "REJECT"
    assert action_class("auto_reject") == "REJECT"
    assert action_class("MANUAL_REVIEW") == "FLAG"
    assert action_class("ADJUST") == "MODIFY"
    assert action_class("SET") == "CAP"


def test_canonical_key_stable_across_threshold_changes():
    conds_a = [{"field": "dti_ratio", "operator": ">", "value": 0.40}]
    conds_b = [{"field": "dti_ratio", "operator": ">", "value": 0.35}]
    acts = [{"action_type": "REJECT", "target_field": "decision_status",
             "value": "REJECTED", "description": "HIGH_DTI"}]
    ka = make_canonical_key(Subsystem.DTI_GATE, conds_a, acts)
    kb = make_canonical_key(Subsystem.DTI_GATE, conds_b, acts)
    assert ka == kb == "DTI_GATE::dti_ratio::GT::REJECT::DECISION"


def test_classifier_picks_bureau_for_bureau_score():
    sub = classify(
        [{"field": "bureau_score", "operator": "<", "value": 720}],
        [{"action_type": "REJECT", "target_field": "decision_status",
          "value": "REJECTED", "description": "FICO"}],
        RuleType.ELIGIBILITY,
    )
    assert sub == Subsystem.BUREAU_GATE


def test_classifier_action_target_overrides_field():
    """Rule on bureau_score that ADJUSTs interest_rate is RATE_MODIFIER."""
    sub = classify(
        [{"field": "bureau_score", "operator": ">=", "value": 750}],
        [{"action_type": "ADJUST", "target_field": "interest_rate",
          "value": -0.005, "description": "Premium discount"}],
        RuleType.PRICING,
    )
    assert sub == Subsystem.RATE_MODIFIER


def test_semantic_signature_shape():
    sig = make_semantic_signature(
        [{"field": "bureau_score", "operator": "<", "value": 720, "logic": "AND"}],
        [{"action_type": "REJECT", "target_field": "decision_status",
          "value": "REJECTED", "description": "x"}],
    )
    assert sig["fields"] == ["bureau_score"]
    assert sig["operators"] == ["LT"]
    assert sig["thresholds"] == [720]
    assert sig["action_types"] == ["REJECT"]


# ── Merge engine ─────────────────────────────────────────────────────────

def _rule(rid, key, field, op, val, action="REJECT", target="decision_status", desc="x"):
    return {
        "id": rid, "rule_id": rid, "rule_name": rid,
        "subsystem": key.split("::")[0], "canonical_key": key,
        "conditions": [{"field": field, "operator": op, "value": val}],
        "actions": [{"action_type": action, "target_field": target,
                     "value": "REJECTED", "description": desc}],
    }


def test_classify_pair_new_when_no_live_match():
    incoming = _rule("I1", "BUREAU_GATE::bureau_score::LT::REJECT::DECISION",
                     "bureau_score", "<", 720)
    spec = classify_pair(incoming, None)
    assert spec.category == MergeItemCategory.NEW_RULE
    assert spec.severity == MergeItemSeverity.INFO
    assert spec.suggested_action == MergeSuggestedAction.ACCEPT


def test_classify_pair_exact_duplicate():
    live = _rule("L1", "DTI_GATE::dti_ratio::GT::REJECT::DECISION", "dti_ratio", ">", 0.43)
    inc = _rule("I1", "DTI_GATE::dti_ratio::GT::REJECT::DECISION", "dti_ratio", ">", 0.43)
    spec = classify_pair(inc, live)
    assert spec.category == MergeItemCategory.EXACT_DUPLICATE
    assert spec.suggested_action == MergeSuggestedAction.DROP


def test_classify_pair_threshold_tightening():
    live = _rule("L1", "DTI_GATE::dti_ratio::GT::REJECT::DECISION", "dti_ratio", ">", 0.43)
    inc = _rule("I1", "DTI_GATE::dti_ratio::GT::REJECT::DECISION", "dti_ratio", ">", 0.35)
    spec = classify_pair(inc, live)
    assert spec.category == MergeItemCategory.THRESHOLD_TIGHTENING
    assert spec.severity == MergeItemSeverity.SOFT
    assert spec.suggested_action == MergeSuggestedAction.SUPERSEDE


def test_classify_pair_threshold_relaxation():
    live = _rule("L1", "DTI_GATE::dti_ratio::GT::REJECT::DECISION", "dti_ratio", ">", 0.35)
    inc = _rule("I1", "DTI_GATE::dti_ratio::GT::REJECT::DECISION", "dti_ratio", ">", 0.45)
    spec = classify_pair(inc, live)
    assert spec.category == MergeItemCategory.THRESHOLD_RELAXATION


def test_classify_pair_action_drift_is_hard():
    """REJECT vs FLAG on the same condition is paired by the merge engine
    via pairing_key (which strips action_class) and surfaces as
    ACTION_DRIFT, blocking apply."""
    live = _rule("L1", "DTI_GATE::dti_ratio::GT::REJECT::DECISION",
                 "dti_ratio", ">", 0.43, action="REJECT")
    inc = _rule("I1", "DTI_GATE::dti_ratio::GT::FLAG::DECISION",
                "dti_ratio", ">", 0.43, action="FLAG")
    spec = classify_pair(inc, live)
    assert spec.category == MergeItemCategory.ACTION_DRIFT
    assert spec.severity == MergeItemSeverity.HARD


def test_diff_rule_sets_basic_counts():
    live = [
        _rule("L1", "BUREAU_GATE::bureau_score::LT::REJECT::DECISION",
              "bureau_score", "<", 700),
        _rule("L2", "DTI_GATE::dti_ratio::GT::REJECT::DECISION",
              "dti_ratio", ">", 0.40),
    ]
    incoming = [
        _rule("I1", "BUREAU_GATE::bureau_score::LT::REJECT::DECISION",
              "bureau_score", "<", 720),                          # tightening
        _rule("I2", "DTI_GATE::dti_ratio::GT::REJECT::DECISION",
              "dti_ratio", ">", 0.40),                            # duplicate
        _rule("I3", "BUREAU_GATE::inquiries_last_3m::GT::REJECT::DECISION",
              "inquiries_last_3m", ">", 3),                       # new
    ]
    specs = diff_rule_sets(incoming, live)
    by_cat = {s.category for s in specs}
    assert MergeItemCategory.THRESHOLD_TIGHTENING in by_cat
    assert MergeItemCategory.EXACT_DUPLICATE in by_cat
    assert MergeItemCategory.NEW_RULE in by_cat
    assert len(specs) == 3


# ── Codegen ──────────────────────────────────────────────────────────────

class _MockRepo:
    name = "Test Repo"
    product = "PERSONAL"
    jurisdiction = "US"


class _MockVersion:
    def __init__(self, snapshot):
        self.version_number = 1
        self.summary = "Test"
        self.rule_snapshot = snapshot


def test_codegen_empty_version_is_valid_python():
    src = render_python(_MockRepo(), _MockVersion([]))
    ast.parse(src)
    assert "no rules" in src.lower()


def test_codegen_renders_subsystem_groups_in_order():
    snapshot = [
        {"id": "R1", "rule_id": "R1", "rule_name": "FICO floor",
         "subsystem": "BUREAU_GATE", "priority": 100,
         "conditions": [{"field": "bureau_score", "operator": "<", "value": 720}],
         "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                      "value": "REJECTED", "description": "FICO"}]},
        {"id": "R2", "rule_id": "R2", "rule_name": "Pricing tier",
         "subsystem": "PRICING_TIER", "priority": 50,
         "conditions": [{"field": "bureau_score", "operator": "between", "value": [720, 769]}],
         "actions": [{"action_type": "SET", "target_field": "interest_rate",
                      "value": 0.1199, "description": "TIER_2"}]},
    ]
    src = render_python(_MockRepo(), _MockVersion(snapshot),
                        generated_at=datetime(2026, 4, 30))
    # ast must accept it
    ast.parse(src)
    # Bureau group renders before pricing group (gates first)
    assert src.find("BUREAU_GATE") < src.find("PRICING_TIER")
    # Both rules turn into decorated functions
    assert "@rule(" in src
    assert "def fico_floor(" in src
    assert "def pricing_tier(" in src


def test_codegen_or_and_logic_chains():
    snapshot = [{
        "id": "R", "rule_id": "R", "rule_name": "Combined",
        "subsystem": "BUREAU_GATE", "priority": 10,
        "conditions": [
            {"field": "inquiries_last_3m", "operator": ">", "value": 3, "logic": "OR"},
            {"field": "inquiries_last_12m", "operator": ">", "value": 10, "logic": "AND"},
        ],
        "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                     "value": "REJECTED", "description": "TOO_MANY"}],
    }]
    src = render_python(_MockRepo(), _MockVersion(snapshot))
    ast.parse(src)
    assert " or " in src        # honoured the OR on the first condition
