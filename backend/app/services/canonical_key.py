"""Canonical key generation for cross-BRD rule identity.

The canonical_key is a deterministic short string that represents the
*identity* of a rule independent of which BRD authored it or what its
exact (numeric) threshold value is. The merge engine uses it to
recognize "this incoming rule is talking about the same thing as that
live rule."

Key shape (current — Slice 12+):
    {SUBSYSTEM}::{primary_field}::{operator_class}[::{eq_discriminator}]::{action_class}::{target_class}

Where:
- SUBSYSTEM is the Subsystem enum value (or UNCLASSIFIED)
- primary_field is the leading condition's field, normalized
- operator_class is the operator family: GT|LT|EQ|RANGE|IN|ALWAYS
- eq_discriminator is included ONLY when operator is EQ/NEQ/IN/NIN AND
  the comparison value is non-numeric (a string/enum). This separates
  lookup-table variants like `IF segment==A → SET tier=GOLD` from
  `IF segment==B → SET tier=SILVER`, which previously collapsed into
  one canonical_key and got silently dropped during merge apply.
  Numeric threshold comparisons (==680, !=720) intentionally omit the
  value so THRESHOLD_TIGHTENING / RELAXATION variants still pair.
- action_class is the action family: REJECT|FLAG|CAP|MODIFY|APPROVE
- target_class is the normalized output target (DECISION|RATE|AMOUNT|
  REVIEW|<raw upper-cased field>). Distinguishes rules that share the
  same trigger but write to different output fields (e.g. segment==A
  → SET max_tenure vs segment==A → ADJUST eligible_amount).

Examples:
    DTI_GATE::dti_ratio::GT::REJECT::DECISION
    BUREAU_GATE::bureau_score::LT::REJECT::DECISION
    SCORING_MODEL::credit_risk_band::EQ::LOW::CAP::CUSTOMER_SEGMENT
    AMOUNT_CAP::customer_segment::EQ::SEGMENT_A::MODIFY::AMOUNT
    AMOUNT_CAP::customer_segment::EQ::SEGMENT_A::CAP::MAX_TENURE_MONTHS

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


# Guard fields are scoping filters (loan_type=PERSONAL, application_type=...,
# repeat_type=..., credit_policy=...) that the LLM frequently puts in
# condition[0]. They aren't the rule's actual policy field — that's the
# threshold being checked next. We skip past these when picking the
# "primary" field for canonical_key/pairing_key purposes.
_GUARD_FIELDS = frozenset({
    "loan_type", "application_type", "repeat_type", "credit_policy",
    "credit_policy_version", "loan_purpose", "currency", "customer_segment",
    "segment", "product", "product_type", "borrower_segment",
})


def _first_non_guard(conditions: list[dict] | None) -> dict:
    """Return the first condition whose field isn't a generic guard
    (loan_type/application_type/etc.). Falls back to conditions[0] if
    every field is a guard, and to {} if there are no conditions."""
    if not conditions:
        return {}
    for cond in conditions:
        if not isinstance(cond, dict):
            continue
        field = normalize_field(cond.get("field"))
        if field not in _GUARD_FIELDS and field != "unknown_field":
            return cond
    # All fields were guards — fall back to the first dict-shaped condition
    for cond in conditions:
        if isinstance(cond, dict):
            return cond
    return {}


def primary_field(conditions: list[dict] | None) -> str:
def primary_field(conditions: list[dict] | None) -> str:
    """Return the field of the first non-guard condition (or fall back).

    Skipping guard fields (`loan_type`, `application_type`, …) is what
    makes the canonical_key meaningful when the LLM emits rules in the
    "guard then policy threshold" shape that BRDs commonly express in
    prose. Without this skip, every "for personal loans, X" rule ends
    up with the same canonical_key regardless of X.
    """
    cond = _first_non_guard(conditions)
    if not cond:
        return "unknown_field"
    return normalize_field(cond.get("field"))
    if not cond:
        return "unknown_field"
    return normalize_field(cond.get("field"))


def primary_operator(conditions: list[dict] | None) -> str:
def primary_operator(conditions: list[dict] | None) -> str:
    cond = _first_non_guard(conditions)
    if not cond:
        return "UNK"
    return operator_class(cond.get("operator"))
    if not cond:
        return "UNK"
    return operator_class(cond.get("operator"))


def primary_action(actions: list[dict] | None) -> str:
    if not actions:
        return "UNK"
    first = actions[0] if isinstance(actions[0], dict) else {}
    return action_class(first.get("action_type"))


def _is_numeric_value(v: Any) -> bool:
    """True when v is (or string-parses to) a number — used to decide
    whether an equality comparison is a numeric threshold (don't include
    in the discriminator so tightening pairs still match) vs an enum
    bucket (include so SEGMENT_A / SEGMENT_B don't collide)."""
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False


def _equality_discriminator(conditions: list[dict] | None) -> str:
    """Return a discriminator string when the primary condition is an
    equality / membership check on a NON-NUMERIC value (enum/string).
    Empty string otherwise — so numeric threshold variants
    (e.g. `fico < 680` vs `fico < 720`) continue to share canonical_key
    and the merge engine can still detect THRESHOLD_TIGHTENING.
    """
    cond = _first_non_guard(conditions)
    if not cond:
        return ""
    op = operator_class(cond.get("operator"))
    if op not in ("EQ", "NEQ", "IN", "NIN"):
        return ""
    val = cond.get("value")
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        non_numeric = [str(v).strip().upper() for v in val if not _is_numeric_value(v)]
        if not non_numeric:
            return ""
        return ",".join(sorted(non_numeric))
    if _is_numeric_value(val):
        return ""
    return str(val).strip().upper()


def _primary_target_class(actions: list[dict] | None) -> str:
    """target_class of the first action's target_field — DECISION, RATE,
    AMOUNT, REVIEW, or the raw upper-cased field name. Lets two rules
    that share a trigger but write to different output fields carry
    different canonical_keys."""
    if not actions:
        return "NOTARGET"
    first = actions[0] if isinstance(actions[0], dict) else {}
    tgt = first.get("target_field")
    if not tgt:
        return "NOTARGET"
    return target_class(tgt)


def make_canonical_key(
    subsystem: Subsystem | str | None,
    conditions: list[dict] | None,
    actions: list[dict] | None,
) -> str:
    """Build the canonical key for a rule (full identity).

    Stable across BRDs as long as the rule operates on the same primary
    field, with the same operator family / equality bucket / action
    family / output target. Includes:

    - action_class — REJECT vs FLAG on the same condition carry
      different identity
    - eq_discriminator (when applicable) — `segment==A` and `segment==B`
      are different rules, not the same one
    - target_class — `segment==A → SET tier` and `segment==A → ADJUST
      amount` are different rules, not the same one

    Numeric threshold variants (`fico < 680` vs `fico < 720`) keep the
    SAME canonical_key so the merge engine can pair them and detect
    THRESHOLD_TIGHTENING.

    Unconditional rules (no usable condition) derive their primary field
    from the action's target_field with operator ALWAYS.
    """
    sub = subsystem.value if isinstance(subsystem, Subsystem) else (
        str(subsystem) if subsystem else Subsystem.UNCLASSIFIED.value
    )
    parts = [
        sub,
        primary_field(conditions, actions),
        primary_operator(conditions, actions),
    ]
    disc = _equality_discriminator(conditions)
    if disc:
        parts.append(disc)
    parts.extend([
        primary_action(actions),
        _primary_target_class(actions),
    ])
    return "::".join(parts)


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
