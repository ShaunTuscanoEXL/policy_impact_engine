"""Dashboard service — aggregates cross-cutting metrics for the home page.

The dashboard answers four questions for an operator landing on the app:
  1. **What's live?** — current production versions, decision distributions
  2. **What needs my attention?** — pending merge proposals, failed runs
  3. **What just happened?** — activity feed across all entity types
  4. **How are we trending?** — approval rate over the last N impact runs

Each function below stays cheap (single-digit SELECTs, all aggregates) so
the dashboard load is well under 500ms even with thousands of records.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brd import BrdDocument
from app.models.impact import ImpactRun, ImpactRunStatus
from app.models.live_repo import LiveRuleRepository, LiveRuleVersion
from app.models.loan_record import LoanRecord
from app.models.merge import MergeProposal, MergeProposalStatus
from app.models.rule import Rule, RuleSet
from app.models.test_case import TestCaseSuite


# ── Top-level dashboard payload ─────────────────────────────────────────


async def get_dashboard_stats(db: AsyncSession) -> dict:
    """Enriched dashboard payload — preserves the original three counts
    so existing UI keeps working, plus adds the hero band data."""
    brd_count = await db.scalar(select(func.count(BrdDocument.id))) or 0
    loan_count = await db.scalar(select(func.count(LoanRecord.id))) or 0
    suite_count = await db.scalar(select(func.count(TestCaseSuite.id))) or 0
    rule_count = await db.scalar(select(func.count(Rule.id))) or 0
    rule_set_count = await db.scalar(select(func.count(RuleSet.id))) or 0
    repo_count = await db.scalar(select(func.count(LiveRuleRepository.id))) or 0
    version_count = await db.scalar(select(func.count(LiveRuleVersion.id))) or 0
    impact_run_count = await db.scalar(select(func.count(ImpactRun.id))) or 0

    # Pipeline counters — what fraction of the BRD → impact funnel exists today?
    pipeline = {
        "brds_uploaded": brd_count,
        "rules_extracted": rule_count,
        "rule_sets": rule_set_count,
        "merge_proposals": await db.scalar(
            select(func.count(MergeProposal.id))
        ) or 0,
        "live_versions": version_count,
        "impact_runs": impact_run_count,
        "test_executions": await db.scalar(
            select(func.count(TestCaseSuite.id)).where(
                TestCaseSuite.last_executed_at.is_not(None)
            )
        ) or 0,
    }

    # Pending merge queue — surface the oldest waiting proposal
    pending_q = await db.execute(
        select(MergeProposal)
        .where(MergeProposal.status == MergeProposalStatus.PENDING)
        .order_by(MergeProposal.created_at)
    )
    pending = list(pending_q.scalars())
    pending_summary = {
        "count": len(pending),
        "oldest_age_hours": (
            (datetime.utcnow() - pending[0].created_at).total_seconds() / 3600
            if pending else None
        ),
        "oldest_id": str(pending[0].id) if pending else None,
    }

    # Live repos with their production version + simple health
    repos_q = await db.execute(
        select(LiveRuleRepository).order_by(LiveRuleRepository.created_at)
    )
    repos = list(repos_q.scalars())
    prod_version_map: dict = {}
    if repos:
        prod_ids = [r.production_version_id for r in repos if r.production_version_id]
        if prod_ids:
            rows = await db.execute(
                select(LiveRuleVersion.id, LiveRuleVersion.version_number)
                .where(LiveRuleVersion.id.in_(prod_ids))
            )
            prod_version_map = {row[0]: row[1] for row in rows.all()}
    live_repos = [
        {
            "id": str(r.id),
            "name": r.name,
            "product": r.product,
            "jurisdiction": r.jurisdiction,
            "current_version": r.current_version,
            "production_version_number": prod_version_map.get(r.production_version_id),
            "has_unpromoted_candidate": (
                r.production_version_id is not None
                and prod_version_map.get(r.production_version_id) is not None
                and prod_version_map[r.production_version_id] < r.current_version
            ),
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in repos
    ]

    # Latest impact run summary
    last_impact_q = await db.execute(
        select(ImpactRun)
        .where(ImpactRun.status == ImpactRunStatus.COMPLETED)
        .order_by(desc(ImpactRun.completed_at))
        .limit(1)
    )
    last_impact = last_impact_q.scalar_one_or_none()
    last_impact_summary = None
    if last_impact and last_impact.summary:
        flips = last_impact.summary.get("decision_flips", {}) or {}
        total_flips = sum(
            v for k, v in flips.items()
            if isinstance(v, int) and ("_to_" in k)
        )
        total_loans = last_impact.summary.get("total_loans", 0)
        last_impact_summary = {
            "id": str(last_impact.id),
            "repository_id": str(last_impact.repository_id),
            "completed_at": (
                last_impact.completed_at.isoformat()
                if last_impact.completed_at else None
            ),
            "total_loans": total_loans,
            "total_flips": total_flips,
            "flip_rate": (total_flips / total_loans) if total_loans else 0,
            "decision_distribution": last_impact.summary.get("decision_distribution"),
            "by_subsystem_top": _top_n_by_metric(
                last_impact.summary.get("by_subsystem", {}) or {},
                "flips_caused", n=3,
            ),
        }

    # Latest test suite execution summary (across all suites)
    last_exec_q = await db.execute(
        select(TestCaseSuite)
        .where(TestCaseSuite.last_executed_at.is_not(None))
        .order_by(desc(TestCaseSuite.last_executed_at))
        .limit(1)
    )
    last_exec = last_exec_q.scalar_one_or_none()
    last_exec_summary = None
    if last_exec and last_exec.last_execution_report:
        rep = last_exec.last_execution_report
        summary = rep.get("summary", {}) or {}
        matches = int(summary.get("matches_expected") or 0)
        deviates = int(summary.get("deviates_from_expected") or 0)
        total = matches + deviates
        last_exec_summary = {
            "suite_id": str(last_exec.id),
            "executed_at": (
                last_exec.last_executed_at.isoformat()
                if last_exec.last_executed_at else None
            ),
            "total_assertions": total,
            "passing": matches,
            "failing": deviates,
            "pass_rate": (matches / total) if total else 0,
            "version_number": rep.get("version_number"),
        }

    return {
        # Original three (kept for backward compat)
        "total_brds": brd_count,
        "total_loan_records": loan_count,
        "total_test_suites": suite_count,
        # New: enrichment
        "total_repositories": repo_count,
        "total_versions": version_count,
        "total_impact_runs": impact_run_count,
        "pipeline": pipeline,
        "pending_merge_queue": pending_summary,
        "live_repos": live_repos,
        "last_impact_run": last_impact_summary,
        "last_suite_execution": last_exec_summary,
    }


# ── Activity feed ───────────────────────────────────────────────────────


async def get_activity_feed(db: AsyncSession, *, limit: int = 20) -> list[dict]:
    """Recent events across BRDs, merge proposals, live versions, impact
    runs, and suite executions — sorted newest-first.

    Implementation: query each entity for up to ``limit`` recent rows,
    project to a uniform ``{type, ts, title, subtitle, href, accent}``
    record, then sort the union.
    """
    events: list[dict] = []

    # BRD uploads
    brds_q = await db.execute(
        select(BrdDocument).order_by(desc(BrdDocument.created_at)).limit(limit)
    )
    for b in brds_q.scalars():
        events.append({
            "type": "brd_uploaded",
            "ts": b.created_at.isoformat() if b.created_at else None,
            "title": f"BRD uploaded: {b.filename}",
            "subtitle": b.file_type or "",
            "href": f"/brds/{b.id}",
            "accent": "blue",
        })

    # Live versions created (covers merges + python imports)
    versions_q = await db.execute(
        select(LiveRuleVersion, LiveRuleRepository)
        .join(LiveRuleRepository, LiveRuleVersion.repository_id == LiveRuleRepository.id)
        .where(LiveRuleVersion.version_number > 0)
        .order_by(desc(LiveRuleVersion.created_at))
        .limit(limit)
    )
    for v, r in versions_q.all():
        events.append({
            "type": "version_created",
            "ts": v.created_at.isoformat() if v.created_at else None,
            "title": f"{r.name} → v{v.version_number}",
            "subtitle": (v.summary or "").split("—")[0].strip() or "rule version applied",
            "href": f"/live-repo/{r.id}",
            "accent": "amber",
        })

    # Production promotions (use repo.production_promoted_at)
    promo_q = await db.execute(
        select(LiveRuleRepository)
        .where(LiveRuleRepository.production_promoted_at.is_not(None))
        .order_by(desc(LiveRuleRepository.production_promoted_at))
        .limit(limit)
    )
    promo_repos = list(promo_q.scalars())
    promo_prod_ids = [r.production_version_id for r in promo_repos if r.production_version_id]
    promo_v_map: dict = {}
    if promo_prod_ids:
        rows = await db.execute(
            select(LiveRuleVersion.id, LiveRuleVersion.version_number)
            .where(LiveRuleVersion.id.in_(promo_prod_ids))
        )
        promo_v_map = {row[0]: row[1] for row in rows.all()}
    for r in promo_repos:
        ver_n = promo_v_map.get(r.production_version_id)
        if ver_n is None:
            continue
        events.append({
            "type": "version_promoted",
            "ts": r.production_promoted_at.isoformat(),
            "title": f"{r.name} → v{ver_n} promoted to production",
            "subtitle": f"by {r.production_promoted_by or 'system'}",
            "href": f"/live-repo/{r.id}",
            "accent": "emerald",
        })

    # Merge proposals created
    proposals_q = await db.execute(
        select(MergeProposal)
        .order_by(desc(MergeProposal.created_at))
        .limit(limit)
    )
    for p in proposals_q.scalars():
        events.append({
            "type": "merge_proposal",
            "ts": p.created_at.isoformat() if p.created_at else None,
            "title": (
                f"Merge proposal {'applied' if p.status == MergeProposalStatus.APPLIED else 'created'}"
            ),
            "subtitle": (p.summary or "")[:120],
            "href": f"/merge-workbench/{p.id}",
            "accent": "violet",
        })

    # Impact runs completed
    impact_q = await db.execute(
        select(ImpactRun)
        .where(ImpactRun.status == ImpactRunStatus.COMPLETED)
        .order_by(desc(ImpactRun.completed_at))
        .limit(limit)
    )
    for ir in impact_q.scalars():
        flip_rate = 0.0
        if ir.summary:
            flips = ir.summary.get("decision_flips", {}) or {}
            total_flips = sum(
                v for k, v in flips.items()
                if isinstance(v, int) and "_to_" in k
            )
            total_loans = ir.summary.get("total_loans", 0)
            flip_rate = (total_flips / total_loans) if total_loans else 0
        events.append({
            "type": "impact_run",
            "ts": ir.completed_at.isoformat() if ir.completed_at else None,
            "title": f"Impact run completed — {flip_rate * 100:.1f}% flips",
            "subtitle": "",
            "href": f"/impact-runs/{ir.id}",
            "accent": "rose",
        })

    # Suite executions
    exec_q = await db.execute(
        select(TestCaseSuite)
        .where(TestCaseSuite.last_executed_at.is_not(None))
        .order_by(desc(TestCaseSuite.last_executed_at))
        .limit(limit)
    )
    for s in exec_q.scalars():
        rep = s.last_execution_report or {}
        summary = rep.get("summary", {}) or {}
        matches = int(summary.get("matches_expected") or 0)
        deviates = int(summary.get("deviates_from_expected") or 0)
        total = matches + deviates
        rate = (matches / total * 100) if total else 0
        events.append({
            "type": "suite_executed",
            "ts": s.last_executed_at.isoformat() if s.last_executed_at else None,
            "title": f"Test suite executed — {rate:.0f}% pass rate",
            "subtitle": f"{matches} / {total} loans matched expected outcome",
            "href": f"/test-suites/{s.id}",
            "accent": "fuchsia",
        })

    # Sort by timestamp desc, drop nulls last
    events.sort(key=lambda e: e["ts"] or "", reverse=True)
    return events[:limit]


# ── Trends ──────────────────────────────────────────────────────────────


async def get_dashboard_trends(db: AsyncSession, *, limit: int = 10) -> dict:
    """Time-series-ish data for dashboard charts.

    Currently returns:
      - approval_rate_history: last N impact runs' candidate approval rate
      - rule_count_history:    rule count per live version (HEAD movement)
    """
    # Approval rate trend (per impact run)
    runs_q = await db.execute(
        select(ImpactRun)
        .where(ImpactRun.status == ImpactRunStatus.COMPLETED)
        .order_by(desc(ImpactRun.completed_at))
        .limit(limit)
    )
    runs = list(runs_q.scalars())
    runs.reverse()  # oldest → newest for chart
    approval_history = []
    for ir in runs:
        if not ir.summary:
            continue
        dist = ir.summary.get("decision_distribution", {}) or {}
        cand = dist.get("candidate", {}) or {}
        total = sum(int(v) for v in cand.values()) or 1
        approved = int(cand.get("APPROVED", 0))
        approval_history.append({
            "completed_at": (
                ir.completed_at.isoformat() if ir.completed_at else None
            ),
            "approval_rate": approved / total,
            "total_loans": total,
            "run_id": str(ir.id),
        })

    # Rule count per version (across all repos, ordered by version creation)
    versions_q = await db.execute(
        select(LiveRuleVersion, LiveRuleRepository)
        .join(LiveRuleRepository, LiveRuleVersion.repository_id == LiveRuleRepository.id)
        .order_by(desc(LiveRuleVersion.created_at))
        .limit(limit * 2)
    )
    rule_counts = []
    for v, r in versions_q.all():
        rule_counts.append({
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "repository": r.name,
            "version_number": v.version_number,
            "rule_count": len(v.rule_snapshot or []),
        })
    rule_counts.reverse()  # oldest first

    return {
        "approval_rate_history": approval_history,
        "rule_count_history": rule_counts[:limit],
    }


# ── helpers ─────────────────────────────────────────────────────────────


def _top_n_by_metric(d: dict, metric: str, *, n: int = 3) -> list[dict]:
    """Sort a {key: {metric: value, ...}} dict by `metric` desc and
    return the top N as a list of {key, value} for chart consumption."""
    pairs = []
    for key, payload in (d or {}).items():
        if isinstance(payload, dict) and isinstance(payload.get(metric), (int, float)):
            pairs.append((key, payload[metric]))
    pairs.sort(key=lambda kv: kv[1], reverse=True)
    return [{"key": k, "value": v} for k, v in pairs[:n]]
