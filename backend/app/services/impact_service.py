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


def _desired_amount(loan: LoanRecord) -> float:
    """Best-effort extract of the loan's requested USD amount. Falls
    back to 0.0 when the field is missing/non-numeric so the projected-
    exposure math doesn't crash on partial data."""
    try:
        amt = (loan.request_payload or {}).get("desired_amount")
        if amt is None:
            return 0.0
        return float(amt)
    except (AttributeError, TypeError, ValueError):
        return 0.0


# Decisions that count as "the loan got money" for exposure math. FLAGGED
# is excluded — it goes to manual review, not auto-funded.
_FUNDED_DECISIONS = {"APPROVED"}

# Action types that modify offer terms (not the final APPROVED/FLAGGED/
# REJECTED decision). Slice 13 tracks these so pricing-only BRDs are
# visible in impact analysis instead of always showing "0 flips".
_OFFER_MOD_ACTIONS = {"SET", "ADJUST", "CAP", "MODIFY"}

# Target fields that ARE the final decision (already tracked separately
# in decision_distribution). Excluded from offer-modification tracking
# to avoid double-counting.
_DECISION_TARGETS = {"decision_status", "decision", "status", "outcome", "verdict"}


def _offer_writes(result: "DecisionResult") -> set[tuple[str, str]]:
    """Project a DecisionResult into the set of (target_field, action_type)
    pairs that modify offer terms — anything that's SET/ADJUST/CAP/MODIFY
    on a non-decision field. Returns an empty set when no fired rules
    touch offer terms (decision-only BRDs)."""
    out: set[tuple[str, str]] = set()
    for fr in result.fired_rules or []:
        if not fr.target_field:
            continue
        if fr.action_type not in _OFFER_MOD_ACTIONS:
            continue
        tgt = str(fr.target_field).strip().lower()
        if tgt in _DECISION_TARGETS:
            continue
        out.add((tgt, fr.action_type))
    return out


