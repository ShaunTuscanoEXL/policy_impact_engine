"""Slice 1 integration tests.

Covers:
  - Admin backfill for legacy rules without canonical_key/subsystem
  - Default-repository auto-creation
  - propose-from-brd with auto-baseline (empty repo gets v1 directly)
  - Subsequent BRD producing a real proposal (not auto-applied)
  - Retirement signals extraction + merge_engine integration
"""
from __future__ import annotations

import pytest

from app.models.brd import BrdDocument, FileType
from app.models.rule import Rule, RuleSet, RuleSetStatus, RuleType, Subsystem
from app.services import live_repo_service as svc
from app.services.merge_engine import diff_rule_sets
from app.services.retirement_signals import (
    extract_retirement_signals,
    signal_from_retires_pattern,
)


pytestmark = pytest.mark.anyio


# ── Helpers ──────────────────────────────────────────────────────────────

async def _seed_brd(db_session, *, name="BRD.docx") -> BrdDocument:
    brd = BrdDocument(
        filename=name, file_path=f"/data/{name}", file_type=FileType.DOCX,
        parsed_content="…",
    )
    db_session.add(brd)
    await db_session.commit()
    await db_session.refresh(brd)
    return brd


async def _seed_rule_set(db_session, brd, rules: list[dict]) -> RuleSet:
    rs = RuleSet(
        brd_document_id=brd.id, version=1,
        name=f"Rules from {brd.filename}",
        status=RuleSetStatus.DRAFT,
    )
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
    await db_session.refresh(rs)
    return rs


def _rule(rid, name, field, op, val, *, action="REJECT", target="decision_status",
          subsystem="UNCLASSIFIED", priority=0):
    return {
        "rule_id": rid, "rule_name": name, "subsystem": subsystem,
        "priority": priority,
        "conditions": [{"field": field, "operator": op, "value": val, "logic": "AND"}],
        "actions": [{"action_type": action, "target_field": target,
                     "value": "REJECTED", "description": rid}],
    }


# ── Backfill ─────────────────────────────────────────────────────────────

async def test_backfill_classifies_legacy_rules(client, db_session):
    """Rules created before slice 0 don't have canonical_key/subsystem.
    The admin endpoint backfills them."""
    brd = await _seed_brd(db_session)
    # Seed a rule WITHOUT subsystem/canonical_key (legacy state)
    rs = RuleSet(brd_document_id=brd.id, version=1, name="Legacy", status=RuleSetStatus.DRAFT)
    db_session.add(rs)
    await db_session.flush()
    legacy = Rule(
        rule_set_id=rs.id,
        rule_id="LEG-001", rule_name="Legacy DTI cap",
        rule_type=RuleType.ELIGIBILITY,
        subsystem=Subsystem.UNCLASSIFIED,
        conditions=[{"field": "dti_ratio", "operator": ">", "value": 0.40}],
        actions=[{"action_type": "REJECT", "target_field": "decision_status",
                  "value": "REJECTED", "description": "DTI"}],
        canonical_key=None, semantic_signature=None, priority=10,
    )
    db_session.add(legacy)
    await db_session.commit()

    # Hit admin endpoint
    r = await client.post("/api/v1/live-repo/admin/backfill")
    assert r.status_code == 200
    body = r.json()
    assert body["rules_classified"] == 1

    # Refetch to confirm canonical_key + subsystem populated
    await db_session.refresh(legacy)
    assert legacy.canonical_key == "DTI_GATE::dti_ratio::GT::REJECT::DECISION"
    assert legacy.subsystem == Subsystem.DTI_GATE
    assert legacy.semantic_signature is not None

    # Calling again is a no-op
    r2 = await client.post("/api/v1/live-repo/admin/backfill")
    assert r2.json()["rules_classified"] == 0


# ── propose-from-brd auto-baseline ───────────────────────────────────────

