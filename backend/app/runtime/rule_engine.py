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
    """View over a loan record's request_payload that resolves rule field
    names through the existing field_registry, PLUS a writable overlay of
    derived values produced by SET actions during evaluation.

    The overlay is what makes multi-stage BRDs work: when a rule does
    ``SET customer_segment = SEGMENT_A``, the engine writes that into the
    overlay so a later rule's ``IF customer_segment == SEGMENT_A`` can
    read it. Raw payload fields are never mutated — the overlay is checked
    first, the raw payload second.

    Examples (using a US-fintech seed record):
        ctx["bureau_score"]              -> 742          (raw)
        ctx["dti_ratio"]                 -> 0.257        (raw)
        ctx.set("customer_segment", "A")                 (derived)
        ctx["customer_segment"]          -> "A"          (overlay)
    """

    __slots__ = ("_request_payload", "_loan_application_id", "_derived")

    def __init__(self, request_payload: dict, loan_application_id: str | None = None):
        self._request_payload = request_payload or {}
        self._loan_application_id = loan_application_id
        # Derived values written by SET actions during this evaluation.
        # Keyed by normalized field name (lower-cased, stripped) so a
        # condition referencing "customer_segment" or "Customer Segment"
        # both resolve to the same overlay slot.
        self._derived: dict[str, Any] = {}

    @property
    def loan_application_id(self) -> str | None:
        return self._loan_application_id

    @staticmethod
    def _norm(field_name: str) -> str:
        # Match the rest of the codebase: lower-case, strip, and collapse
        # spaces/dashes/dots to underscore so "Customer Segment",
        # "customer-segment", and "customer_segment" all resolve alike.
        s = str(field_name or "").strip().lower()
        return s.replace(" ", "_").replace("-", "_").replace(".", "_")

    def set(self, field_name: str, value: Any) -> None:
        """Write a derived value into the overlay so later rules can read
        it. Used by the engine when a SET action fires on a non-decision
        field."""
        self._derived[self._norm(field_name)] = value

    def __getitem__(self, field_name: str) -> Any:
        # Overlay (derived) wins over the raw payload — a rule that SET a
        # field overrides whatever the raw loan carried.
        norm = self._norm(field_name)
        if norm in self._derived:
            return self._derived[norm]
        # A DIRECT top-level key beats registry resolution. App-set flags
        # and derived inputs (e.g. dti_breach_regeneration) live at the
        # payload root; without this they would fuzzy-match an unrelated
        # registry field — "dti_breach_regeneration" → debt_to_income_ratio
        # — and silently read the wrong value.
        if field_name in self._request_payload:
            return self._request_payload[field_name]
        if norm in self._request_payload:
            return self._request_payload[norm]
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
    # Globally unique identifier from the snapshot (rule.id). The
    # human-readable `rule_id` can collide across BRDs (multiple rules
    # named "RULE-001" merged into a single repo); rule_uuid is the
    # only safe key for "did THIS specific rule fire?" comparisons.
    rule_uuid: str | None = None


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


# ── Dependency-aware ordering (producers before consumers) ───────────────
# A rule "produces" the target_field of each SET action; it "consumes" the
# field of each condition. When rule B's condition reads a field that rule
# A SETs, A must evaluate before B — otherwise B reads the raw payload
# (where the derived field doesn't exist) and never fires. The flat
# subsystem sort doesn't guarantee this (SCORING_MODEL, which produces
# customer_segment, sorts AFTER AMOUNT_CAP / RATE_MODIFIER, which consume
# it), so we topologically sort, tie-broken by the historical _sort_key.

def _norm_field(name: Any) -> str:
    s = str(name or "").strip().lower()
    return s.replace(" ", "_").replace("-", "_").replace(".", "_")


def _produced_fields(rule: dict) -> set[str]:
    out: set[str] = set()
    for a in rule.get("actions") or []:
        if not isinstance(a, dict):
            continue
        if str(a.get("action_type", "")).strip().upper() == "SET":
            tf = _norm_field(a.get("target_field"))
            if tf:
                out.add(tf)
    return out


def _consumed_fields(rule: dict) -> set[str]:
    out: set[str] = set()
    for c in rule.get("conditions") or []:
        if isinstance(c, dict):
            f = _norm_field(c.get("field"))
            if f:
                out.add(f)
    return out


