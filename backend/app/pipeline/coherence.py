"""BRD coherence validator — graph-level analysis of a rule set.

The per-rule validator (rule_validator.py) checks each rule in isolation
plus pairwise conflicts. This module looks at the rule set AS A WHOLE —
the way a BRD is actually written, where context flows top-to-bottom and
later rules depend on classifications/eligibility established earlier.

It builds the produce/consume dependency graph and reports:

  - dead_consumer        a rule reads a field that is neither a known raw
                         loan field nor produced by any rule → it can
                         never match (typo, or a missing upstream rule)
  - orphan_producer      a rule SETs a derived/classification field that
                         no rule ever consumes → the classification does
                         nothing (e.g. "Good Customer" defined but never
                         gated on — the exact gap the user flagged)
  - dependency_cycle     rule A produces a field B consumes and vice
                         versa → no valid evaluation order
  - unreferenced_eligibility
                         a producer whose field name looks like an
                         eligibility/classification flag and which nothing
                         downstream references (subset of orphan_producer,
                         escalated because eligibility gates are the most
                         likely to be the "context" a BRD intends)

This is deterministic — no LLM. It's the "mechanism that validates the
BRD was actually converted correctly" the way a reviewer would: does the
graph of rules actually connect the way the document describes?
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.rule import RuleDefinition
from app.services.field_registry import resolve_field_path


# Output-target fields that are decisions/offer terms, not classification
# flags. Producing one of these without a consumer is normal (it's the
# final output), so they're excluded from orphan-producer reporting.
_TERMINAL_TARGETS = {
    "decision_status", "decision", "status", "outcome", "verdict",
    "interest_rate", "apr", "rate", "interest_rate_adjustment",
    "eligible_amount", "loan_amount", "approved_amount", "max_eligible_amount",
    "max_tenure_months", "tenure", "term_months", "recommended_tenure_months",
    "origination_fee_pct", "origination_fee", "coupon",
    "for_manual_review", "manual_review", "credit_risk_band",
}

# Name fragments that mark a produced field as an eligibility/classification
# flag — the kind of thing a BRD defines once and expects downstream rules
# to gate on.
_ELIGIBILITY_HINTS = (
    "eligib", "classification", "segment", "good_customer", "flag",
    "tier", "qualif", "approved_for", "is_", "_status",
)


@dataclass
class CoherenceIssue:
    kind: str                 # dead_consumer | orphan_producer | dependency_cycle | unreferenced_eligibility
    severity: str             # error | warning | info
    rule_ids: list[str]
    field: str | None
    message: str


@dataclass
class CoherenceReport:
    is_coherent: bool
    issues: list[CoherenceIssue] = field(default_factory=list)
    produced_fields: list[str] = field(default_factory=list)
    consumed_fields: list[str] = field(default_factory=list)
    # (producer_rule_id, consumer_rule_id, field) edges — lets the UI draw
    # the dependency graph and show what connects to what.
    dependency_edges: list[tuple[str, str, str]] = field(default_factory=list)


def _norm(name) -> str:
    s = str(name or "").strip().lower()
    return s.replace(" ", "_").replace("-", "_").replace(".", "_")


def _is_known_raw_field(field_name: str) -> bool:
    """True if the field resolves to a real loan-payload path via the
    field registry — i.e. it's a raw input the loan actually carries."""
    return resolve_field_path(field_name) is not None


def _looks_like_eligibility(field_name: str) -> bool:
    f = _norm(field_name)
    return any(h in f for h in _ELIGIBILITY_HINTS)


def _produced(rule: RuleDefinition) -> set[str]:
    out: set[str] = set()
    for a in rule.actions or []:
        if str(getattr(a, "action_type", "")).strip().upper() == "SET":
            tf = _norm(getattr(a, "target_field", None))
            if tf:
                out.add(tf)
    return out


def _consumed(rule: RuleDefinition) -> set[str]:
    return {_norm(c.field) for c in (rule.conditions or []) if getattr(c, "field", None)}


