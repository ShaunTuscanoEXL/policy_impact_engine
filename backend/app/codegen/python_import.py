"""Python -> rule-dict parser.

Inverse of ``app.codegen.python_export``. Given a `.py` source string
that follows the codegen format, return a list of rule dicts ready to
hand to the merge engine or persist as a candidate rule_set.

Acceptance contract (loose, codegen-format-tolerant):
- module-level functions decorated with ``@rule(...)`` are rules
- decorator kwargs become the rule's metadata: id, subsystem,
  priority, source
- the function body is parsed for top-level ``if`` statements (or a
  bare ``return decision....()`` for unconditional rules)
- conditions are parsed from the ``if`` test expression: numeric
  comparisons against ``ctx.<field>`` are converted to
  Condition dicts; chained ``and``/``or`` produce multi-condition
  rules with the matching ``logic``
- actions come from ``return decision.REJECT(...)`` /
  ``decision.FLAG(...)`` / ``decision.CAP(...)`` / ``decision.MODIFY(...)``
- ``between`` is recognised from the pattern
  ``LO <= ctx.<field> <= HI`` (or ``LO < ctx.<field> < HI``)

Slice 3 caveats:
- We DO NOT execute the file (this is intentional — trust-source
  doesn't mean run-source). All extraction is via :mod:`ast`.
- Imports + the module docstring are ignored.
- Anything we can't classify cleanly is reported via :class:`ParseWarning`
  rather than raising. Callers can decide whether to abort or accept.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any


# ── Public types ─────────────────────────────────────────────────────────

@dataclass
class ParseWarning:
    rule_name: str | None
    message: str


@dataclass
class ParsedRule:
    rule_id: str
    rule_name: str
    description: str | None
    subsystem: str
    priority: int
    source_section: str | None
    conditions: list[dict]
    actions: list[dict]


@dataclass
class ParseResult:
    rules: list[ParsedRule] = field(default_factory=list)
    warnings: list[ParseWarning] = field(default_factory=list)

    def to_dicts(self) -> list[dict]:
        return [
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "description": r.description,
                "subsystem": r.subsystem,
                "priority": r.priority,
                "source_section": r.source_section,
                "conditions": r.conditions,
                "actions": r.actions,
            }
            for r in self.rules
        ]


# ── Operator AST → string mapping ────────────────────────────────────────

_AST_OP = {
    ast.Gt:    ">",
    ast.GtE:   ">=",
    ast.Lt:    "<",
    ast.LtE:   "<=",
    ast.Eq:    "==",
    ast.NotEq: "!=",
}


def _ctx_attr(node: ast.AST) -> str | None:
    """If ``node`` is ``ctx.<name>``, return ``<name>``; else None."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "ctx":
        return node.attr
    return None


