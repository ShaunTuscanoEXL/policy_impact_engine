"""Canonical key generation for cross-BRD rule identity.

The canonical_key is a deterministic short string that represents the
*identity* of a rule independent of which BRD authored it or what its
exact threshold value is. The merge engine uses it to recognize "this
incoming rule is talking about the same thing as that live rule."

Key shape:
    {SUBSYSTEM}::{primary_field}::{operator_class}::{action_class}

Where:
- SUBSYSTEM is the Subsystem enum value (or UNCLASSIFIED)
- primary_field is the leading condition's field, normalized
- operator_class is the operator family: GT|LT|EQ|RANGE|IN
- action_class is the action family: REJECT|FLAG|CAP|MODIFY

Examples:
    DTI_GATE::dti_ratio::GT::REJECT
    BUREAU_GATE::bureau_score::LT::REJECT
    PRICING_TIER::bureau_score::RANGE::MODIFY
    AMOUNT_CAP::desired_amount::GT::CAP

Two rules with the same canonical_key are candidates for SUPERSEDE /
DUPLICATE / OPPOSITE_DIRECTION classification by the merge engine. They
are NOT necessarily the same rule — the merge engine still inspects
thresholds and action targets to make a final decision.
"""
from __future__ import annotations

from typing import Any

from app.models.rule import Subsystem


# ── Operator → operator-class normalization ──────────────────────────────
_OPERATOR_CLASS = {
    ">":  "GT",
    ">=": "GT",
    "gt": "GT",
    "gte": "GT",
    "<":  "LT",
    "<=": "LT",
    "lt": "LT",
    "lte": "LT",
    "==": "EQ",
    "=":  "EQ",
    "eq": "EQ",
    "!=": "NEQ",
    "ne": "NEQ",
    "in": "IN",
    "not_in": "NIN",
    "between": "RANGE",
    "range": "RANGE",
}


# ── Action type → action-class normalization ─────────────────────────────
_ACTION_CLASS = {
    "REJECT": "REJECT",
    "DECLINE": "REJECT",
    "AUTO_REJECT": "REJECT",
    "FLAG": "FLAG",
    "MANUAL_REVIEW": "FLAG",
    "REVIEW": "FLAG",
    "CAP": "CAP",
    "SET": "CAP",        # SET on amount fields is effectively a cap
    "ADJUST": "MODIFY",
    "MODIFY": "MODIFY",
    "PRICE": "MODIFY",
    "APPROVE": "APPROVE",
}


def operator_class(op: str | None) -> str:
    if not op:
        return "UNK"
    return _OPERATOR_CLASS.get(str(op).strip().lower(), str(op).upper())


def action_class(action_type: str | None) -> str:
    if not action_type:
        return "UNK"
    return _ACTION_CLASS.get(str(action_type).strip().upper(), str(action_type).upper())


def normalize_field(name: str | None) -> str:
    """Lowercase + collapse whitespace/dashes/spaces to underscore."""
    if not name:
        return "unknown_field"
    s = str(name).strip().lower()
    return (
        s.replace(" ", "_")
         .replace("-", "_")
         .replace(".", "_")
    )


def primary_field(conditions: list[dict] | None) -> str:
    """Return the field of the first condition (or 'unknown_field')."""
    if not conditions:
        return "unknown_field"
    first = conditions[0] if isinstance(conditions[0], dict) else {}
    return normalize_field(first.get("field"))


def primary_operator(conditions: list[dict] | None) -> str:
    if not conditions:
        return "UNK"
    first = conditions[0] if isinstance(conditions[0], dict) else {}
    return operator_class(first.get("operator"))


def primary_action(actions: list[dict] | None) -> str:
    if not actions:
        return "UNK"
    first = actions[0] if isinstance(actions[0], dict) else {}
    return action_class(first.get("action_type"))


