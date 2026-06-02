"""Slice 1 — decision attribution + audit timeline.

Every verb-button in the system (approve / apply / promote / run-impact
/ execute-suite) now records an actor + optional rationale, both
persisted on the underlying entity AND appended to the audit log so
the per-BRD timeline can render the chronology.
"""
from __future__ import annotations

import pytest

from app.models.brd import BrdDocument, FileType
from app.models.loan_record import LoanRecord
from app.models.rule import Rule, RuleSet, RuleSetStatus, RuleType, Subsystem


pytestmark = pytest.mark.anyio


# ── Helpers (mirror those in test_slice4_wireups for consistency) ───────


async def _seed_brd(db_session, name="ATTR.docx") -> BrdDocument:
    brd = BrdDocument(
        filename=name, file_path=f"/data/{name}",
        file_type=FileType.DOCX, parsed_content="…",
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
          subsystem="BUREAU_GATE", priority=0, desc="x"):
    return {
        "rule_id": rid, "rule_name": name, "subsystem": subsystem,
        "priority": priority, "description": desc,
        "conditions": [{"field": field, "operator": op, "value": val, "logic": "AND"}],
        "actions": [{"action_type": action, "target_field": target,
                     "value": "REJECTED", "description": desc}],
    }


def _us_loan(loan_id: str, *, fico: int, dti: float = 0.30,
             monthly_income: float = 8000, desired_amount: float = 25000) -> dict:
    return {
        "loan_application_id": loan_id,
        "application_type": "DIGITAL",
        "credit_policy": "PERSONAL",
        "desired_amount": desired_amount,
        "borrower_credit_model": {
            "customer_inputs": {
                "monthly_income": monthly_income,
                "annual_income": monthly_income * 12,
            },
            "banking_inputs": {},
            "bureau_credits": {"bureau_score": fico, "inquiries_last_3m": 1},
        },
        "calculated_attributes": {
            "debt_to_income_ratio": dti,
            "scores": {"g5": {"score": 0.75}, "g6": {"score": 0.7}},
        },
        "decision_context": {"risk_segment": "PRIME"},
    }


async def _seed_loans(db_session, payloads):
    for p in payloads:
        db_session.add(LoanRecord(
            loan_application_id=p["loan_application_id"],
            request_payload=p,
            response_payload={"decision_status": "APPROVED"},
        ))
    await db_session.commit()


# ── 1. Approve writes attribution + audit event ─────────────────────────


