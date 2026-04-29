"""Render a LiveRuleVersion as a Python module string.

Output format (illustrative):

    # Generated: us_personal_loan_v17.py
    \"\"\"
    LIVE RULE REPOSITORY — US Personal Loan (Production)
    Version 17 — generated 2026-04-30 from BRD-PL-2026-001
    \"\"\"
    from policy_engine.runtime import RuleContext, decision

    # ─── BUREAU_GATE ───────────────────────────────────────
    @rule(id="R-BUR-001", subsystem="BUREAU_GATE", priority=100,
          origin_brd="BRD-PL-2026-001", version_added=14)
    def fico_minimum(ctx: RuleContext):
        if ctx.bureau_score < 720:
            return decision.REJECT(reason="SUBPRIME_FICO_SCORE")

The format is chosen so that:

- Every rule is a decorated function — testable, debuggable, lintable.
- Subsystems group adjacent rules so a human can read the file top-down.
- Conditions and actions are compiled into idiomatic Python instead of
  generic dict lookups.

Slice 0 caveats:
- Multi-condition logic uses chained `and`/`or` — no short-circuit
  optimization beyond Python's own.
- Unrecognized operators / actions fall through to a `_raw(...)` helper
  and a TODO comment for the human to tidy.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from app.models.live_repo import LiveRuleRepository, LiveRuleVersion


# ── Operator mapping → Python source ─────────────────────────────────────
_OP_PY = {
    ">":  ">",
    ">=": ">=",
    "gt": ">",
    "gte": ">=",
    "<":  "<",
    "<=": "<=",
    "lt": "<",
    "lte": "<=",
    "==": "==",
    "=":  "==",
    "eq": "==",
    "!=": "!=",
    "ne": "!=",
}


def _safe_identifier(name: str) -> str:
    """Best-effort conversion of a rule name to a Python function name."""
    out = []
    for ch in (name or "").lower().strip():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_", "/", "."):
            out.append("_")
    s = "".join(out).strip("_")
    if not s:
        return "rule"
    if s[0].isdigit():
        s = "rule_" + s
    return s


def _render_value(v: Any) -> str:
    if v is None:
        return "None"
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_render_value(x) for x in v) + "]"
    return repr(v)


def _render_condition(cond: dict) -> str:
    """Render a single Condition into a Python boolean expression."""
    if not isinstance(cond, dict):
        return "_raw(...)  # TODO: malformed condition"

    field = (cond.get("field") or "unknown_field").strip()
    op = cond.get("operator") or "=="
    val = cond.get("value")

    op_lower = str(op).lower()

    if op_lower in ("between", "range"):
        if isinstance(val, (list, tuple)) and len(val) == 2:
            lo, hi = val[0], val[1]
            return f"({_render_value(lo)} <= ctx.{field} <= {_render_value(hi)})"
        return f"_raw('between', ctx.{field}, {_render_value(val)})  # TODO: bad range"

    if op_lower in ("in",):
        return f"ctx.{field} in {_render_value(val)}"
    if op_lower in ("not_in", "not in"):
        return f"ctx.{field} not in {_render_value(val)}"

    py_op = _OP_PY.get(op_lower) or _OP_PY.get(str(op))
    if py_op is None:
        return f"_raw({_render_value(op)}, ctx.{field}, {_render_value(val)})  # TODO: unknown op"

    return f"ctx.{field} {py_op} {_render_value(val)}"


def _render_conditions(conditions: list[dict]) -> str:
    """Combine conditions using their `logic` field (AND/OR).

    Slice 0: simple left-fold with the operator from the previous
    condition. Mixed AND/OR chains are wrapped with parens conservatively.
    """
    if not conditions:
        return "True"

    parts: list[str] = []
    for i, c in enumerate(conditions):
        expr = _render_condition(c)
        if i == 0:
            parts.append(expr)
            continue
        prev_logic = (conditions[i - 1].get("logic") if isinstance(conditions[i - 1], dict) else "AND") or "AND"
        joiner = "or" if str(prev_logic).upper() == "OR" else "and"
        parts.append(f"{joiner} {expr}")
    return " ".join(parts)


def _render_action(action: dict) -> str:
    """Render an Action as a Python return statement."""
    if not isinstance(action, dict):
        return "return _raw(...)  # TODO: malformed action"

    act_type = (action.get("action_type") or "FLAG").strip().upper()
    target = (action.get("target_field") or "").strip()
    value = action.get("value")
    desc = (action.get("description") or "").strip()

    if act_type in ("REJECT", "DECLINE", "AUTO_REJECT"):
        reason = desc or value or "POLICY_REJECT"
        return f"return decision.REJECT(reason={_render_value(str(reason))})"
    if act_type in ("FLAG", "MANUAL_REVIEW", "REVIEW"):
        reason = desc or value or "MANUAL_REVIEW"
        return f"return decision.FLAG(reason={_render_value(str(reason))})"
    if act_type in ("CAP", "SET") and target:
        return f"return decision.CAP(field={_render_value(target)}, value={_render_value(value)})"
    if act_type in ("ADJUST", "MODIFY", "PRICE") and target:
        return f"return decision.MODIFY(field={_render_value(target)}, delta={_render_value(value)})"
    if act_type in ("APPROVE",):
        return "return decision.APPROVE()"

    return (
        f"return decision.RAW(action_type={_render_value(act_type)}, "
        f"target={_render_value(target)}, value={_render_value(value)})  "
        f"# TODO: unrecognized action"
    )


def _render_actions(actions: list[dict]) -> list[str]:
    if not actions:
        return ["return None"]
    return [_render_action(a) for a in actions]


def _render_rule_body(rule_data: dict) -> list[str]:
    """Return a list of indented (4-space) source lines for the function body."""
    conds = rule_data.get("conditions") or []
    acts = rule_data.get("actions") or []

    cond_expr = _render_conditions(conds)

    lines: list[str] = []
    description = (rule_data.get("description") or rule_data.get("rule_name") or "").strip()
    if description:
        lines.append(f'"""{description}"""')

    if cond_expr == "True":
        # Unconditional rule → just emit the action(s) at top level
        for a in _render_actions(acts):
            lines.append(a)
        return lines

    lines.append(f"if {cond_expr}:")
    for a in _render_actions(acts):
        lines.append("    " + a)
    return lines


def _render_decorator(rule_data: dict) -> str:
    rid = rule_data.get("rule_id") or rule_data.get("id") or "?"
    sub = rule_data.get("subsystem") or "UNCLASSIFIED"
    pri = rule_data.get("priority", 0)
    src = rule_data.get("source_section") or rule_data.get("origin_brd_id") or ""
    parts = [
        f"id={_render_value(rid)}",
        f"subsystem={_render_value(str(sub))}",
        f"priority={pri}",
    ]
    if src:
        parts.append(f"source={_render_value(str(src))}")
    return "@rule(" + ", ".join(parts) + ")"


def _group_by_subsystem(rules: Iterable[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for r in rules:
        key = str(r.get("subsystem") or "UNCLASSIFIED")
        groups.setdefault(key, []).append(r)
    # Sort each group by priority (desc) then by rule_id for stability
    for k in groups:
        groups[k].sort(key=lambda r: (-int(r.get("priority", 0)), str(r.get("rule_id", ""))))
    return groups


# Subsystem render order (gates first, then pricing, then exposure, then scoring)
_SUBSYSTEM_ORDER = [
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


def render_python(
    repo: LiveRuleRepository,
    version: LiveRuleVersion,
    *,
    generated_at: datetime | None = None,
) -> str:
    """Return the rendered Python source for one repository version."""
    rules = list(version.rule_snapshot or [])
    groups = _group_by_subsystem(rules)
    ts = (generated_at or datetime.utcnow()).strftime("%Y-%m-%dT%H:%M:%SZ")

    out: list[str] = []
    out.append(f'"""LIVE RULE REPOSITORY — {repo.name}')
    out.append(f"Product: {repo.product}    Jurisdiction: {repo.jurisdiction}")
    out.append(f"Version: {version.version_number}")
    out.append(f"Generated: {ts}")
    if version.summary:
        out.append("")
        out.append(f"Summary: {version.summary}")
    out.append('"""')
    out.append("from policy_engine.runtime import RuleContext, decision, rule, _raw")
    out.append("")
    out.append("")

    # Render groups in canonical order; any unknown groups appended at the end
    seen: set[str] = set()
    for sub in _SUBSYSTEM_ORDER:
        if sub not in groups:
            continue
        seen.add(sub)
        out.extend(_render_group(sub, groups[sub]))

    for sub, group in groups.items():
        if sub in seen:
            continue
        out.extend(_render_group(sub, group))

    if not rules:
        out.append("# (no rules in this version)")
        out.append("")

    return "\n".join(out)


def _render_group(subsystem: str, rules: list[dict]) -> list[str]:
    lines: list[str] = []
    bar = "─" * 56
    lines.append(f"# {bar}")
    lines.append(f"# {subsystem}")
    lines.append(f"# {bar}")
    lines.append("")

    for r in rules:
        lines.append(_render_decorator(r))
        fname = _safe_identifier(r.get("rule_name") or r.get("rule_id") or "rule")
        lines.append(f"def {fname}(ctx: RuleContext):")
        for body_line in _render_rule_body(r):
            lines.append("    " + body_line)
        lines.append("")
    return lines
