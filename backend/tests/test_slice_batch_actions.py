"""Slice 6 — bulk decisions on merge proposal items."""
from __future__ import annotations

import pytest

from app.models.brd import BrdDocument, FileType
from app.models.loan_record import LoanRecord
from app.models.merge import (
    MergeItemCategory,
    MergeItemSeverity,
    MergeProposalItem,
    MergeSuggestedAction,
)
from app.models.rule import Rule, RuleSet, RuleSetStatus, RuleType, Subsystem
from sqlalchemy import select


pytestmark = pytest.mark.anyio


async def _seed_brd(db_session, name="BATCH.docx") -> BrdDocument:
    brd = BrdDocument(
        filename=name, file_path=f"/data/{name}",
        file_type=FileType.DOCX, parsed_content="…",
    )
    db_session.add(brd)
    await db_session.commit()
    await db_session.refresh(brd)
    return brd


async def _seed_rule_set(db_session, brd, rules) -> RuleSet:
    rs = RuleSet(brd_document_id=brd.id, version=1,
                 name=f"Rules from {brd.filename}", status=RuleSetStatus.DRAFT)
    db_session.add(rs)
    await db_session.flush()
    for r in rules:
        db_session.add(Rule(
            rule_set_id=rs.id,
            rule_id=r["rule_id"], rule_name=r["rule_name"],
            description=r.get("description"),
            rule_type=RuleType(r.get("rule_type", "ELIGIBILITY")),
            subsystem=Subsystem(r.get("subsystem", "BUREAU_GATE")),
            conditions=r["conditions"], actions=r["actions"],
            priority=r.get("priority", 0),
        ))
    await db_session.commit()
    await db_session.refresh(rs)
    return rs


def _rule(rid, field, op, val):
    return {
        "rule_id": rid, "rule_name": f"Rule {rid}",
        "subsystem": "BUREAU_GATE",
        "conditions": [{"field": field, "operator": op, "value": val, "logic": "AND"}],
        "actions": [{"action_type": "REJECT", "target_field": "decision_status",
                     "value": "REJECTED", "description": "x"}],
    }


def _us_loan(loan_id: str, fico: int = 700) -> dict:
    return {
        "loan_application_id": loan_id, "desired_amount": 10000,
        "borrower_credit_model": {"customer_inputs": {"monthly_income": 5000},
                                  "bureau_credits": {"bureau_score": fico}},
        "calculated_attributes": {"debt_to_income_ratio": 0.3},
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


async def _make_proposal_with_mixed_items(client, db_session, brd):
    """Two BRDs into the same repo to get a non-trivial merge proposal:
    first BRD baselines as v1, second BRD's similar+new rules generate
    a mix of EXACT_DUPLICATE / NEW_RULE / etc items."""
    # First BRD baselines the repo
    propose1 = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd.id), "product": "PERSONAL", "jurisdiction": "US",
        "auto_apply_when_empty": True, "decided_by": "auto",
    })).json()
    repo_id = propose1["repository_id"]

    # Second BRD with overlap + new rules
    brd2 = await _seed_brd(db_session, "BATCH2.docx")
    await _seed_rule_set(db_session, brd2, [
        _rule("R1", "bureau_score", "<", 650),       # may dup with v1's R1
        _rule("R-NEW", "bureau_score", "<", 600),    # NEW
        _rule("R-NEW2", "monthly_income", "<", 1500),# NEW
    ])
    propose2 = (await client.post("/api/v1/live-repo/propose-from-brd", json={
        "brd_id": str(brd2.id), "product": "PERSONAL", "jurisdiction": "US",
        "auto_apply_when_empty": False,
    })).json()
    return propose2["proposal_id"], repo_id


async def test_batch_accept_all_new_rule_items_skips_existing(client, db_session):
    brd = await _seed_brd(db_session)
    await _seed_rule_set(db_session, brd, [
        _rule("R1", "bureau_score", "<", 650),
        _rule("R-OLD", "bureau_score", "<", 700),
    ])
    await _seed_loans(db_session, [_us_loan("L1")])
    proposal_id, _ = await _make_proposal_with_mixed_items(client, db_session, brd)

    # Pre-set one item's user_action so we can verify it isn't overwritten.
    items = (await client.get(f"/api/v1/merge-proposal/{proposal_id}")).json()["items"]
    new_rule_items = [i for i in items if i["category"] == "NEW_RULE"]
    assert len(new_rule_items) >= 1, items
    first_id = new_rule_items[0]["id"]
    await client.patch(
        f"/api/v1/merge-proposal/{proposal_id}/items/{first_id}",
        json={"user_action": "REJECT"},
    )

    # Bulk-accept all NEW_RULE items.
    r = await client.post(
        f"/api/v1/merge-proposal/{proposal_id}/batch-update",
        json={"user_action": "ACCEPT", "category": "NEW_RULE"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # The pre-set item must have been skipped, the rest accepted.
    assert body["skipped_existing"] >= 1
    assert body["updated"] >= 1
    assert body["user_action"] == "ACCEPT"

    # Verify the pre-set item still REJECT and the others are ACCEPT.
    final = (await client.get(f"/api/v1/merge-proposal/{proposal_id}")).json()["items"]
    pre_set = next(i for i in final if i["id"] == first_id)
    assert pre_set["user_action"] == "REJECT"
    others = [i for i in final if i["category"] == "NEW_RULE" and i["id"] != first_id]
    for it in others:
        assert it["user_action"] == "ACCEPT", it


async def test_batch_overwrite_existing_replaces_prior_decisions(client, db_session):
    brd = await _seed_brd(db_session, "OVERWRITE.docx")
    await _seed_rule_set(db_session, brd, [
        _rule("R1", "bureau_score", "<", 650),
    ])
    await _seed_loans(db_session, [_us_loan("L1")])
    proposal_id, _ = await _make_proposal_with_mixed_items(client, db_session, brd)

    # Pre-set an INFO item to REJECT.
    items = (await client.get(f"/api/v1/merge-proposal/{proposal_id}")).json()["items"]
    info_items = [i for i in items if i["severity"] == "INFO"]
    if not info_items:
        pytest.skip("No INFO items present to exercise overwrite path.")
    first_id = info_items[0]["id"]
    await client.patch(
        f"/api/v1/merge-proposal/{proposal_id}/items/{first_id}",
        json={"user_action": "REJECT"},
    )

    # Bulk accept INFO with overwrite_existing=True.
    r = await client.post(
        f"/api/v1/merge-proposal/{proposal_id}/batch-update",
        json={"user_action": "ACCEPT", "severity": "INFO", "overwrite_existing": True},
    )
    body = r.json()
    assert body["skipped_existing"] == 0  # nothing skipped — overwrite was on
    final = (await client.get(f"/api/v1/merge-proposal/{proposal_id}")).json()["items"]
    after = next(i for i in final if i["id"] == first_id)
    assert after["user_action"] == "ACCEPT"


async def test_batch_unmatched_items_unaffected(client, db_session):
    brd = await _seed_brd(db_session, "UNMATCHED.docx")
    await _seed_rule_set(db_session, brd, [
        _rule("R1", "bureau_score", "<", 650),
    ])
    await _seed_loans(db_session, [_us_loan("L1")])
    proposal_id, _ = await _make_proposal_with_mixed_items(client, db_session, brd)

    # Filter for a category that doesn't exist in this proposal.
    r = await client.post(
        f"/api/v1/merge-proposal/{proposal_id}/batch-update",
        json={"user_action": "ACCEPT", "category": "OPPOSITE_DIRECTION"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["updated"] == 0
    assert body["skipped_unmatched"] >= 1
