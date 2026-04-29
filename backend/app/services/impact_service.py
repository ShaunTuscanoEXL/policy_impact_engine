"""Impact-run service: evaluate two LiveRuleVersions against the
loan_records corpus and report what changed.

Slice 2 ships an in-process synchronous runner. The API surface is
designed so that swapping the runner to Celery later is invisible to
callers — POST returns immediately with status PENDING, the worker
flips it to RUNNING then COMPLETED. For now we run inline (the
loan_records corpus is 10k records and the evaluator does ~30 rules
in pure Python — well under a second).

Summary shape (see docs/plans/2026-04-30-live-rule-repository.md §4.7):

    {
      "total_loans": 10000,
      "decision_distribution": {
        "base":      {"APPROVED": 6240, "FLAGGED": 1180, "REJECTED": 2580},
        "candidate": {"APPROVED": 5970, "FLAGGED": 1310, "REJECTED": 2720}
      },
      "decision_flips": {
        "approved_to_rejected": 320,
        "rejected_to_approved": 50,
        "approved_to_flagged": 130,
        "flagged_to_approved": 20,
        ...
      },
      "by_subsystem": {"DTI_GATE": {"flips_caused": 280}},
      "by_segment":   {"PRIME": {"approval_rate_change": -0.034}, ...}
    }
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.impact import ImpactRun, ImpactRunStatus
from app.models.live_repo import LiveRuleVersion
from app.models.loan_record import LoanRecord
from app.runtime.rule_engine import (
    DecisionResult,
    evaluate_snapshot,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _empty_dist() -> dict[str, int]:
    return {"APPROVED": 0, "FLAGGED": 0, "REJECTED": 0}


def _flip_key(base: str, candidate: str) -> str:
    return f"{base.lower()}_to_{candidate.lower()}"


def _segment_for(loan: LoanRecord) -> str:
    """Best-effort segmentation from request_payload.decision_context.risk_segment.
    Falls back to UNKNOWN if missing."""
    try:
        ctx = (loan.request_payload or {}).get("decision_context") or {}
        return str(ctx.get("risk_segment") or "UNKNOWN").upper()
    except (AttributeError, TypeError):
        return "UNKNOWN"


def _summarize(
    base_results: list[tuple[LoanRecord, DecisionResult]],
    candidate_results: list[tuple[LoanRecord, DecisionResult]],
) -> dict:
    total = len(base_results)
    base_dist = _empty_dist()
    cand_dist = _empty_dist()
    flips: dict[str, int] = {}
    by_subsystem: dict[str, dict[str, int]] = {}
    by_segment_base: dict[str, dict[str, int]] = {}
    by_segment_cand: dict[str, dict[str, int]] = {}

    for (loan, base_r), (_, cand_r) in zip(base_results, candidate_results):
        base_dist[base_r.decision] = base_dist.get(base_r.decision, 0) + 1
        cand_dist[cand_r.decision] = cand_dist.get(cand_r.decision, 0) + 1

        seg = _segment_for(loan)
        by_segment_base.setdefault(seg, _empty_dist())
        by_segment_cand.setdefault(seg, _empty_dist())
        by_segment_base[seg][base_r.decision] = by_segment_base[seg].get(base_r.decision, 0) + 1
        by_segment_cand[seg][cand_r.decision] = by_segment_cand[seg].get(cand_r.decision, 0) + 1

        if base_r.decision != cand_r.decision:
            key = _flip_key(base_r.decision, cand_r.decision)
            flips[key] = flips.get(key, 0) + 1
            # Attribute the flip to the candidate's terminal subsystem
            if cand_r.fired_rules:
                terminal = cand_r.fired_rules[-1]
                by_subsystem.setdefault(terminal.subsystem, {"flips_caused": 0})
                by_subsystem[terminal.subsystem]["flips_caused"] += 1

    by_segment_summary: dict[str, dict[str, float]] = {}
    for seg in set(by_segment_base) | set(by_segment_cand):
        b = by_segment_base.get(seg, _empty_dist())
        c = by_segment_cand.get(seg, _empty_dist())
        b_total = sum(b.values()) or 1
        c_total = sum(c.values()) or 1
        b_appr = b.get("APPROVED", 0) / b_total
        c_appr = c.get("APPROVED", 0) / c_total
        by_segment_summary[seg] = {
            "loans": b_total,
            "base_approval_rate": round(b_appr, 4),
            "candidate_approval_rate": round(c_appr, 4),
            "approval_rate_change": round(c_appr - b_appr, 4),
        }

    return {
        "total_loans": total,
        "decision_distribution": {
            "base": base_dist,
            "candidate": cand_dist,
        },
        "decision_flips": flips,
        "by_subsystem": by_subsystem,
        "by_segment": by_segment_summary,
    }


# ── Loan iteration (in-memory for slice 2) ──────────────────────────────

async def _load_loans(
    db: AsyncSession,
    *,
    limit: int | None,
) -> list[LoanRecord]:
    """Fetch a batch of LoanRecords. Slice 2 keeps this simple — bulk
    fetch with optional limit. A future slice can stream in chunks via
    server-side cursors when corpus grows to 1M+."""
    stmt = select(LoanRecord)
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars())


# ── Public service API ──────────────────────────────────────────────────

async def get_impact_run(db: AsyncSession, run_id: uuid.UUID) -> ImpactRun | None:
    return await db.get(ImpactRun, run_id)


async def list_impact_runs(
    db: AsyncSession, *, repository_id: uuid.UUID | None = None
) -> list[ImpactRun]:
    stmt = select(ImpactRun).order_by(ImpactRun.created_at.desc())
    if repository_id:
        stmt = stmt.where(ImpactRun.repository_id == repository_id)
    return list((await db.execute(stmt)).scalars())


async def execute_impact_run(
    db: AsyncSession,
    *,
    repository_id: uuid.UUID,
    base_version_id: uuid.UUID | None,
    candidate_version_id: uuid.UUID,
    loan_record_filter: dict | None = None,
    created_by: str | None = None,
) -> ImpactRun:
    """Synchronously run the impact evaluation and persist the result.

    Pass ``base_version_id=None`` to compare against a do-nothing
    baseline (every loan APPROVED) — useful when you want to see
    "what does the candidate do on its own".
    """
    # Load both snapshots
    cand_version = await db.get(LiveRuleVersion, candidate_version_id)
    if cand_version is None:
        raise ValueError(f"Candidate version {candidate_version_id} not found")
    cand_snapshot: list[dict] = list(cand_version.rule_snapshot or [])

    base_snapshot: list[dict] = []
    if base_version_id is not None:
        base_version = await db.get(LiveRuleVersion, base_version_id)
        if base_version is None:
            raise ValueError(f"Base version {base_version_id} not found")
        base_snapshot = list(base_version.rule_snapshot or [])

    # Persist the run row first (RUNNING)
    run = ImpactRun(
        repository_id=repository_id,
        base_version_id=base_version_id,
        candidate_version_id=candidate_version_id,
        loan_record_filter=loan_record_filter,
        status=ImpactRunStatus.RUNNING,
        created_by=created_by,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    try:
        limit = (loan_record_filter or {}).get("limit") if isinstance(loan_record_filter, dict) else None
        loans = await _load_loans(db, limit=limit)

        base_results: list[tuple[LoanRecord, DecisionResult]] = []
        cand_results: list[tuple[LoanRecord, DecisionResult]] = []
        for loan in loans:
            req = loan.request_payload or {}
            base_results.append((loan, evaluate_snapshot(
                base_snapshot, req, loan_application_id=loan.loan_application_id,
            )))
            cand_results.append((loan, evaluate_snapshot(
                cand_snapshot, req, loan_application_id=loan.loan_application_id,
            )))

        run.summary = _summarize(base_results, cand_results)
        run.status = ImpactRunStatus.COMPLETED
        run.completed_at = datetime.utcnow()
    except Exception as exc:  # noqa: BLE001 — surface any runtime error
        run.status = ImpactRunStatus.FAILED
        run.error = repr(exc)
        run.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(run)
    return run


# ── In-memory runner for unit tests (no DB) ─────────────────────────────

def evaluate_pair_in_memory(
    base_snapshot: list[dict],
    candidate_snapshot: list[dict],
    loans: Iterable[dict],
) -> dict:
    """Run impact evaluation against a list of loan request_payload dicts
    (as opposed to LoanRecord ORM rows). Used by unit tests."""
    base_results = []
    cand_results = []

    class _LoanProxy:
        """Minimal ORM-row stand-in so _summarize works without DB."""
        def __init__(self, payload: dict, app_id: str):
            self.request_payload = payload
            self.loan_application_id = app_id

    for i, payload in enumerate(loans):
        proxy = _LoanProxy(payload, f"LA-test-{i:06d}")
        base_results.append((proxy, evaluate_snapshot(
            base_snapshot, payload, loan_application_id=proxy.loan_application_id,
        )))
        cand_results.append((proxy, evaluate_snapshot(
            candidate_snapshot, payload, loan_application_id=proxy.loan_application_id,
        )))
    return _summarize(base_results, cand_results)
