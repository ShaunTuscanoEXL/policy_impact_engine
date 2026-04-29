"""Slice 3 — Python AST round-trip tests.

Covers:
  - parse_python on simple/complex codegen output
  - between, in/not_in, AND/OR chains, FLAG/REJECT/CAP/MODIFY actions
  - warnings for malformed rules
  - end-to-end round trip:
      seed BRD -> baseline -> export.py -> parse -> import as new version
      -> snapshot of new version matches the parsed rules
"""
from __future__ import annotations

import pytest

from app.codegen import parse_python, render_python
from app.models.brd import BrdDocument, FileType
from app.models.rule import Rule, RuleSet, RuleSetStatus, RuleType, Subsystem


pytestmark = pytest.mark.anyio


# ── Pure parser tests (no DB) ────────────────────────────────────────────

def test_parse_simple_reject_rule():
    src = '''
"""Header"""
from policy_engine.runtime import RuleContext, decision, rule, _raw

@rule(id="R-DTI-001", subsystem="DTI_GATE", priority=90)
def dti_cap(ctx: RuleContext):
    """Reject when DTI exceeds CFPB QM 43%"""
    if ctx.dti_ratio > 0.43:
        return decision.REJECT(reason="HIGH_DTI_RATIO")
'''
    result = parse_python(src)
    assert result.warnings == []
    assert len(result.rules) == 1
    rule = result.rules[0]
    assert rule.rule_id == "R-DTI-001"
    assert rule.subsystem == "DTI_GATE"
    assert rule.priority == 90
    assert rule.description == "Reject when DTI exceeds CFPB QM 43%"
    assert rule.conditions == [
        {"field": "dti_ratio", "operator": ">", "value": 0.43, "logic": "AND"}
    ]
    assert rule.actions == [
        {"action_type": "REJECT", "target_field": "decision_status",
         "value": "REJECTED", "description": "HIGH_DTI_RATIO"}
    ]


def test_parse_between_operator():
    src = '''
from policy_engine.runtime import RuleContext, decision, rule

@rule(id="R-PRC", subsystem="PRICING_TIER", priority=50)
def pricing_tier(ctx: RuleContext):
    if (720 <= ctx.bureau_score <= 769):
        return decision.CAP(field="interest_rate", value=0.1199)
'''
    result = parse_python(src)
    assert result.warnings == []
    rule = result.rules[0]
    assert rule.conditions == [
        {"field": "bureau_score", "operator": "between", "value": [720, 769], "logic": "AND"}
    ]
    assert rule.actions == [
        {"action_type": "CAP", "target_field": "interest_rate",
         "value": 0.1199, "description": "CAP"}
    ]


def test_parse_or_chain():
    src = '''
from policy_engine.runtime import RuleContext, decision, rule

@rule(id="R-INQ", subsystem="BUREAU_GATE", priority=80)
def inquiry_cap(ctx: RuleContext):
    """Too many recent inquiries"""
    if ctx.inquiries_last_3m > 3 or ctx.inquiries_last_12m > 10:
        return decision.REJECT(reason="TOO_MANY_INQUIRIES")
'''
    result = parse_python(src)
    assert result.warnings == []
    conds = result.rules[0].conditions
    assert len(conds) == 2
    assert conds[0]["field"] == "inquiries_last_3m"
    assert conds[0]["operator"] == ">"
    assert conds[0]["value"] == 3
    # Convention: logic on cond[i] tells us how to join cond[i] with cond[i+1].
    # Cond 0's "OR" carries the OR semantics; cond 1's logic is irrelevant
    # (no next condition) so it stays at the default "AND".
    assert conds[0]["logic"] == "OR"
    assert conds[1]["field"] == "inquiries_last_12m"


def test_parse_in_operator():
    src = '''
from policy_engine.runtime import RuleContext, decision, rule

@rule(id="R", subsystem="EMPLOYMENT_GATE", priority=10)
def employment_check(ctx: RuleContext):
    if ctx.employment_type in ["W2_FULL_TIME", "W2_PART_TIME"]:
        return decision.APPROVE()
'''
    result = parse_python(src)
    assert result.warnings == []
    cond = result.rules[0].conditions[0]
    assert cond["operator"] == "in"
    assert cond["value"] == ["W2_FULL_TIME", "W2_PART_TIME"]