def _literal_value(node: ast.AST) -> Any:
    """Best-effort literal extraction. Returns the python value or None
    if the expression isn't a literal we recognize."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


# ── Condition extraction ─────────────────────────────────────────────────

def _conditions_from_compare(cmp: ast.Compare) -> list[dict] | None:
    """Handle a single Compare node.

    Two shapes:
      1. ``ctx.<field> <op> <value>`` → one condition
      2. ``<lo> <= ctx.<field> <= <hi>`` (between)
      3. ``<value> <op> ctx.<field>`` (reversed; we flip the operator)
    """
    if len(cmp.ops) == 2 and len(cmp.comparators) == 2:
        # between: lo <op1> ctx.field <op2> hi
        lo_node, mid, hi_node = cmp.left, cmp.comparators[0], cmp.comparators[1]
        field = _ctx_attr(mid)
        if field is None:
            return None
        lo, hi = _literal_value(lo_node), _literal_value(hi_node)
        if lo is None or hi is None:
            return None
        return [{"field": field, "operator": "between", "value": [lo, hi], "logic": "AND"}]

    if len(cmp.ops) == 1 and len(cmp.comparators) == 1:
        op_t = type(cmp.ops[0])
        op_str = _AST_OP.get(op_t)
        if op_str is None:
            return None

        # Standard form: ctx.field OP value
        left_field = _ctx_attr(cmp.left)
        right_value = _literal_value(cmp.comparators[0])
        if left_field is not None and right_value is not None:
            return [{"field": left_field, "operator": op_str, "value": right_value, "logic": "AND"}]

        # Reversed: value OP ctx.field → flip operator direction
        right_field = _ctx_attr(cmp.comparators[0])
        left_value = _literal_value(cmp.left)
        if right_field is not None and left_value is not None:
            flipped = {">": "<", "<": ">", ">=": "<=", "<=": ">=",
                       "==": "==", "!=": "!="}.get(op_str, op_str)
            return [{"field": right_field, "operator": flipped, "value": left_value, "logic": "AND"}]

    return None


def _conditions_from_call(call: ast.Call) -> list[dict] | None:
    """Recognise ``ctx.field in (...)`` / ``ctx.field not in (...)``.

    Note: `in` lives on ast.Compare with ast.In/ast.NotIn ops, not Call;
    handled in :func:`_conditions_from_compare_in`.
    """
    return None


def _conditions_from_compare_in(cmp: ast.Compare) -> list[dict] | None:
    if len(cmp.ops) != 1 or len(cmp.comparators) != 1:
        return None
    op = cmp.ops[0]
    field = _ctx_attr(cmp.left)
    if field is None:
        return None
    val = _literal_value(cmp.comparators[0])
    if not isinstance(val, (list, tuple)):
        return None
    if isinstance(op, ast.In):
        return [{"field": field, "operator": "in", "value": list(val), "logic": "AND"}]
    if isinstance(op, ast.NotIn):
        return [{"field": field, "operator": "not_in", "value": list(val), "logic": "AND"}]
    return None


def _walk_test_expr(node: ast.AST, *, parent_logic: str = "AND") -> list[dict] | None:
    """Walk an `if` test expression into a flat list of condition dicts.

    Slice 3 supports left-folded chains:
        A and B          → [A(AND), B]
        A or B           → [A(OR), B]
        A and B and C    → [A, B, C] joined with AND
        A or B or C      → [A, B, C] joined with OR
        A and (B or C)   → flattened with parent_logic on the boundary

    Mixed-direction nesting (e.g. ``A or (B and C)``) is best-effort —
    we emit a warning by returning None for the parser to mark it.
    """
    if isinstance(node, ast.BoolOp):
        # AND or OR chain
        chain_logic = "AND" if isinstance(node.op, ast.And) else "OR"
        out: list[dict] = []
        for i, v in enumerate(node.values):
            sub = _walk_test_expr(v, parent_logic=chain_logic)
            if sub is None:
                return None
            # The logic on the LAST condition of `sub` will join it with
            # the NEXT chain element; set accordingly.
            if i < len(node.values) - 1 and sub:
                sub[-1] = {**sub[-1], "logic": chain_logic}
            out.extend(sub)
        return out

    if isinstance(node, ast.Compare):
        # Could be `in`/`not in`, `between`, or a single comparison
        if any(isinstance(o, (ast.In, ast.NotIn)) for o in node.ops):
            return _conditions_from_compare_in(node)
        return _conditions_from_compare(node)

    return None


# ── Action extraction ───────────────────────────────────────────────────

def _action_from_return(ret: ast.Return) -> dict | None:
    """Recognise the four canonical decision return shapes:
        decision.REJECT(reason="...")
        decision.FLAG(reason="...")
        decision.CAP(field="x", value=...)
        decision.MODIFY(field="x", delta=...)
    """
    if not isinstance(ret.value, ast.Call):
        return None
    func = ret.value.func
    if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
            and func.value.id == "decision"):
        return None

    method = func.attr.upper()
    kwargs: dict[str, Any] = {}
    for kw in ret.value.keywords:
        if kw.arg is None:
            continue
        kwargs[kw.arg] = _literal_value(kw.value)

    if method in ("REJECT", "DECLINE"):
        return {
            "action_type": "REJECT",
            "target_field": "decision_status",
            "value": "REJECTED",
            "description": str(kwargs.get("reason") or "REJECT"),
        }
    if method in ("FLAG", "REVIEW", "MANUAL_REVIEW"):
        return {
            "action_type": "FLAG",
            "target_field": "manual_review",
            "value": True,
            "description": str(kwargs.get("reason") or "FLAG"),
        }
    if method == "CAP":
        return {
            "action_type": "CAP",
            "target_field": str(kwargs.get("field") or ""),
            "value": kwargs.get("value"),
            "description": "CAP",
        }
    if method == "MODIFY":
        return {
            "action_type": "ADJUST",
            "target_field": str(kwargs.get("field") or ""),
            "value": kwargs.get("delta"),
            "description": "MODIFY",
        }
    if method == "APPROVE":
        return {
            "action_type": "APPROVE",
            "target_field": "decision_status",
            "value": "APPROVED",
            "description": "APPROVE",
        }
    return None


# ── Rule extraction (per FunctionDef) ───────────────────────────────────

def _decorator_metadata(decorator: ast.AST) -> dict[str, Any]:
    """Extract kwargs from ``@rule(id=..., subsystem=..., priority=...)``."""
    meta: dict[str, Any] = {}
    if not isinstance(decorator, ast.Call):
        return meta
    func = decorator.func
    if not (isinstance(func, ast.Name) and func.id == "rule"):
        return meta
    for kw in decorator.keywords:
        if kw.arg is None:
            continue
        meta[kw.arg] = _literal_value(kw.value)
    return meta


def _docstring_from_body(body: list[ast.stmt]) -> tuple[str | None, list[ast.stmt]]:
    """If the first stmt is a string Expr, treat as docstring and return
    (docstring, remaining_body)."""
    if not body:
        return None, body
    first = body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return first.value.value, body[1:]
    return None, body


def _parse_function_def(fn: ast.FunctionDef, warnings: list[ParseWarning]) -> ParsedRule | None:
    """Convert a single ``@rule`` decorated function into a ParsedRule
    dict, or None (with a warning) if it can't be classified."""
    rule_decorators = [d for d in fn.decorator_list if isinstance(d, ast.Call)
                       and isinstance(d.func, ast.Name) and d.func.id == "rule"]
    if not rule_decorators:
        return None

    meta = _decorator_metadata(rule_decorators[0])
    rule_id = str(meta.get("id") or fn.name)
    subsystem = str(meta.get("subsystem") or "UNCLASSIFIED")
    priority = int(meta.get("priority") or 0)
    source_section = meta.get("source")

    docstring, body = _docstring_from_body(fn.body)

    # The body should contain either:
    #   - one `if <test>: <action>` (with action being one of decision.X(...))
    #   - one bare `return decision.X(...)` (unconditional rule)
    conditions: list[dict] = []
    actions: list[dict] = []

    if not body:
        warnings.append(ParseWarning(fn.name, "rule body is empty"))
        return None

    if len(body) == 1 and isinstance(body[0], ast.Return):
        action = _action_from_return(body[0])
        if action is None:
            warnings.append(ParseWarning(fn.name, "unrecognized return action"))
            return None
        actions.append(action)
        return ParsedRule(
            rule_id=rule_id, rule_name=fn.name.replace("_", " ").title(),
            description=docstring, subsystem=subsystem, priority=priority,
            source_section=str(source_section) if source_section else None,
            conditions=[], actions=actions,
        )

    # Otherwise expect one top-level `if <cond>: <returns>`
    if len(body) == 1 and isinstance(body[0], ast.If):
        if_node = body[0]
        cond_dicts = _walk_test_expr(if_node.test)
        if cond_dicts is None:
            warnings.append(ParseWarning(fn.name, "could not parse condition expression"))
            return None
        conditions = cond_dicts
        for st in if_node.body:
            if isinstance(st, ast.Return):
                act = _action_from_return(st)
                if act is not None:
                    actions.append(act)
        if not actions:
            warnings.append(ParseWarning(fn.name, "no recognizable decision return inside if-body"))
            return None
        return ParsedRule(
            rule_id=rule_id, rule_name=fn.name.replace("_", " ").title(),
            description=docstring, subsystem=subsystem, priority=priority,
            source_section=str(source_section) if source_section else None,
            conditions=conditions, actions=actions,
        )

    warnings.append(ParseWarning(fn.name,
                                 "rule body has unsupported shape (expected one if-statement or one return)"))
    return None


# ── Entry point ─────────────────────────────────────────────────────────

def parse_python(source: str) -> ParseResult:
    """Parse a Python source string in the codegen format and return
    a ParseResult with rules + warnings.

    Raises :class:`SyntaxError` only if the source isn't valid Python at
    all. All other parse failures are returned as ParseWarnings so the
    caller can choose whether to surface them as 4xx or merge anyway.
    """
    tree = ast.parse(source)
    warnings: list[ParseWarning] = []
    rules: list[ParsedRule] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            parsed = _parse_function_def(node, warnings)
            if parsed:
                rules.append(parsed)
    return ParseResult(rules=rules, warnings=warnings)