def analyze_coherence(rules: list[RuleDefinition]) -> CoherenceReport:
    """Build the dependency graph and surface coherence issues."""
    if not rules:
        return CoherenceReport(is_coherent=True)

    # Producer map: field -> [rule_ids that SET it]
    producers: dict[str, list[str]] = {}
    consumers: dict[str, list[str]] = {}
    produced_per: dict[str, set[str]] = {}
    consumed_per: dict[str, set[str]] = {}

    for r in rules:
        p = _produced(r)
        c = _consumed(r)
        produced_per[r.rule_id] = p
        consumed_per[r.rule_id] = c
        for f in p:
            producers.setdefault(f, []).append(r.rule_id)
        for f in c:
            consumers.setdefault(f, []).append(r.rule_id)

    all_produced = set(producers)
    all_consumed = set(consumers)
    issues: list[CoherenceIssue] = []

    # ── Dead consumers ──────────────────────────────────────────────
    # A consumed field that nothing produces AND isn't a known raw loan
    # field → the rule can never fire. Warning (not error) because the
    # registry may not know every legitimate raw field.
    for fld in sorted(all_consumed):
        if fld in all_produced:
            continue
        if _is_known_raw_field(fld):
            continue
        rids = consumers[fld]
        issues.append(CoherenceIssue(
            kind="dead_consumer",
            severity="warning",
            rule_ids=rids,
            field=fld,
            message=(
                f"Rule(s) {', '.join(rids)} condition on '{fld}', but no rule "
                f"produces it and it is not a known loan field. These rules may "
                f"never fire — check for a typo or a missing upstream rule."
            ),
        ))

    # ── Orphan / unreferenced-eligibility producers ─────────────────
    # A SET on a non-terminal field that nothing consumes does nothing
    # downstream. If the field looks like an eligibility/classification
    # flag, escalate the message — that's almost certainly the BRD's
    # intended "context" that got dropped.
    for fld in sorted(all_produced):
        if fld in all_consumed:
            continue
        if fld in _TERMINAL_TARGETS:
            continue  # producing a final output without a consumer is normal
        rids = producers[fld]
        if _looks_like_eligibility(fld):
            issues.append(CoherenceIssue(
                kind="unreferenced_eligibility",
                severity="warning",
                rule_ids=rids,
                field=fld,
                message=(
                    f"Rule(s) {', '.join(rids)} set the eligibility/classification "
                    f"field '{fld}', but no downstream rule conditions on it. The "
                    f"BRD likely intends later rules to apply only to this group — "
                    f"the gating may have been dropped. Confirm whether downstream "
                    f"rules should require '{fld}'."
                ),
            ))
        else:
            issues.append(CoherenceIssue(
                kind="orphan_producer",
                severity="info",
                rule_ids=rids,
                field=fld,
                message=(
                    f"Rule(s) {', '.join(rids)} set '{fld}', but no rule reads it. "
                    f"This write has no downstream effect."
                ),
            ))

    # ── Dependency edges + cycle detection ──────────────────────────
    edges: list[tuple[str, str, str]] = []
    # adjacency by rule_id for cycle check
    adj: dict[str, set[str]] = {r.rule_id: set() for r in rules}
    for fld, prod_ids in producers.items():
        for cons_id in consumers.get(fld, []):
            for prod_id in prod_ids:
                if prod_id == cons_id:
                    continue
                edges.append((prod_id, cons_id, fld))
                adj[prod_id].add(cons_id)

    cycle = _find_cycle(adj)
    if cycle:
        issues.append(CoherenceIssue(
            kind="dependency_cycle",
            severity="error",
            rule_ids=cycle,
            field=None,
            message=(
                f"Circular dependency between rules {' → '.join(cycle + [cycle[0]])}: "
                f"each produces a field the next consumes. There is no valid "
                f"evaluation order — one of these rules will not see the other's "
                f"output."
            ),
        ))

    is_coherent = not any(i.severity == "error" for i in issues)
    return CoherenceReport(
        is_coherent=is_coherent,
        issues=issues,
        produced_fields=sorted(all_produced),
        consumed_fields=sorted(all_consumed),
        dependency_edges=edges,
    )


def _find_cycle(adj: dict[str, set[str]]) -> list[str] | None:
    """Return one cycle as a list of rule_ids, or None. DFS with a
    recursion stack."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = {node: WHITE for node in adj}
    parent: dict[str, str | None] = {node: None for node in adj}

    def visit(node: str) -> list[str] | None:
        color[node] = GREY
        for nxt in adj.get(node, ()):  # deterministic enough for reporting
            if color.get(nxt, BLACK) == GREY:
                # Found a back-edge → reconstruct the cycle.
                cycle = [nxt]
                cur = node
                while cur is not None and cur != nxt:
                    cycle.append(cur)
                    cur = parent[cur]
                cycle.reverse()
                return cycle
            if color.get(nxt, BLACK) == WHITE:
                parent[nxt] = node
                found = visit(nxt)
                if found:
                    return found
        color[node] = BLACK
        return None

    for node in adj:
        if color[node] == WHITE:
            found = visit(node)
            if found:
                return found
    return None