def test_parse_flag_and_modify_actions():
    src = '''
from policy_engine.runtime import RuleContext, decision, rule

@rule(id="R-FLAG", subsystem="BANKING_BEHAVIOR", priority=20)
def warn(ctx: RuleContext):
    if ctx.banking_stability_index < 0.5:
        return decision.FLAG(reason="UNSTABLE_BANKING")

@rule(id="R-MOD", subsystem="RATE_MODIFIER", priority=10)
def premium(ctx: RuleContext):
    if ctx.bureau_score >= 750:
        return decision.MODIFY(field="interest_rate", delta=-0.005)
'''
    result = parse_python(src)
    assert result.warnings == []
    by_id = {r.rule_id: r for r in result.rules}
    flag_rule = by_id["R-FLAG"]
    assert flag_rule.actions[0]["action_type"] == "FLAG"
    assert flag_rule.actions[0]["description"] == "UNSTABLE_BANKING"
    mod_rule = by_id["R-MOD"]
    assert mod_rule.actions[0]["action_type"] == "ADJUST"
    assert mod_rule.actions[0]["target_field"] == "interest_rate"
    assert mod_rule.actions[0]["value"] == -0.005


def test_parse_warns_on_unrecognized_shape():
    src = '''
from policy_engine.runtime import RuleContext, decision, rule

@rule(id="R-BAD", subsystem="UNCLASSIFIED", priority=1)
def malformed(ctx: RuleContext):
    """Two top-level if-stmts is unsupported in slice 3."""
    if ctx.bureau_score < 600:
        return decision.REJECT(reason="X")
    if ctx.bureau_score < 500:
        return decision.REJECT(reason="Y")
'''
    result = parse_python(src)
    assert len(result.rules) == 0
    assert any("unsupported shape" in w.message for w in result.warnings)


def test_parse_ignores_undecorated_functions():
    src = '''
from policy_engine.runtime import RuleContext, decision, rule

def helper():
    return 42

@rule(id="R", subsystem="DTI_GATE", priority=1)
def real_rule(ctx: RuleContext):
    if ctx.dti_ratio > 0.5:
        return decision.REJECT(reason="DTI")
'''
    result = parse_python(src)
    assert len(result.rules) == 1
    assert result.rules[0].rule_id == "R"


# ── Round-trip via codegen ───────────────────────────────────────────────

def test_render_then_parse_produces_equivalent_rules():
    """Render a snapshot, parse it back, and confirm the conditions and
    actions survive."""
    snapshot = [
        {"id": "R-BUR-001", "rule_id": "R-BUR-001", "rule_name": "FICO floor",
         "description": "Minimum FICO 720", "subsystem": "BUREAU_GATE", "priority": 100,
         "conditions": [{"field": "bureau_score", "operator": "<", "value": 720}],
         "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                      "value": "REJECTED", "description": "SUBPRIME_FICO_SCORE"}]},
        {"id": "R-DTI-001", "rule_id": "R-DTI-001", "rule_name": "DTI cap",
         "description": "CFPB QM cap", "subsystem": "DTI_GATE", "priority": 90,
         "conditions": [{"field": "dti_ratio", "operator": ">", "value": 0.43}],
         "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                      "value": "REJECTED", "description": "HIGH_DTI_RATIO"}]},
        {"id": "R-PRC-001", "rule_id": "R-PRC-001", "rule_name": "Pricing tier",
         "description": "Tier 2 pricing", "subsystem": "PRICING_TIER", "priority": 50,
         "conditions": [{"field": "bureau_score", "operator": "between", "value": [720, 769]}],
         "actions": [{"action_type": "SET", "target_field": "interest_rate",
                      "value": 0.1199, "description": "TIER_2_RATE"}]},
    ]

    class _MockRepo:
        name = "Test"
        product = "PERSONAL"
        jurisdiction = "US"

    class _MockVersion:
        version_number = 1
        summary = "Test"
        rule_snapshot = snapshot

    py = render_python(_MockRepo(), _MockVersion())
    result = parse_python(py)

    # Codegen renders REJECT -> decision.REJECT(...) which the parser
    # turns back into the canonical {action_type:"REJECT", target_field:
    # "decision_status", value:"REJECTED"} dict. So we expect 3 rules
    # with matching conditions and equivalent actions.
    assert len(result.rules) == 3
    by_id = {r.rule_id: r for r in result.rules}
    assert by_id["R-BUR-001"].conditions[0]["field"] == "bureau_score"
    assert by_id["R-BUR-001"].conditions[0]["operator"] == "<"
    assert by_id["R-BUR-001"].conditions[0]["value"] == 720
    assert by_id["R-BUR-001"].actions[0]["action_type"] == "REJECT"
    assert by_id["R-DTI-001"].conditions[0]["operator"] == ">"
    assert by_id["R-DTI-001"].conditions[0]["value"] == 0.43
    # Codegen renders SET on interest_rate as decision.CAP(...) which the
    # parser maps back to action_type "CAP" — the round trip preserves
    # the SEMANTICS (constrain a value) even though the literal action_type
    # token differs from the original SET token. This is fine for slice 3.
    assert by_id["R-PRC-001"].conditions[0]["operator"] == "between"
    assert by_id["R-PRC-001"].conditions[0]["value"] == [720, 769]
    assert by_id["R-PRC-001"].actions[0]["action_type"] == "CAP"
    assert by_id["R-PRC-001"].actions[0]["target_field"] == "interest_rate"
    assert by_id["R-PRC-001"].actions[0]["value"] == 0.1199


# ── End-to-end: export -> import via API ─────────────────────────────────

async def _seed_brd_and_baseline(client, db_session, *, rules: list[dict]):
    brd = BrdDocument(filename="BRD.docx", file_path="/data/BRD.docx",
                      file_type=FileType.DOCX, parsed_content="…")
    db_session.add(brd)
    await db_session.commit()
    await db_session.refresh(brd)
    rs = RuleSet(brd_document_id=brd.id, version=1, name="Initial",
                 status=RuleSetStatus.DRAFT)
    db_session.add(rs)
    await db_session.flush()
    for r in rules:
        db_session.add(Rule(
            rule_set_id=rs.id,
            rule_id=r["rule_id"], rule_name=r["rule_name"],
            description=r.get("description"),
            rule_type=RuleType(r.get("rule_type", "ELIGIBILITY")),
            subsystem=Subsystem(r.get("subsystem", "UNCLASSIFIED")),
            conditions=r["conditions"], actions=r["actions"],
            priority=r.get("priority", 0),
        ))
    await db_session.commit()
    return (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "decided_by": "vishnu",
    })).json()


