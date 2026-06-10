"""Convert LLM-emitted ``retires_pattern`` hints into canonical_key
retirement signals consumed by the merge engine.

Slice 1 ships the wiring; the LLM prompt update is in
``app/pipeline/rule_extractor.py`` SYSTEM_PROMPT. The merge engine
applies signals in :func:`app.services.merge_engine.diff_rule_sets`.
"""
from __future__ import annotations

from typing import Iterable

from app.services.canonical_key import (
    action_class,
    make_canonical_key,
    normalize_field,
    operator_class,
)


# Operator-class → representative operator. The LLM-emitted retires_pattern
# block only specifies the operator FAMILY (GT/LT/EQ/...), not a specific
# operator. make_canonical_key needs a concrete operator string, so we map
# back to a canonical exemplar that round-trips through operator_class().
_OP_CLASS_TO_OP = {
    "GT": ">", "LT": "<", "EQ": "==", "NEQ": "!=",
    "IN": "in", "NIN": "not_in", "RANGE": "between",
}


def signal_from_retires_pattern(pattern: dict) -> dict | None:
    """Build a canonical_key-shaped retirement signal from an
    LLM-emitted ``retires_pattern`` block.

    Pattern shape (loose; tolerates partial fields):
        {
          "subsystem": "DTI_GATE",
          "field": "dti_ratio",
          "operator_class": "GT",
          "basis": "explicit_replacement",
          "evidence_section": "Section 4.1",
          "action_class": "REJECT",        # optional, defaults REJECT
          "target_field": "decision_status" # optional, defaults decision_status
        }

    The signal's canonical_key MUST match the format produced by
    :func:`make_canonical_key` so the merge engine can compare against
    HEAD-snapshot keys directly. We construct conditions/actions from
    the loose pattern and delegate, instead of hand-formatting (which
    drifted out of sync after Slice 12 added the target_class suffix).

    Returns ``None`` if required fields are missing.
    """
    if not isinstance(pattern, dict):
        return None
    subsystem = (pattern.get("subsystem") or "").strip().upper()
    field = normalize_field(pattern.get("field"))
    op_cls = operator_class(pattern.get("operator_class") or pattern.get("operator"))
    if not subsystem or field == "unknown_field" or op_cls == "UNK":
        return None
    act_cls = action_class(
        pattern.get("action_class") or pattern.get("action_type") or "REJECT"
    )
    target_field = pattern.get("target_field") or "decision_status"

    # Reconstruct minimal conditions/actions so make_canonical_key can
    # produce a key in the current shape. We use a representative numeric
    # threshold (0) so the equality_discriminator stays empty — retirement
    # signals identify a rule FAMILY (subsystem+field+op+action+target),
    # not a specific lookup-table variant.
    op_exemplar = _OP_CLASS_TO_OP.get(op_cls, "==")
    conditions = [{"field": field, "operator": op_exemplar, "value": 0, "logic": "AND"}]
    # Map action_class back to a representative action_type for the
    # canonical_key generator (it re-normalizes via _ACTION_CLASS anyway).
    actions = [{
        "action_type": act_cls,
        "target_field": target_field,
        "value": "",
        "description": "",
    }]
    ck = make_canonical_key(subsystem, conditions, actions)

    return {
        "canonical_key": ck,
        "basis": pattern.get("basis", "explicit"),
        "evidence_section": pattern.get("evidence_section"),
    }


def extract_retirement_signals(llm_rule_payload: Iterable[dict]) -> list[dict]:
    """Walk an LLM rule payload and pull out every ``retires_pattern``
    hint, converting each into a merge-engine-ready signal."""
    signals: list[dict] = []
    for rule in llm_rule_payload or []:
        if not isinstance(rule, dict):
            continue
        pattern = rule.get("retires_pattern")
        if not pattern:
            continue
        signal = signal_from_retires_pattern(pattern)
        if signal:
            signals.append(signal)
    return signals
