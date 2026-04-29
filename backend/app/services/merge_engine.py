"""Merge engine — diff a candidate rule set against a Live Rule
Repository version and produce a MergeProposal with one item per
incoming or retired rule.

Slice 0 scope: classifies into the minimum useful set of categories.
EXACT_DUPLICATE / NEW_RULE / THRESHOLD_TIGHTENING / THRESHOLD_RELAXATION
/ OPPOSITE_DIRECTION / ACTION_DRIFT / REMOVED_RULE.

Coverage gaps and tiered-replacement detection are deferred to Phase 4
(slice 1).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.models.merge import (
    MergeItemCategory,
    MergeItemSeverity,
    MergeSuggestedAction,
)
from app.services.canonical_key import (
    operator_class,
    primary_action,
    primary_field,
    primary_operator,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _primary_threshold(conditions: list[dict] | None) -> Any:
    if not conditions:
        return None
    first = conditions[0] if isinstance(conditions[0], dict) else {}
    return first.get("value")


def _safe_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _is_numeric_pair(a: Any, b: Any) -> bool:
    return _safe_float(a) is not None and _safe_float(b) is not None


def _direction(operator: str | None) -> str:
    """Return GT / LT / EQ / RANGE / IN / OTHER."""
    return operator_class(operator)


def _is_tighter(op_class: str, old: float, new: float) -> bool:
    """Is `new` a stricter threshold than `old` for the given operator class?

    Example: dti_ratio > X → REJECT.
        Tighter = lower X (rejects more applicants).
    Example: bureau_score < X → REJECT.
        Tighter = higher X (rejects more applicants).
    """
    if op_class == "GT":
        return new < old
    if op_class == "LT":
        return new > old
    return False  # for EQ/RANGE/IN we don't reason about tightness here


def _opposite_direction(live_op: str, incoming_op: str) -> bool:
    return {live_op, incoming_op} == {"GT", "LT"}


# ── Result type ──────────────────────────────────────────────────────────

@dataclass
class ProposalItemSpec:
    """Plain-data spec for a MergeProposalItem to be created.

    Service layer turns these into ORM rows attached to a MergeProposal.
    """
    category: MergeItemCategory
    severity: MergeItemSeverity
    suggested_action: MergeSuggestedAction
    incoming_rule_id: str | None
    live_rule_id: str | None
    canonical_key: str | None
    diff: dict[str, Any]
    rationale: str
    confidence: float = 1.0


# ── Public API ───────────────────────────────────────────────────────────

def classify_pair(
    incoming: dict | None,
    live: dict | None,
) -> ProposalItemSpec:
    """Classify one incoming-vs-live rule pair into a MergeProposalItem
    spec. Either side may be None (for pure NEW or REMOVED).

    Each `dict` is the serialized form of a Rule:
      {id, rule_id, rule_name, conditions, actions, canonical_key,
       semantic_signature, subsystem, ...}
    """
    if incoming is None and live is not None:
        return _spec_removed(live)

    if live is None and incoming is not None:
        return _spec_new(incoming)

    if incoming is None and live is None:  # defensive
        raise ValueError("classify_pair called with both sides None")

    return _spec_collision(incoming, live)


def diff_rule_sets(
    incoming_rules: Iterable[dict],
    live_rules: Iterable[dict],
) -> list[ProposalItemSpec]:
    """Produce one MergeProposalItem spec per incoming or retired rule.

    Pairing strategy: by canonical_key. If multiple incoming rules share
    the same canonical_key as one live rule (e.g. tier replacement),
    each is treated independently in this slice — slice 1 introduces
    SUPERSEDE_GROUP detection.
    """
    incoming_by_key: dict[str, list[dict]] = {}
    for r in incoming_rules:
        key = r.get("canonical_key") or "UNCLASSIFIED"
        incoming_by_key.setdefault(key, []).append(r)

    live_by_key: dict[str, list[dict]] = {}
    for r in live_rules:
        key = r.get("canonical_key") or "UNCLASSIFIED"
        live_by_key.setdefault(key, []).append(r)

    seen_keys: set[str] = set()
    specs: list[ProposalItemSpec] = []

    # 1) Pair up by canonical_key
    for key, in_rules in incoming_by_key.items():
        seen_keys.add(key)
        live_match = live_by_key.get(key, [])

        if not live_match:
            for r in in_rules:
                specs.append(classify_pair(incoming=r, live=None))
            continue

        # Pair greedily: first incoming with first live, etc.
        for i, in_rule in enumerate(in_rules):
            if i < len(live_match):
                specs.append(classify_pair(incoming=in_rule, live=live_match[i]))
            else:
                specs.append(classify_pair(incoming=in_rule, live=None))

        # Extra live rules with same key but no incoming match: keep as-is
        # (no item) — slice 1 will treat these as RETIRE candidates if the
        # BRD's retirement signals say so.

    # 2) Live rules with no incoming pairing at all → no item in slice 0
    # (REMOVED_RULE detection requires retirement signals which arrive in
    # phase 4). We'll list the live keys that vanished as informational
    # items in slice 1.
    _ = seen_keys  # placeholder for future use

    return specs


# ── Spec builders ────────────────────────────────────────────────────────

def _spec_new(incoming: dict) -> ProposalItemSpec:
    return ProposalItemSpec(
        category=MergeItemCategory.NEW_RULE,
        severity=MergeItemSeverity.INFO,
        suggested_action=MergeSuggestedAction.ACCEPT,
        incoming_rule_id=str(incoming.get("id")) if incoming.get("id") else None,
        live_rule_id=None,
        canonical_key=incoming.get("canonical_key"),
        diff={
            "field": primary_field(incoming.get("conditions")),
            "operator": primary_operator(incoming.get("conditions")),
            "threshold": _primary_threshold(incoming.get("conditions")),
            "action": primary_action(incoming.get("actions")),
        },
        rationale="No matching rule in the live repository for this canonical_key.",
        confidence=0.95,
    )


def _spec_removed(live: dict) -> ProposalItemSpec:
    return ProposalItemSpec(
        category=MergeItemCategory.REMOVED_RULE,
        severity=MergeItemSeverity.INFO,
        suggested_action=MergeSuggestedAction.RETIRE,
        incoming_rule_id=None,
        live_rule_id=str(live.get("id")) if live.get("id") else None,
        canonical_key=live.get("canonical_key"),
        diff={
            "field": primary_field(live.get("conditions")),
            "operator": primary_operator(live.get("conditions")),
            "threshold": _primary_threshold(live.get("conditions")),
            "action": primary_action(live.get("actions")),
        },
        rationale="Live rule not present in incoming BRD; flagged for explicit retirement.",
        confidence=0.55,
    )


def _spec_collision(incoming: dict, live: dict) -> ProposalItemSpec:
    """Both sides share canonical_key — figure out the relationship."""
    in_op = primary_operator(incoming.get("conditions"))
    live_op = primary_operator(live.get("conditions"))
    in_thr = _primary_threshold(incoming.get("conditions"))
    live_thr = _primary_threshold(live.get("conditions"))
    in_act = primary_action(incoming.get("actions"))
    live_act = primary_action(live.get("actions"))
    field = primary_field(incoming.get("conditions"))
    canonical = incoming.get("canonical_key") or live.get("canonical_key")

    base_diff = {
        "field": field,
        "operator_live": live_op,
        "operator_incoming": in_op,
        "threshold_live": live_thr,
        "threshold_incoming": in_thr,
        "action_live": live_act,
        "action_incoming": in_act,
    }

    incoming_id = str(incoming.get("id")) if incoming.get("id") else None
    live_id = str(live.get("id")) if live.get("id") else None

    # 1) Hard: opposite-direction operators on the same field
    if _opposite_direction(live_op, in_op):
        return ProposalItemSpec(
            category=MergeItemCategory.OPPOSITE_DIRECTION,
            severity=MergeItemSeverity.HARD,
            suggested_action=MergeSuggestedAction.NEEDS_HUMAN,
            incoming_rule_id=incoming_id,
            live_rule_id=live_id,
            canonical_key=canonical,
            diff=base_diff,
            rationale=(
                f"Live and incoming rules use opposite operators on `{field}` "
                f"(live: {live_op}, incoming: {in_op}). Resolve manually."
            ),
            confidence=0.95,
        )

    # 2) Hard: same key/threshold but different action class (REJECT → FLAG)
    if (
        in_op == live_op
        and _is_numeric_pair(in_thr, live_thr)
        and _safe_float(in_thr) == _safe_float(live_thr)
        and in_act != live_act
    ):
        return ProposalItemSpec(
            category=MergeItemCategory.ACTION_DRIFT,
            severity=MergeItemSeverity.HARD,
            suggested_action=MergeSuggestedAction.NEEDS_HUMAN,
            incoming_rule_id=incoming_id,
            live_rule_id=live_id,
            canonical_key=canonical,
            diff=base_diff,
            rationale=(
                f"Same threshold on `{field}` but action changed from "
                f"`{live_act}` to `{in_act}`. Semantic shift requires review."
            ),
            confidence=0.95,
        )

    # 3) Exact duplicate
    if (
        in_op == live_op
        and in_act == live_act
        and _safe_float(in_thr) is not None
        and _safe_float(in_thr) == _safe_float(live_thr)
    ):
        return ProposalItemSpec(
            category=MergeItemCategory.EXACT_DUPLICATE,
            severity=MergeItemSeverity.INFO,
            suggested_action=MergeSuggestedAction.DROP,
            incoming_rule_id=incoming_id,
            live_rule_id=live_id,
            canonical_key=canonical,
            diff=base_diff,
            rationale="Identical to an existing live rule; safe to drop.",
            confidence=1.0,
        )

    # 4) Threshold drift (same operator, same action, different value)
    if (
        in_op == live_op
        and in_act == live_act
        and _is_numeric_pair(in_thr, live_thr)
    ):
        in_v = _safe_float(in_thr)
        live_v = _safe_float(live_thr)
        if _is_tighter(in_op, live_v, in_v):
            return ProposalItemSpec(
                category=MergeItemCategory.THRESHOLD_TIGHTENING,
                severity=MergeItemSeverity.SOFT,
                suggested_action=MergeSuggestedAction.SUPERSEDE,
                incoming_rule_id=incoming_id,
                live_rule_id=live_id,
                canonical_key=canonical,
                diff=base_diff,
                rationale=(
                    f"`{field}` threshold tightened from {live_v} to {in_v} "
                    f"(stricter, same direction & action)."
                ),
                confidence=0.95,
            )
        return ProposalItemSpec(
            category=MergeItemCategory.THRESHOLD_RELAXATION,
            severity=MergeItemSeverity.SOFT,
            suggested_action=MergeSuggestedAction.SUPERSEDE,
            incoming_rule_id=incoming_id,
            live_rule_id=live_id,
            canonical_key=canonical,
            diff=base_diff,
            rationale=(
                f"`{field}` threshold relaxed from {live_v} to {in_v} "
                f"(looser, same direction & action). Confirm intent."
            ),
            confidence=0.85,
        )

    # 5) Catch-all: collision we can't classify cleanly
    return ProposalItemSpec(
        category=MergeItemCategory.OVERLAPPING_RANGE,
        severity=MergeItemSeverity.SOFT,
        suggested_action=MergeSuggestedAction.NEEDS_HUMAN,
        incoming_rule_id=incoming_id,
        live_rule_id=live_id,
        canonical_key=canonical,
        diff=base_diff,
        rationale="Same canonical key but neither a clean duplicate nor a simple drift.",
        confidence=0.6,
    )