async def test_full_round_trip_export_then_import(client, db_session):
    """Baseline a repo from a BRD, export.py -> import as v2, then
    confirm v2's snapshot mirrors v1's rules (one rule per @rule
    function in the imported source)."""
    base = await _seed_brd_and_baseline(client, db_session, rules=[
        {
            "rule_id": "R-BUR-001", "rule_name": "FICO floor",
            "description": "Minimum FICO 720", "subsystem": "BUREAU_GATE", "priority": 100,
            "conditions": [{"field": "bureau_score", "operator": "<", "value": 720, "logic": "AND"}],
            "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                         "value": "REJECTED", "description": "SUBPRIME_FICO_SCORE"}],
        },
        {
            "rule_id": "R-DTI-001", "rule_name": "DTI cap",
            "description": "CFPB QM cap", "subsystem": "DTI_GATE", "priority": 90,
            "conditions": [{"field": "dti_ratio", "operator": ">", "value": 0.43, "logic": "AND"}],
            "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                         "value": "REJECTED", "description": "HIGH_DTI_RATIO"}],
        },
    ])
    repo_id = base["repository_id"]
    assert base["auto_applied"] is True
    assert base["new_version_number"] == 1

    # Export the head as Python
    py = (await client.get(f"/api/v1/live-repo/{repo_id}/export.py")).text
    assert "def fico_floor" in py
    assert "def dti_cap" in py

    # Import the same source — should land as v2
    r = await client.post(f"/api/v1/live-repo/{repo_id}/import", json={
        "source": py,
        "decided_by": "vishnu",
        "summary": "Round-trip from v1 export",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["rules_imported"] == 2
    assert body["new_version_number"] == 2
    assert body["warnings"] == []

    # v2 snapshot has the same canonical_keys
    v2 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/2")).json()
    assert v2["rule_count"] == 2
    keys = {r["canonical_key"] for r in v2["rule_snapshot"]}
    assert "BUREAU_GATE::bureau_score::LT::REJECT" in keys
    assert "DTI_GATE::dti_ratio::GT::REJECT" in keys

    # Repo HEAD advanced to 2
    detail = (await client.get(f"/api/v1/live-repo/{repo_id}")).json()
    assert detail["current_version"] == 2


async def test_import_rejects_invalid_python(client, db_session):
    repo_id = (await client.post("/api/v1/live-repo", json={
        "name": "X", "product": "PERSONAL", "jurisdiction": "US",
    })).json()["id"]
    bad = "this is not valid python @@@@"
    r = await client.post(f"/api/v1/live-repo/{repo_id}/import", json={
        "source": bad, "decided_by": "vishnu",
    })
    assert r.status_code == 400
    assert "syntax" in r.json()["detail"].lower()


async def test_import_rejects_source_with_no_rules(client, db_session):
    repo_id = (await client.post("/api/v1/live-repo", json={
        "name": "X", "product": "PERSONAL", "jurisdiction": "US",
    })).json()["id"]
    src_no_rules = '''
"""Empty module."""
from policy_engine.runtime import RuleContext

def helper():
    return 1
'''
    r = await client.post(f"/api/v1/live-repo/{repo_id}/import", json={
        "source": src_no_rules, "decided_by": "vishnu",
    })
    assert r.status_code == 400
    assert "no @rule" in r.json()["detail"].lower()
