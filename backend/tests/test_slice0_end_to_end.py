"""Slice 0 end-to-end integration test.

Exercises the whole walking-skeleton flow against a SQLite test app:

    1. Create a live repo (POST /live-repo)
    2. Seed a BRD + an initial rule_set with rules
    3. Build a merge proposal (POST /merge-proposal)
    4. Inspect items
    5. Apply (POST /merge-proposal/{id}/apply)
    6. Pull HEAD as Python (GET /live-repo/{id}/export.py)

No LLM, no real BRD parsing — we seed rules directly via the DB session
so the test only exercises the new live-repo + merge code paths.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.brd import BrdDocument, FileType
from app.models.rule import Rule, RuleSet, RuleSetStatus, RuleType, Subsystem


pytestmark = pytest.mark.anyio


# ── Helpers ──────────────────────────────────────────────────────────────

async def _seed_brd(db_session) -> BrdDocument:
    brd = BrdDocument(
        filename="BRD-PL-2026-001-DTI.docx",
        file_path="/data/sample_brds/BRD-PL-2026-001-DTI.docx",
        file_type=FileType.DOCX,
        parsed_content="DTI cap tightening BRD body…",
    )
    db_session.add(brd)
    await db_session.commit()
    await db_session.refresh(brd)
    return brd


async def _seed_rule_set(db_session, brd: BrdDocument, rules: list[dict]) -> RuleSet:
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
          desc="x", subsystem="UNCLASSIFIED", priority=0):
    return {
        "rule_id": rid, "rule_name": name, "subsystem": subsystem,
        "priority": priority, "description": desc,
        "conditions": [{"field": field, "operator": op, "value": val, "logic": "AND"}],
        "actions": [{"action_type": action, "target_field": target,
                     "value": "REJECTED", "description": desc}],
    }


# ── End-to-end ───────────────────────────────────────────────────────────

async def test_slice0_full_flow(client, db_session):
    # 1) Create the live repository
    r = await client.post("/api/v1/live-repo", json={
        "name": "US Personal Loan",
        "product": "PERSONAL",
        "jurisdiction": "US",
        "description": "Slice 0 e2e",
    })
    assert r.status_code == 201, r.text
    repo = r.json()
    repo_id = repo["id"]
    assert repo["current_version"] == 0  # seeded with empty v0

    # 2) Seed a BRD + 3 rules (FICO floor, DTI cap, inquiry cap)
    brd = await _seed_brd(db_session)
    rs = await _seed_rule_set(db_session, brd, [
        _rule("R-BUR-001", "FICO floor",
              "bureau_score", "<", 700,
              subsystem="BUREAU_GATE", priority=100, desc="FICO_LOW"),
        _rule("R-DTI-001", "DTI cap",
              "dti_ratio", ">", 0.43,
              subsystem="DTI_GATE", priority=90, desc="DTI_HIGH"),
        _rule("R-INQ-001", "Inquiry cap",
              "inquiries_last_3m", ">", 3,
              subsystem="BUREAU_GATE", priority=80, desc="HUNGRY"),
    ])

    # 3) Build a merge proposal — repo is empty so all 3 should be NEW_RULE
    r = await client.post("/api/v1/merge-proposal", json={
        "repository_id": repo_id,
        "source_rule_set_id": str(rs.id),
    })
    assert r.status_code == 201, r.text
    proposal = r.json()
    assert proposal["status"] == "PENDING"
    assert proposal["base_version"] == 0
    assert len(proposal["items"]) == 3
    # All 3 should be classified NEW_RULE (live repo is empty)
    cats = {i["category"] for i in proposal["items"]}
    assert cats == {"NEW_RULE"}
    # No hard blockers — should apply cleanly
    assert proposal["blockers"] == []

    # 4) Apply the proposal → version 1
    r = await client.post(
        f"/api/v1/merge-proposal/{proposal['id']}/apply",
        json={"decided_by": "vishnu"},
    )
    assert r.status_code == 200, r.text
    apply_resp = r.json()
    assert apply_resp["applied"] is True
    assert apply_resp["new_version_number"] == 1
    assert "Applied 3 item(s)" in apply_resp["summary"]

    # 5) Verify the version detail reflects the snapshot
    r = await client.get(f"/api/v1/live-repo/{repo_id}/version/1")
    assert r.status_code == 200, r.text
    v1 = r.json()
    assert v1["version_number"] == 1
    assert v1["rule_count"] == 3
    snapshot_keys = {x["canonical_key"] for x in v1["rule_snapshot"]}
    assert "BUREAU_GATE::bureau_score::LT::REJECT::DECISION" in snapshot_keys
    assert "DTI_GATE::dti_ratio::GT::REJECT::DECISION" in snapshot_keys
    assert "BUREAU_GATE::inquiries_last_3m::GT::REJECT::DECISION" in snapshot_keys

    # 6) Download the generated Python — it should parse + name our rules
    r = await client.get(f"/api/v1/live-repo/{repo_id}/export.py")
    assert r.status_code == 200, r.text
    py = r.text
    assert "LIVE RULE REPOSITORY" in py
    assert "Version: 1" in py
    assert "BUREAU_GATE" in py
    assert "DTI_GATE" in py
    assert "def fico_floor" in py
    assert "def dti_cap" in py
    assert "def inquiry_cap" in py
    # And it must be valid Python
    import ast
    ast.parse(py)

    # 7) HEAD repository now reports current_version=1
    r = await client.get(f"/api/v1/live-repo/{repo_id}")
    assert r.status_code == 200, r.text
    repo_after = r.json()
    assert repo_after["current_version"] == 1
    assert any(v["version_number"] == 1 for v in repo_after["versions"])


async def test_slice0_supersede_then_apply(client, db_session):
    """Submit one BRD, apply. Submit a tighter BRD: should produce
    THRESHOLD_TIGHTENING and apply cleanly."""
    # Repo + initial baseline
    r = await client.post("/api/v1/live-repo", json={
        "name": "X", "product": "PERSONAL", "jurisdiction": "US",
    })
    repo_id = r.json()["id"]

    brd1 = await _seed_brd(db_session)
    rs1 = await _seed_rule_set(db_session, brd1, [
        _rule("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.45,
              subsystem="DTI_GATE", priority=90, desc="DTI_HIGH"),
    ])
    proposal_id = (await client.post("/api/v1/merge-proposal", json={
        "repository_id": repo_id, "source_rule_set_id": str(rs1.id),
    })).json()["id"]
    apply_resp = (await client.post(
        f"/api/v1/merge-proposal/{proposal_id}/apply",
        json={"decided_by": "alice"},
    )).json()
    assert apply_resp["applied"] is True
    assert apply_resp["new_version_number"] == 1

    # Second BRD tightens the threshold
    brd2 = await _seed_brd(db_session)
    rs2 = await _seed_rule_set(db_session, brd2, [
        _rule("R-DTI-001-NEW", "DTI cap v2", "dti_ratio", ">", 0.35,
              subsystem="DTI_GATE", priority=90, desc="DTI_HIGH"),
    ])
    p2 = (await client.post("/api/v1/merge-proposal", json={
        "repository_id": repo_id, "source_rule_set_id": str(rs2.id),
    })).json()
    assert p2["counts_by_category"].get("THRESHOLD_TIGHTENING") == 1
    assert p2["counts_by_severity"].get("SOFT") == 1
    assert p2["blockers"] == []

    # Apply → v2
    apply_resp = (await client.post(
        f"/api/v1/merge-proposal/{p2['id']}/apply",
        json={"decided_by": "bob"},
    )).json()
    assert apply_resp["applied"] is True
    assert apply_resp["new_version_number"] == 2

    # The single canonical key now points at the tightened rule (0.35)
    v2 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/2")).json()
    assert v2["rule_count"] == 1
    snapshot = v2["rule_snapshot"]
    assert snapshot[0]["conditions"][0]["value"] == 0.35


async def test_slice0_action_drift_blocks_apply(client, db_session):
    """An incoming rule with the same canonical key but a different
    action (REJECT → FLAG) should be HARD and block apply until
    the reviewer sets user_action."""
    repo_id = (await client.post("/api/v1/live-repo", json={
        "name": "Y", "product": "PERSONAL", "jurisdiction": "US",
    })).json()["id"]

    brd1 = await _seed_brd(db_session)
    rs1 = await _seed_rule_set(db_session, brd1, [
        _rule("R-DTI-001", "DTI cap", "dti_ratio", ">", 0.43,
              subsystem="DTI_GATE", priority=90, desc="DTI_HIGH"),
    ])
    p1 = (await client.post("/api/v1/merge-proposal", json={
        "repository_id": repo_id, "source_rule_set_id": str(rs1.id),
    })).json()
    await client.post(
        f"/api/v1/merge-proposal/{p1['id']}/apply",
        json={"decided_by": "alice"},
    )

    # Incoming changes REJECT → FLAG at the same threshold
    brd2 = await _seed_brd(db_session)
    rs2 = await _seed_rule_set(db_session, brd2, [
        _rule("R-DTI-001-FLAG", "DTI flag", "dti_ratio", ">", 0.43,
              subsystem="DTI_GATE", priority=90, action="FLAG",
              target="decision_status", desc="DTI_REVIEW"),
    ])
    p2 = (await client.post("/api/v1/merge-proposal", json={
        "repository_id": repo_id, "source_rule_set_id": str(rs2.id),
    })).json()
    assert p2["counts_by_category"].get("ACTION_DRIFT") == 1
    assert p2["counts_by_severity"].get("HARD") == 1
    assert len(p2["blockers"]) == 1

    # Apply must FAIL (not raise — return applied=false with blockers list)
    apply_resp = (await client.post(
        f"/api/v1/merge-proposal/{p2['id']}/apply",
        json={"decided_by": "bob"},
    )).json()
    assert apply_resp["applied"] is False
    assert len(apply_resp["blockers"]) == 1

    # Resolve via PATCH: reviewer accepts the FLAG action
    item_id = p2["blockers"][0]
    r = await client.patch(
        f"/api/v1/merge-proposal/{p2['id']}/items/{item_id}",
        json={"user_action": "ACCEPT", "notes": "Reviewer accepts FLAG semantics"},
    )
    assert r.status_code == 200
    assert r.json()["user_action"] == "ACCEPT"

    # Re-apply now succeeds
    apply_resp = (await client.post(
        f"/api/v1/merge-proposal/{p2['id']}/apply",
        json={"decided_by": "bob"},
    )).json()
    assert apply_resp["applied"] is True
    assert apply_resp["new_version_number"] == 2