def _offer_field_class(field: str) -> str:
    """Coarse grouping for the offer-modifications UI — every concrete
    target field maps to a class so the dashboard can show "X loans got
    new RATE adjustments" without listing every field name."""
    f = field.lower()
    if any(x in f for x in ("rate", "apr", "coupon")):
        return "RATE"
    if any(x in f for x in ("amount", "limit", "principal")):
        return "AMOUNT"
    if any(x in f for x in ("tenure", "term", "month", "duration")):
        return "TENURE"
    if any(x in f for x in ("fee", "origination")):
        return "FEE"
    if "segment" in f or "tier" in f or "band" in f:
        return "SEGMENT"
    if "flag" in f or "eligib" in f:
        return "ELIGIBILITY"
    return "OTHER"


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
    by_segment_amount_base: dict[str, float] = {}
    by_segment_amount_cand: dict[str, float] = {}

    # Slice 2: business-friendly metrics — projected USD exposure
    # change, approval-flip counts (split by direction), and the
    # USD impact of each direction. Lets the UI render
    # "$130M less exposure (mostly NEAR_PRIME)" without the policy
    # team having to reconstruct the math from raw flip counts.
    base_funded_amount = 0.0
    cand_funded_amount = 0.0
    loans_newly_denied = 0  # was APPROVED, now isn't
    loans_newly_approved = 0  # was REJECTED/FLAGGED, now APPROVED
    exposure_change_loss = 0.0  # $ no longer funded
    exposure_change_gain = 0.0  # $ newly funded

    # Slice 13: offer-modification tracking — counts loans that gained
    # or lost non-decision writes (SET/ADJUST/CAP/MODIFY on fields like
    # eligible_amount, interest_rate, max_tenure_months). Pricing-only
    # BRDs that previously showed "0 flips" now have a visible signal.
    # Keys are (target_field, action_type); values count loans.
    loans_with_new_write_by_field: dict[str, int] = {}
    loans_with_dropped_write_by_field: dict[str, int] = {}
    loans_with_any_offer_change = 0
    loans_with_offer_change_but_decision_unchanged = 0

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

            # Direction-aware counters for the business summary
            was_funded = base_r.decision in _FUNDED_DECISIONS
            now_funded = cand_r.decision in _FUNDED_DECISIONS
            if was_funded and not now_funded:
                loans_newly_denied += 1
                exposure_change_loss += amt
            elif now_funded and not was_funded:
                loans_newly_approved += 1
                exposure_change_gain += amt

        # Slice 13: track offer-term modifications (non-decision writes)
        # so pricing/eligibility-only BRDs are visible. Diff the SET/
        # ADJUST writes each side made for this loan and bucket gains
        # vs drops by target field.
        base_writes = _offer_writes(base_r)
        cand_writes = _offer_writes(cand_r)
        if base_writes != cand_writes:
            new_writes = cand_writes - base_writes
            dropped_writes = base_writes - cand_writes
            for tgt, _act in new_writes:
                loans_with_new_write_by_field[tgt] = (
                    loans_with_new_write_by_field.get(tgt, 0) + 1
                )
            for tgt, _act in dropped_writes:
                loans_with_dropped_write_by_field[tgt] = (
                    loans_with_dropped_write_by_field.get(tgt, 0) + 1
                )
            loans_with_any_offer_change += 1
            if base_r.decision == cand_r.decision:
                # Offer terms changed but final decision stayed the same
                # — the case that used to be invisible in the dashboard.
                loans_with_offer_change_but_decision_unchanged += 1

    # Per-segment summary with absolute numbers AND deltas — the UI
    # uses the absolutes for hero copy and the deltas for sparklines.
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
            "base_funded_amount_usd": round(by_segment_amount_base.get(seg, 0.0), 2),
            "candidate_funded_amount_usd": round(by_segment_amount_cand.get(seg, 0.0), 2),
            "funded_amount_delta_usd": round(
                by_segment_amount_cand.get(seg, 0.0)
                - by_segment_amount_base.get(seg, 0.0),
                2,
            ),
        }

    # Identify the segment with the biggest absolute approval-rate
    # change so the hero can call it out. Ties broken by loan volume.
    top_segment_key = None
    if by_segment_summary:
        top_segment_key = max(
            by_segment_summary.keys(),
            key=lambda s: (
                abs(by_segment_summary[s]["approval_rate_change"]),
                by_segment_summary[s]["loans"],
            ),
        )

    base_total = sum(base_dist.values()) or 1
    cand_total = sum(cand_dist.values()) or 1
    base_appr_rate = base_dist.get("APPROVED", 0) / base_total
    cand_appr_rate = cand_dist.get("APPROVED", 0) / cand_total

    business_summary: dict[str, Any] = {
        "base_approval_rate": round(base_appr_rate, 4),
        "candidate_approval_rate": round(cand_appr_rate, 4),
        "approval_rate_delta": round(cand_appr_rate - base_appr_rate, 4),
        "loans_newly_denied": loans_newly_denied,
        "loans_newly_approved": loans_newly_approved,
        "net_funded_loans_change": loans_newly_approved - loans_newly_denied,
        "base_funded_amount_usd": round(base_funded_amount, 2),
        "candidate_funded_amount_usd": round(cand_funded_amount, 2),
        "exposure_change_loss_usd": round(exposure_change_loss, 2),
        "exposure_change_gain_usd": round(exposure_change_gain, 2),
        "net_exposure_change_usd": round(
            cand_funded_amount - base_funded_amount, 2
        ),
        "top_changed_segment": top_segment_key,
    }

    # Slice 13: aggregate the offer-modification tracking into the
    # shape the BusinessImpactCard consumes — by raw field, by coarse
    # class, plus the headline "X loans got an offer change without a
    # decision change" so pricing-only BRDs have a visible signal.
    new_by_class: dict[str, int] = {}
    new_by_field: list[dict[str, Any]] = []
    for fld, n in sorted(
        loans_with_new_write_by_field.items(), key=lambda kv: -kv[1]
    ):
        cls = _offer_field_class(fld)
        new_by_class[cls] = new_by_class.get(cls, 0) + n
        new_by_field.append({"field": fld, "field_class": cls, "loans_affected": n})
    dropped_by_field: list[dict[str, Any]] = [
        {
            "field": fld,
            "field_class": _offer_field_class(fld),
            "loans_affected": n,
        }
        for fld, n in sorted(
            loans_with_dropped_write_by_field.items(), key=lambda kv: -kv[1]
        )
    ]
    offer_modifications = {
        "loans_with_any_offer_change": loans_with_any_offer_change,
        "loans_with_offer_change_but_decision_unchanged": (
            loans_with_offer_change_but_decision_unchanged
        ),
        "new_writes_by_field": new_by_field,
        "new_writes_by_class": [
            {"class": k, "loans_affected": v}
            for k, v in sorted(new_by_class.items(), key=lambda kv: -kv[1])
        ],
        "dropped_writes_by_field": dropped_by_field,
        "fields_touched_only_in_candidate": [
            f for f in loans_with_new_write_by_field
            if f not in loans_with_dropped_write_by_field
        ],
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
        # Slice 2: plain-English-friendly summary block.
        "business_summary": business_summary,
        # Slice 13: non-decision offer modifications so pricing/
        # eligibility BRDs are visible even when no loans flip decision.
        "offer_modifications": offer_modifications,
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