async def test_propose_from_brd_auto_baselines_empty_repo(client, db_session):
    """First BRD against an empty repo → auto-applied as v1."""
    brd = await _seed_brd(db_session, name="BRD-PL-2026-001.docx")
    await _seed_rule_set(db_session, brd, [
        _rule("R-BUR-001", "FICO floor", "bureau_score", "<", 720,
              subsystem="BUREAU_GATE", priority=100),
        _rule("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.43,
              subsystem="DTI_GATE", priority=90),
    ])

    r = await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id),
        "product": "PERSONAL", "jurisdiction": "US",
        "auto_apply_when_empty": True,
        "decided_by": "vishnu",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["auto_applied"] is True
    assert body["new_version_number"] == 1
    repo_id = body["repository_id"]

    # Repo is now at version 1 with both rules in the snapshot
    detail = (await client.get(f"/api/v1/live-repo/{repo_id}")).json()
    assert detail["current_version"] == 1
    assert detail["product"] == "PERSONAL"
    assert detail["jurisdiction"] == "US"

    v1 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/1")).json()
    assert v1["rule_count"] == 2


async def test_propose_from_brd_does_not_auto_apply_when_repo_has_rules(client, db_session):
    """Once a repo has rules, propose-from-brd creates a PENDING proposal
    rather than auto-applying."""
    # First BRD baselines the repo
    brd1 = await _seed_brd(db_session)
    await _seed_rule_set(db_session, brd1, [
        _rule("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.45,
              subsystem="DTI_GATE", priority=90),
    ])
    first = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd1.id),
        "product": "PERSONAL", "jurisdiction": "US",
        "decided_by": "vishnu",
    })).json()
    repo_id = first["repository_id"]
    assert first["auto_applied"] is True

    # Second BRD must NOT auto-apply — it should produce a PENDING proposal
    brd2 = await _seed_brd(db_session, name="BRD-PL-2026-002.docx")
    await _seed_rule_set(db_session, brd2, [
        _rule("R-DTI-001", "DTI cap tighter", "dti_ratio", ">", 0.35,
              subsystem="DTI_GATE", priority=90),
    ])
    second = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd2.id),
        "product": "PERSONAL", "jurisdiction": "US",
    })).json()
    assert second["auto_applied"] is False
    assert second["repository_id"] == repo_id  # same default repo found
    assert second["new_version_number"] is None

    # Inspect the proposal — it should classify as THRESHOLD_TIGHTENING
    proposal = (await client.get(f"/api/v1/merge-proposal/{second['proposal_id']}")).json()
    assert proposal["status"] == "PENDING"
    assert proposal["counts_by_category"].get("THRESHOLD_TIGHTENING") == 1


# ── Retirement signals (Layer 1) ─────────────────────────────────────────

def test_signal_from_retires_pattern_well_formed():
    sig = signal_from_retires_pattern({
        "subsystem": "DTI_GATE",
        "field": "dti_ratio",
        "operator_class": "GT",
        "basis": "explicit_replacement",
        "evidence_section": "Section 4.1",
    })
    assert sig is not None
    assert sig["canonical_key"] == "DTI_GATE::dti_ratio::GT::REJECT::DECISION"
    assert sig["basis"] == "explicit_replacement"
    assert sig["evidence_section"] == "Section 4.1"


def test_signal_from_retires_pattern_returns_none_when_incomplete():
    assert signal_from_retires_pattern({}) is None
    assert signal_from_retires_pattern({"subsystem": "DTI_GATE"}) is None
    assert signal_from_retires_pattern("not a dict") is None  # type: ignore[arg-type]


def test_extract_retirement_signals_walks_full_payload():
    payload = [
        {"rule_id": "X", "retires_pattern": {
            "subsystem": "DTI_GATE", "field": "dti_ratio",
            "operator_class": "GT", "basis": "explicit_replacement",
        }},
        {"rule_id": "Y"},  # no retires_pattern — ignored
        {"rule_id": "Z", "retires_pattern": {
            "subsystem": "BUREAU_GATE", "field": "bureau_score",
            "operator_class": "LT", "basis": "supersedes_full_table",
        }},
    ]
    signals = extract_retirement_signals(payload)
    assert len(signals) == 2
    keys = {s["canonical_key"] for s in signals}
    assert "DTI_GATE::dti_ratio::GT::REJECT::DECISION" in keys
    assert "BUREAU_GATE::bureau_score::LT::REJECT::DECISION" in keys


