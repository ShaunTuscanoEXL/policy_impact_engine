"""Pure-Python rule evaluator.

Loads a snapshot (list of rule dicts) and a LoanRecord, evaluates rules
in priority order grouped by subsystem (gates first, then pricing, then
exposure, then scoring), and returns a DecisionResult that summarizes
which rules fired and what the final decision is.

The evaluator is intentionally agnostic to where the loan record came
from — it reads from the same JSON shape produced by
``seed_loan_records.py``. This means the same engine works for:
- impact runs against the production loan_records corpus
- ad-hoc what-if simulations from the UI
- test_case suite execution (slice 3+)

Slice 2 scope:
- 4 action types: REJECT, FLAG, CAP, MODIFY (matches codegen output)
- All standard operators incl. between, in, not_in
- AND / OR chained conditions (via cond["logic"] on the previous cond)
- Returns a DecisionResult with: decision, fired_rules, reasons, terminal_rule
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services.field_registry import resolve_field_path


# ── Subsystem evaluation order ───────────────────────────────────────────
# Mirrors codegen output order: gates first (so a REJECT terminates),
# then pricing/amount adjustments, then scoring overlays.
_EVAL_ORDER = [
    "REGULATORY_FLOOR",
    "BUREAU_GATE",
    "INCOME_GATE",
    "DTI_GATE",
    "EMPLOYMENT_GATE",
    "BANKING_BEHAVIOR",
    "FRAUD_SIGNAL",
    "EXPOSURE_LIMIT",
    "AMOUNT_CAP",
    "PRICING_TIER",
    "RATE_MODIFIER",
    "SCORING_MODEL",
    "UNCLASSIFIED",
]
_EVAL_RANK = {sub: i for i, sub in enumerate(_EVAL_ORDER)}


# ── Loan context: dot-path-aware accessor over the request_payload ──────

class LoanContext:
    """Read-only view over a loan record's request_payload that resolves
    rule field names through the existing field_registry.

    Examples (using a US-fintech seed record):
        ctx["bureau_score"]              -> 742
        ctx["dti_ratio"]                 -> 0.257
        ctx["banking_stability_index"]   -> 0.83
    """

    __slots__ = ("_request_payload", "_loan_application_id")

    def __init__(self, request_payload: dict, loan_application_id: str | None = None):
        self._request_payload = request_payload or {}
        self._loan_application_id = loan_application_id

    @property
    def loan_application_id(self) -> str | None:
        return self._loan_application_id

    def __getitem__(self, field_name: str) -> Any:
        path = resolve_field_path(field_name) or field_name
        return self._walk(path)

    def get(self, field_name: str, default: Any = None) -> Any:
        try:
            v = self[field_name]
            return default if v is None else v
        except (KeyError, TypeError):
            return default

    def _walk(self, dot_path: str) -> Any:
        node: Any = self._request_payload
        for part in dot_path.split("."):
            if isinstance(node, dict):
                node = node.get(part)
            else:
                return None
            if node is None:
                return None
        return node


# ── Decision result type ────────────────────────────────────────────────

@dataclass
class FiredRule:
    rule_id: str
    rule_name: str
    subsystem: str
    action_type: str
    target_field: str | None
    value: Any
    reason: str | None


@dataclass
class DecisionResult:
    """Outcome of evaluating a rule snapshot against a single loan."""
    decision: str                                  # APPROVED | REJECTED | FLAGGED | CAPPED
    fired_rules: list[FiredRule] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    terminal_rule_id: str | None = None
    interest_rate_modifiers: list[float] = field(default_factory=list)
    amount_caps: list[float] = field(default_factory=list)

    def is_rejected(self) -> bool:
        return self.decision == "REJECTED"


# ── Operator evaluation ─────────────────────────────────────────────────

def _coerce_number(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _eval_one_condition(cond: dict, ctx: LoanContext) -> bool:
    if not isinstance(cond, dict):
        return False
    field_name = cond.get("field")
    op = (cond.get("operator") or "").strip().lower()
    target_value = cond.get("value")
    actual = ctx.get(field_name)

    if actual is None:
        return False  # field missing → condition can't fire

    # Numeric ops
    if op in (">", "gt"):
        a, b = _coerce_number(actual), _coerce_number(target_value)
        return a is not None and b is not None and a > b
    if op in (">=", "gte"):
        a, b = _coerce_number(actual), _coerce_number(target_value)
        return a is not None and b is not None and a >= b
    if op in ("<", "lt"):
        a, b = _coerce_number(actual), _coerce_number(target_value)
        return a is not None and b is not None and a < b
    if op in ("<=", "lte"):
        a, b = _coerce_number(actual), _coerce_number(target_value)
        return a is not None and b is not None and a <= b

    # Equality
    if op in ("==", "=", "eq"):
        a_num = _coerce_number(actual)
        b_num = _coerce_number(target_value)
        if a_num is not None and b_num is not None:
            return a_num == b_num
        return str(actual) == str(target_value)
    if op in ("!=", "ne"):
        a_num = _coerce_number(actual)
        b_num = _coerce_number(target_value)
        if a_num is not None and b_num is not None:
            return a_num != b_num
        return str(actual) != str(target_value)

    # Set membership
    if op in ("in",):
        if isinstance(target_value, (list, tuple, set)):
            return actual in target_value
        return False
    if op in ("not_in", "not in"):
        if isinstance(target_value, (list, tuple, set)):
            return actual not in target_value
        return False

    # Range
    if op in ("between", "range"):
        if isinstance(target_value, (list, tuple)) and len(target_value) == 2:
            lo, hi = _coerce_number(target_value[0]), _coerce_number(target_value[1])
            a = _coerce_number(actual)
            return None not in (lo, hi, a) and lo <= a <= hi
        return False

    # Unknown operator → treat as not-fired (defensive)
    return False


def _eval_conditions(conditions: list[dict], ctx: LoanContext) -> bool:
    """Combine conditions via the per-condition `logic` field (AND/OR).

    Logic of condition[i] joins it with condition[i-1]. This mirrors the
    codegen renderer: rule fires when the chain evaluates truthy under
    Python boolean semantics.
    """
    if not conditions:
        return True
    result = _eval_one_condition(conditions[0], ctx)
    for i in range(1, len(conditions)):
        prev_logic = (conditions[i - 1].get("logic") if isinstance(conditions[i - 1], dict) else "AND") or "AND"
        cur = _eval_one_condition(conditions[i], ctx)
        if str(prev_logic).upper() == "OR":
            result = result or cur
        else:
            result = result and cur
    return result


# ── Rule snapshot evaluation ────────────────────────────────────────────

def _sort_key(rule: dict) -> tuple[int, int, str]:
    sub = (rule.get("subsystem") or "UNCLASSIFIED").upper()
    return (
        _EVAL_RANK.get(sub, 999),         # subsystem order
        -int(rule.get("priority", 0)),    # higher priority first
        str(rule.get("rule_id", "")),     # stable tiebreaker
    )


def _action_to_fired(rule: dict, action: dict) -> FiredRule:
    act_type = str(action.get("action_type", "")).strip().upper()
    return FiredRule(
        rule_id=str(rule.get("rule_id") or rule.get("id") or "?"),
        rule_name=str(rule.get("rule_name") or rule.get("rule_id") or "?"),
        subsystem=str(rule.get("subsystem", "UNCLASSIFIED")),
        action_type=act_type,
        target_field=str(action.get("target_field") or "") or None,
        value=action.get("value"),
        reason=str(action.get("description") or "") or None,
    )


def evaluate_snapshot(
    snapshot: Iterable[dict],
    request_payload: dict,
    *,
    loan_application_id: str | None = None,
) -> DecisionResult:
    """Run every rule in `snapshot` against a single loan request_payload
    in canonical (subsystem, priority) order.

    Decision rules:
    - First REJECT terminates (gate-style underwriting)
    - FLAG fires accumulate; final decision becomes FLAGGED if no REJECT
    - CAP / MODIFY accumulate but don't change the final decision label
      (the impact summary tracks them separately)
    - If no terminal action fires the decision is APPROVED
    """
    ctx = LoanContext(request_payload, loan_application_id=loan_application_id)
    rules_sorted = sorted(snapshot, key=_sort_key)

    fired: list[FiredRule] = []
    reasons: list[str] = []
    terminal_rule_id: str | None = None
    decision = "APPROVED"
    rate_mods: list[float] = []
    amount_caps: list[float] = []

    for rule in rules_sorted:
        conditions = rule.get("conditions") or []
        actions = rule.get("actions") or []
        if not _eval_conditions(conditions, ctx):
            continue
        for act in actions:
            fr = _action_to_fired(rule, act)
            fired.append(fr)
            if fr.reason:
                reasons.append(fr.reason)
            if fr.action_type in ("REJECT", "DECLINE", "AUTO_REJECT"):
                decision = "REJECTED"
                terminal_rule_id = fr.rule_id
                break  # stop processing this rule's other actions
            if fr.action_type in ("FLAG", "MANUAL_REVIEW", "REVIEW"):
                if decision == "APPROVED":
                    decision = "FLAGGED"
            if fr.action_type in ("CAP", "SET") and isinstance(fr.value, (int, float)):
                amount_caps.append(float(fr.value))
            if fr.action_type in ("ADJUST", "MODIFY") and isinstance(fr.value, (int, float)):
                rate_mods.append(float(fr.value))
        if terminal_rule_id:
            break

    return DecisionResult(
        decision=decision,
        fired_rules=fired,
        reasons=reasons,
        terminal_rule_id=terminal_rule_id,
        interest_rate_modifiers=rate_mods,
        amount_caps=amount_caps,
    )