async def test_approve_rule_set_records_actor_notes_and_audit_event(client, db_session):
    brd = await _seed_brd(db_session)
    rs = await _seed_rule_set(db_session, brd, [
        _rule("R1", "Low FICO reject", "bureau_score", "<", 600),
    ])

    r = await client.patch(
        f"/api/v1/rule-sets/{rs.id}/approve",
        json={"approved_by": "anita.kapoor",
              "approval_notes": "spot-checked the FICO band rule against the source PDF"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "APPROVED"
    assert body["approved_by"] == "anita.kapoor"
    assert body["approved_at"] is not None
    assert "spot-checked" in (body["approval_notes"] or "")

    # Audit timeline contains the approval event.
    audit = (await client.get(f"/api/v1/audit-events?brd_id={brd.id}")).json()
    actions = [e["action"] for e in audit]
    assert "RULE_SET_APPROVED" in actions
    approval = next(e for e in audit if e["action"] == "RULE_SET_APPROVED")
    assert approval["actor"] == "anita.kapoor"
    assert "spot-checked" in (approval["rationale"] or "")
    assert approval["entity_type"] == "RULE_SET"


async def test_approve_rule_set_works_without_attribution_for_back_compat(client, db_session):
    brd = await _seed_brd(db_session, "back-compat.docx")
    rs = await _seed_rule_set(db_session, brd, [
        _rule("R1", "x", "bureau_score", "<", 600),
    ])

    # Empty body — old clients should still work.
    r = await client.patch(f"/api/v1/rule-sets/{rs.id}/approve")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "APPROVED"
    assert body["approved_by"] == "reviewer"  # falls back to default
    assert body["approval_notes"] is None


# ── 2. Apply merge proposal records rationale ───────────────────────────


async def test_apply_merge_proposal_records_decision_rationale(client, db_session):
    brd = await _seed_brd(db_session, "apply.docx")
    await _seed_rule_set(db_session, brd, [
        _rule("R1", "Low FICO reject", "bureau_score", "<", 600),
    ])
    await _seed_loans(db_session, [_us_loan("LA-1", fico=650)])

    propose = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "product": "PERSONAL", "jurisdiction": "US",
        "auto_apply_when_empty": False,  # we'll apply manually with rationale
    })).json()
    proposal_id = propose["proposal_id"]

    r = await client.post(
        f"/api/v1/merge-proposal/{proposal_id}/apply",
        json={"decided_by": "marc.boutin",
              "rationale": "all SOFT items reviewed; no HARD conflicts present"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is True

    # Proposal carries the attribution.
    proposal = (await client.get(f"/api/v1/merge-proposal/{proposal_id}")).json()
    assert proposal["status"] == "APPLIED"
    assert proposal["decided_by"] == "marc.boutin"
    assert "no HARD conflicts" in (proposal["decision_rationale"] or "")

    # Version summary weaves the rationale in so the timeline renders it.
    repo_id = propose["repository_id"]
    v_n = body["new_version_number"]
    version = (await client.get(f"/api/v1/live-repo/{repo_id}/version/{v_n}")).json()
    assert "marc.boutin" in (version["summary"] or "")
    assert "no HARD conflicts" in (version["summary"] or "")

    # Audit log captured the apply.
    audit = (await client.get(f"/api/v1/audit-events?brd_id={brd.id}")).json()
    apply_evs = [e for e in audit if e["action"] == "MERGE_PROPOSAL_APPLIED"]
    assert len(apply_evs) == 1
    assert apply_evs[0]["actor"] == "marc.boutin"


# ── 3. Promote version writes attribution + audit event ─────────────────


async def test_promote_version_records_rationale_and_audit_event(client, db_session):
    brd = await _seed_brd(db_session, "promote.docx")
    await _seed_rule_set(db_session, brd, [
        _rule("R1", "x", "bureau_score", "<", 600),
    ])
    await _seed_loans(db_session, [_us_loan("LA-1", fico=650)])
    propose = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "product": "PERSONAL", "jurisdiction": "US",
        "auto_apply_when_empty": True, "decided_by": "auto-baseline",
    })).json()
    repo_id = propose["repository_id"]
    # auto-applied as v1 → already production. Promote it explicitly.

    r = await client.post(
        f"/api/v1/live-repo/{repo_id}/promote",
        json={"version_number": 1,
              "promoted_by": "release-bot",
              "rationale": "scenario tests pass + impact within tolerance"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["promoted_by"] == "release-bot"
    assert "scenario tests" in (body["rationale"] or "")

    # Repo summary reflects the rationale on subsequent reads.
    repo = (await client.get(f"/api/v1/live-repo/{repo_id}")).json()
    assert repo["production_promoted_by"] == "release-bot"
    assert "scenario tests" in (repo["production_promotion_rationale"] or "")

    # Audit event present.
    audit = (await client.get(f"/api/v1/audit-events?brd_id={brd.id}")).json()
    promote_evs = [e for e in audit if e["action"] == "VERSION_PROMOTED"]
    assert len(promote_evs) == 1
    assert promote_evs[0]["actor"] == "release-bot"
    assert promote_evs[0]["metadata"]["version_number"] == 1


# ── 4. Impact run records rationale + emits paired START/COMPLETE events ──


async def test_impact_run_records_rationale_and_emits_audit_events(client, db_session):
    brd = await _seed_brd(db_session, "impact.docx")
    await _seed_rule_set(db_session, brd, [
        _rule("R1", "x", "bureau_score", "<", 600),
    ])
    await _seed_loans(db_session, [
        _us_loan("LA-1", fico=650),
        _us_loan("LA-2", fico=550),
    ])
    propose = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "product": "PERSONAL", "jurisdiction": "US",
        "auto_apply_when_empty": True, "decided_by": "auto-baseline",
    })).json()
    repo_id = propose["repository_id"]
    v1 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/1")).json()

    r = await client.post("/api/v1/impact-run", json={
        "repository_id": repo_id,
        "candidate_version_id": v1["id"],
        "created_by": "ops-team",
        "rationale": "pre-promotion regression check before approving v2",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created_by"] == "ops-team"
    assert "pre-promotion" in (body["rationale"] or "")

    audit = (await client.get(f"/api/v1/audit-events?brd_id={brd.id}")).json()
    actions = [e["action"] for e in audit]
    assert "IMPACT_RUN_STARTED" in actions
    assert "IMPACT_RUN_COMPLETED" in actions
    started = next(e for e in audit if e["action"] == "IMPACT_RUN_STARTED")
    assert started["actor"] == "ops-team"
    assert "pre-promotion" in (started["rationale"] or "")


# ── 5. Execute suite records executor + rationale ───────────────────────


async def test_execute_suite_records_executor_and_audit_event(client, db_session):
    brd = await _seed_brd(db_session, "exec.docx")
    await _seed_rule_set(db_session, brd, [
        _rule("R1", "Low FICO reject", "bureau_score", "<", 600),
    ])
    await _seed_loans(db_session, [
        _us_loan(f"LA-{i:03d}", fico=550) for i in range(5)
    ])
    propose = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "product": "PERSONAL", "jurisdiction": "US",
        "auto_apply_when_empty": True, "decided_by": "auto-baseline",
    })).json()
    repo_id = propose["repository_id"]
    v1 = (await client.get(f"/api/v1/live-repo/{repo_id}/version/1")).json()

    suite = (await client.post("/api/v1/test-cases/generate-from-version", json={
        "version_id": v1["id"], "negative_count": 1, "max_matches": 3,
    })).json()
    suite_id = suite["id"]

    r = await client.post(
        f"/api/v1/test-cases/{suite_id}/execute",
        json={"version_id": v1["id"],
              "executed_by": "qa-team",
              "rationale": "validating new FICO floor before sign-off"},
    )
    assert r.status_code == 200, r.text

    # The suite detail now exposes who ran it.
    detail = (await client.get(f"/api/v1/test-cases/{suite_id}")).json()
    assert detail["last_executed_by"] == "qa-team"
    assert "validating new FICO floor" in (detail["last_execution_rationale"] or "")

    audit = (await client.get(f"/api/v1/audit-events?brd_id={brd.id}")).json()
    exec_evs = [e for e in audit if e["action"] == "SUITE_EXECUTED"]
    assert len(exec_evs) == 1
    assert exec_evs[0]["actor"] == "qa-team"
    assert exec_evs[0]["metadata"]["version_number"] == 1


