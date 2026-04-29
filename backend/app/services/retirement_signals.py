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
    normalize_field,
    operator_class,
)


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
          "action_class": "REJECT"   # optional
        }

    Returns:
        {"canonical_key": "DTI_GATE::dti_ratio::GT::REJECT",
         "basis": "...", "evidence_section": "..."}
        or ``None`` if required fields are missing.
    """
    if not isinstance(pattern, dict):
        return None
    subsystem = (pattern.get("subsystem") or "").strip().upper()
    field = normalize_field(pattern.get("field"))
    op = operator_class(pattern.get("operator_class") or pattern.get("operator"))
    if not subsystem or field == "unknown_field" or op == "UNK":
        return None
    act = action_class(pattern.get("action_class") or pattern.get("action_type") or "REJECT")

    return {
        "canonical_key": f"{subsystem}::{field}::{op}::{act}",
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