def test_merge_engine_picks_up_retirement_signals():
    """Live has a rule that the incoming BRD's retirement signal targets.
    The merge engine should emit a REMOVED_RULE item with action RETIRE
    and high confidence."""
    live = [{
        "id": "L1", "rule_id": "L1", "rule_name": "Legacy DTI cap",
        "subsystem": "DTI_GATE",
        "canonical_key": "DTI_GATE::dti_ratio::GT::REJECT::DECISION",
        "conditions": [{"field": "dti_ratio", "operator": ">", "value": 0.40}],
        "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                     "value": "REJECTED", "description": "DTI"}],
    }]
    incoming = []  # incoming BRD has no DTI rule — only the retirement signal
    signals = [{"canonical_key": "DTI_GATE::dti_ratio::GT::REJECT::DECISION",
                "basis": "explicit_replacement",
                "evidence_section": "Section 4.1"}]
    specs = diff_rule_sets(incoming, live, retirement_signals=signals)
    # Should produce exactly one REMOVED_RULE item
    removals = [s for s in specs if s.category.value == "REMOVED_RULE"]
    assert len(removals) == 1
    assert removals[0].suggested_action.value == "RETIRE"
    assert removals[0].confidence >= 0.9
    assert "explicit_replacement" in removals[0].rationale


async def test_propose_from_brd_threads_retirement_signals_through(client, db_session):
    """End-to-end: baseline a repo, then submit a BRD where the
    incoming rule_set is paired with retirement_signals via the
    service. The merge proposal should include a REMOVED_RULE item."""
    # Baseline with two rules
    brd1 = await _seed_brd(db_session)
    await _seed_rule_set(db_session, brd1, [
        _rule("R-BUR-001", "FICO floor", "bureau_score", "<", 720,
              subsystem="BUREAU_GATE", priority=100),
        _rule("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.40,
              subsystem="DTI_GATE", priority=90),
    ])
    first = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd1.id),
        "decided_by": "vishnu",
    })).json()
    repo_id = first["repository_id"]
    assert first["auto_applied"] is True

    # Submit BRD2 that introduces a new BUREAU rule and explicitly
    # retires the DTI gate. This service-level call simulates what the
    # extractor pipeline will pass once the prompt change is wired.
    brd2 = await _seed_brd(db_session, name="BRD-2.docx")
    rs2 = await _seed_rule_set(db_session, brd2, [
        _rule("R-BUR-002", "Inquiry cap", "inquiries_last_3m", ">", 3,
              subsystem="BUREAU_GATE", priority=80),
    ])

    # Direct service call so we can pass retirement_signals
    proposal, version = await svc.propose_from_brd(
        db_session,
        brd_id=brd2.id,
        retirement_signals=[{
            "canonical_key": "DTI_GATE::dti_ratio::GT::REJECT::DECISION",
            "basis": "explicit_replacement",
            "evidence_section": "Section 4.1",
        }],
        decided_by="vishnu",
    )
    assert version is None  # repo wasn't empty, no auto-apply

    # Re-fetch via API to check item categories
    p = (await client.get(f"/api/v1/merge-proposal/{proposal.id}")).json()
    cats = p["counts_by_category"]
    assert cats.get("NEW_RULE") == 1     # the inquiry rule
    assert cats.get("REMOVED_RULE") == 1  # the retired DTI gate
    # Apply the proposal — DTI rule should disappear from the snapshot
    apply_resp = (await client.post(
        f"/api/v1/merge-proposal/{proposal.id}/apply",
        json={"decided_by": "vishnu"},
    )).json()
    assert apply_resp["applied"] is True
    new_v = apply_resp["new_version_number"]
    snapshot = (await client.get(f"/api/v1/live-repo/{repo_id}/version/{new_v}")).json()
    canonical_keys = {r["canonical_key"] for r in snapshot["rule_snapshot"]}
    assert "DTI_GATE::dti_ratio::GT::REJECT::DECISION" not in canonical_keys
    assert "BUREAU_GATE::bureau_score::LT::REJECT::DECISION" in canonical_keys           # FICO survived
    assert "BUREAU_GATE::inquiries_last_3m::GT::REJECT::DECISION" in canonical_keys      # new rule added