def _compute_order(snapshot: list[dict]) -> list[int]:
    """Return rule indices in producer-before-consumer order.

    Kahn's algorithm with the historical _sort_key as the tiebreak among
    ready (in-degree-0) rules. This preserves gate short-circuit: a gate
    reading only raw fields has in-degree 0 and sorts early by subsystem
    rank, so a REJECT still fires before any pricing rule. Cyclic rules
    (A produces a field B consumes and vice-versa) are appended last in
    _sort_key order — the coherence validator flags the cycle.
    """
    import heapq

    n = len(snapshot)
    producers: dict[str, set[int]] = {}
    consumed_per: list[set[str]] = []
    for i, r in enumerate(snapshot):
        for f in _produced_fields(r):
            producers.setdefault(f, set()).add(i)
        consumed_per.append(_consumed_fields(r))

    adj: list[set[int]] = [set() for _ in range(n)]
    indeg = [0] * n
    for j in range(n):
        for f in consumed_per[j]:
            for i in producers.get(f, ()):
                if i == j:
                    continue  # self-loop (rule reads a field it also sets)
                if j not in adj[i]:
                    adj[i].add(j)
                    indeg[j] += 1

    keys = [_sort_key(snapshot[i]) for i in range(n)]
    ready = [(keys[i], i) for i in range(n) if indeg[i] == 0]
    heapq.heapify(ready)
    order: list[int] = []
    while ready:
        _, i = heapq.heappop(ready)
        order.append(i)
        for j in sorted(adj[i], key=lambda x: keys[x]):
            indeg[j] -= 1
            if indeg[j] == 0:
                heapq.heappush(ready, (keys[j], j))

    if len(order) < n:
        # Cycle — append the leftover rules deterministically.
        leftover = sorted((i for i in range(n) if i not in set(order)),
                          key=lambda i: keys[i])
        order.extend(leftover)
    return order


# Cache the computed order per snapshot so a 100k-loan impact run sorts
# once, not per loan. Keyed by the tuple of rule UUIDs — unique per repo
# version, so no cross-version collisions.
_ORDER_CACHE: dict[tuple, list[int]] = {}
_ORDER_CACHE_MAX = 256


def _order_rules(snapshot: list[dict]) -> list[dict]:
    key = tuple(
        str(r.get("id") or r.get("rule_id") or idx)
        for idx, r in enumerate(snapshot)
    )
    perm = _ORDER_CACHE.get(key)
    if perm is None:
        perm = _compute_order(snapshot)
        if len(_ORDER_CACHE) >= _ORDER_CACHE_MAX:
            _ORDER_CACHE.clear()
        _ORDER_CACHE[key] = perm
    return [snapshot[i] for i in perm]


def _action_to_fired(rule: dict, action: dict) -> FiredRule:
    act_type = str(action.get("action_type", "")).strip().upper()
    rule_uuid_raw = rule.get("id")
    return FiredRule(
        rule_id=str(rule.get("rule_id") or rule.get("id") or "?"),
        rule_name=str(rule.get("rule_name") or rule.get("rule_id") or "?"),
        subsystem=str(rule.get("subsystem", "UNCLASSIFIED")),
        action_type=act_type,
        target_field=str(action.get("target_field") or "") or None,
        value=action.get("value"),
        reason=str(action.get("description") or "") or None,
        rule_uuid=str(rule_uuid_raw) if rule_uuid_raw else None,
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
    # Producer-before-consumer order so derived fields (e.g. a rule that
    # SETs customer_segment) are available to rules that condition on them.
    rules_sorted = _order_rules(list(snapshot))

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
            # Write SET outputs into the context overlay so later rules
            # in producer-before-consumer order can read this derived
            # value. This is what makes multi-stage BRDs (eligibility →
            # classification → segment → pricing) actually execute.
            if fr.action_type == "SET" and fr.target_field:
                ctx.set(fr.target_field, fr.value)
                # Honor SET decision_status writes as decisions. BRDs often
                # phrase rejects/flags as "set decision_status = REJECTED"
                # rather than a REJECT action; without this those rules
                # would fire but leave the decision APPROVED. The terminal
                # decision vocabulary is APPROVED / FLAGGED / REJECTED —
                # APPROVED_WITH_CONDITIONS and similar map to APPROVED for
                # the top-level decision while the precise label stays on
                # the decision_status field (overlay + offer modifications).
                if _norm_field(fr.target_field) == "decision_status":
                    sv = str(fr.value).strip().upper()
                    if sv in ("REJECTED", "REJECT", "DECLINED", "DECLINE", "AUTO_REJECT"):
                        decision = "REJECTED"
                        terminal_rule_id = fr.rule_id
                        break
                    if sv in ("FLAGGED", "FLAG", "MANUAL_REVIEW", "REVIEW",
                              "FLAGGED_FOR_REVIEW", "SENIOR_CREDIT_OFFICER_REVIEW"):
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