def make_canonical_key(
    subsystem: Subsystem | str | None,
    conditions: list[dict] | None,
    actions: list[dict] | None,
) -> str:
    """Build the canonical key for a rule (full identity).

    Stable across BRDs as long as the rule operates on the same primary
    field, with the same operator family and the same action family.
    Includes action_class so that two rules with different action types
    (e.g. REJECT vs FLAG on the same condition) carry different identity.
    """
    sub = subsystem.value if isinstance(subsystem, Subsystem) else (
        str(subsystem) if subsystem else Subsystem.UNCLASSIFIED.value
    )
    return "::".join([
        sub,
        primary_field(conditions),
        primary_operator(conditions),
        primary_action(actions),
    ])


# ── Target-class normalization ───────────────────────────────────────────
# Used by the pairing_key so that two rules whose action targets the same
# *thing* can be paired up by the merge engine even if they differ in
# action_type (REJECT vs FLAG vs MANUAL_REVIEW). This is what makes
# ACTION_DRIFT detectable.
_TARGET_CLASS = {
    "decision_status": "DECISION",
    "decision":        "DECISION",
    "status":          "DECISION",
    "outcome":         "DECISION",
    "verdict":         "DECISION",
    "interest_rate":   "RATE",
    "apr":             "RATE",
    "rate":            "RATE",
    "eligible_amount": "AMOUNT",
    "loan_amount":     "AMOUNT",
    "max_eligible_amount": "AMOUNT",
    "desired_amount":  "AMOUNT",
    "manual_review":   "REVIEW",
    "review_queue":    "REVIEW",
}


def target_class(target: str | None) -> str:
    if not target:
        return "DECISION"  # default — most actions are decision-affecting
    norm = normalize_field(target)
    return _TARGET_CLASS.get(norm, norm.upper())


def primary_target_class(actions: list[dict] | None) -> str:
    if not actions:
        return "DECISION"
    first = actions[0] if isinstance(actions[0], dict) else {}
    return target_class(first.get("target_field"))


def make_pairing_key(
    subsystem: Subsystem | str | None,
    conditions: list[dict] | None,
    actions: list[dict] | None,
) -> str:
    """Pairing key for cross-BRD collision detection.

    Strips action_class but keeps target_class. Two rules with the same
    pairing_key but different action_class are paired so the merge engine
    can flag ACTION_DRIFT instead of treating them as unrelated NEW_RULEs.

    Example:
        REJECT when dti > 0.43 → DTI_GATE::dti_ratio::GT::DECISION
        FLAG   when dti > 0.43 → DTI_GATE::dti_ratio::GT::DECISION  (same)
        ADJUST interest_rate when dti > 0.43
                              → DTI_GATE::dti_ratio::GT::RATE       (different)
    """
    sub = subsystem.value if isinstance(subsystem, Subsystem) else (
        str(subsystem) if subsystem else Subsystem.UNCLASSIFIED.value
    )
    return "::".join([
        sub,
        primary_field(conditions),
        primary_operator(conditions),
        primary_target_class(actions),
    ])


def pairing_key_from_dict(rule_dict: dict) -> str:
    """Compute the pairing_key from a serialized rule dict — used by the
    merge engine when grouping rules across the candidate vs live sets."""
    return make_pairing_key(
        rule_dict.get("subsystem"),
        rule_dict.get("conditions") or [],
        rule_dict.get("actions") or [],
    )


def make_semantic_signature(
    conditions: list[dict] | None,
    actions: list[dict] | None,
) -> dict[str, Any]:
    """Normalized representation of a rule used for diffing.

    Produces a small dict that captures the structural shape without
    BRD-specific text — used by the merge engine to detect threshold
    drift, action drift, and overlapping ranges.
    """
    conds = conditions or []
    acts = actions or []
    return {
        "fields":      [normalize_field(c.get("field")) for c in conds if isinstance(c, dict)],
        "operators":   [operator_class(c.get("operator")) for c in conds if isinstance(c, dict)],
        "thresholds":  [c.get("value") for c in conds if isinstance(c, dict)],
        "logic":       [str(c.get("logic", "AND")).upper() for c in conds if isinstance(c, dict)],
        "action_types": [action_class(a.get("action_type")) for a in acts if isinstance(a, dict)],
        "action_targets": [normalize_field(a.get("target_field")) for a in acts if isinstance(a, dict)],
    }