# ── 6. Audit query routes work for all three filter shapes ──────────────


async def test_audit_query_filters_work(client, db_session):
    """Smoke-test the three filter shapes the timeline UI will use:
    by brd_id, by repository_id, by entity. All return events newest-first
    and respect the limit parameter."""
    brd = await _seed_brd(db_session, "filt.docx")
    rs = await _seed_rule_set(db_session, brd, [
        _rule("R1", "x", "bureau_score", "<", 600),
    ])
    await _seed_loans(db_session, [_us_loan("LA-1", fico=550)])

    # Trigger several events.
    await client.patch(f"/api/v1/rule-sets/{rs.id}/approve",
                       json={"approved_by": "u1"})
    propose = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "product": "PERSONAL", "jurisdiction": "US",
        "auto_apply_when_empty": True, "decided_by": "u2",
    })).json()
    repo_id = propose["repository_id"]
    await client.post(f"/api/v1/live-repo/{repo_id}/promote",
                      json={"version_number": 1, "promoted_by": "u3"})

    # by brd
    by_brd = (await client.get(f"/api/v1/audit-events?brd_id={brd.id}")).json()
    assert len(by_brd) >= 2

    # by repo
    by_repo = (await client.get(f"/api/v1/audit-events?repository_id={repo_id}")).json()
    repo_actions = {e["action"] for e in by_repo}
    assert "VERSION_PROMOTED" in repo_actions

    # by entity (the rule_set)
    by_entity = (await client.get(
        f"/api/v1/audit-events?entity_type=RULE_SET&entity_id={rs.id}"
    )).json()
    assert any(e["action"] == "RULE_SET_APPROVED" for e in by_entity)

    # default-list with limit
    all_events = (await client.get("/api/v1/audit-events?limit=2")).json()
    assert len(all_events) <= 2
