"""drift_service — Slice 10 production drift watch.

Compares the production version's decision distribution against:
  (a) what the most-recent impact run that produced it PREDICTED, and
  (b) the live loan corpus as of right now.

Returns a structured "drift report" that the UI binds to a panel on
the live-repo page: "Approval rate predicted 71.4%, observed 68.9%
(−2.5 pts) — drift is concentrated in NEAR_PRIME (−6.1 pts)."

Designed to run synchronously on-demand. A future slice can wrap this
in a daily Celery beat job + persist a `production_drift_snapshots`
table for trend charts; the API contract here is identical so the
frontend won't change when that happens.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.impact import ImpactRun, ImpactRunStatus
from app.models.live_repo import LiveRuleRepository, LiveRuleVersion
from app.models.loan_record import LoanRecord
from app.runtime.rule_engine import evaluate_snapshot
from app.services.impact_service import _empty_dist, _segment_for, _desired_amount

logger = logging.getLogger(__name__)


def _normalize_dist(dist: dict[str, int]) -> dict[str, float]:
    """Convert absolute counts to fractions of total (0–1)."""
    total = sum(dist.values()) or 1
    return {k: v / total for k, v in dist.items()}


def _diff_distributions(
    predicted: dict[str, int],
    observed: dict[str, int],
) -> dict[str, dict[str, float]]:
    """For each decision label, return predicted_pct / observed_pct /
    delta_pct so the UI can render a side-by-side comparison."""
    pred_pct = _normalize_dist(predicted)
    obs_pct = _normalize_dist(observed)
    keys = set(predicted) | set(observed) | {"APPROVED", "FLAGGED", "REJECTED"}
    out: dict[str, dict[str, float]] = {}
    for k in sorted(keys):
        p = pred_pct.get(k, 0.0)
        o = obs_pct.get(k, 0.0)
        out[k] = {
            "predicted_pct": round(p, 4),
            "observed_pct": round(o, 4),
            "delta_pct": round(o - p, 4),
            "predicted_count": int(predicted.get(k, 0)),
            "observed_count": int(observed.get(k, 0)),
        }
    return out


async def compute_drift_for_repo(
    db: AsyncSession,
    *,
    repository_id: uuid.UUID,
    loan_limit: int | None = None,
) -> dict[str, Any]:
    """Run the drift comparison for a repo's current production version.

    Returns shape:
        {
          "repository_id": "...",
          "production_version_id": "...",
          "production_version_number": 3,
          "computed_at": "2026-04-30T18:42:00",
          "predicted_source": {
            "impact_run_id": "...",
            "completed_at": "...",
            "loan_count": 100000,
          } | None,
          "observed": {
            "loan_count": 100000,
            "decision_distribution": {"APPROVED": 68900, ...},
            "by_segment": {"PRIME": {...}, ...},
          },
          "drift": {
            "decision_distribution": {
              "APPROVED": {"predicted_pct": 0.71, "observed_pct": 0.68, "delta_pct": -0.03, ...},
              ...
            },
            "by_segment": {"PRIME": {"approval_rate_delta": ..., ...}, ...},
            "max_abs_delta_pct": 0.061,
            "top_drifting_segment": "NEAR_PRIME",
          },
          "warnings": [],
        }
    """
    repo = await db.get(LiveRuleRepository, repository_id)
    if repo is None:
        raise ValueError(f"Repository {repository_id} not found")
    if repo.production_version_id is None:
        raise ValueError(
            f"Repository {repository_id} has no production version yet — "
            "promote a version first."
        )

    version = await db.get(LiveRuleVersion, repo.production_version_id)
    if version is None:
        raise ValueError(
            f"Production version {repo.production_version_id} not found "
            "(stale pointer?)"
        )
    snapshot: list[dict] = list(version.rule_snapshot or [])

    # Find the impact run that produced this version (or, failing that,
    # the most recent COMPLETED run for this repo using version as
    # candidate). Its summary.decision_distribution.candidate is the
    # PREDICTED distribution.
    pred_run_q = await db.execute(
        select(ImpactRun)
        .where(
            ImpactRun.repository_id == repository_id,
            ImpactRun.candidate_version_id == version.id,
            ImpactRun.status == ImpactRunStatus.COMPLETED,
        )
        .order_by(ImpactRun.created_at.desc())
        .limit(1)
    )
    predicted_run = pred_run_q.scalar_one_or_none()
    predicted_dist: dict[str, int] = _empty_dist()
    predicted_source: dict[str, Any] | None = None
    if predicted_run is not None and predicted_run.summary:
        candidate_dist = (
            predicted_run.summary.get("decision_distribution", {}) or {}
        ).get("candidate", {}) or {}
        if candidate_dist:
            predicted_dist = {**_empty_dist(), **{k: int(v) for k, v in candidate_dist.items()}}
            predicted_source = {
                "impact_run_id": str(predicted_run.id),
                "completed_at": (
                    predicted_run.completed_at.isoformat()
                    if predicted_run.completed_at
                    else None
                ),
                "loan_count": predicted_run.summary.get("total_loans"),
            }

    # Observed: re-evaluate snapshot vs the current loan corpus.
    stmt = select(LoanRecord)
    if loan_limit is not None:
        stmt = stmt.limit(loan_limit)
    loans = list((await db.execute(stmt)).scalars())

    observed_dist = _empty_dist()
    by_segment_obs: dict[str, dict[str, int]] = {}
    by_segment_funded: dict[str, float] = {}
    for loan in loans:
        result = evaluate_snapshot(
            snapshot,
            loan.request_payload or {},
            loan_application_id=loan.loan_application_id,
        )
        observed_dist[result.decision] = observed_dist.get(result.decision, 0) + 1
        seg = _segment_for(loan)
        by_segment_obs.setdefault(seg, _empty_dist())
        by_segment_obs[seg][result.decision] = (
            by_segment_obs[seg].get(result.decision, 0) + 1
        )
        if result.decision == "APPROVED":
            by_segment_funded[seg] = by_segment_funded.get(seg, 0.0) + _desired_amount(loan)

    # Per-segment observed approval rate + delta vs the predicted run's
    # by_segment block (when present).
    by_segment_drift: dict[str, dict[str, float]] = {}
    pred_segments = (
        (predicted_run.summary.get("by_segment", {}) if predicted_run and predicted_run.summary else {})
        or {}
    )
    for seg, dist in by_segment_obs.items():
        seg_total = sum(dist.values()) or 1
        obs_appr = dist.get("APPROVED", 0) / seg_total
        pred_seg = pred_segments.get(seg, {}) or {}
        pred_appr = float(pred_seg.get("candidate_approval_rate") or 0.0)
        by_segment_drift[seg] = {
            "loans": seg_total,
            "predicted_approval_rate": round(pred_appr, 4),
            "observed_approval_rate": round(obs_appr, 4),
            "approval_rate_delta": round(obs_appr - pred_appr, 4) if pred_appr else 0.0,
            "observed_funded_amount_usd": round(by_segment_funded.get(seg, 0.0), 2),
        }

    drift_dist = _diff_distributions(predicted_dist, observed_dist)
    max_abs = 0.0
    for k, info in drift_dist.items():
        max_abs = max(max_abs, abs(info["delta_pct"]))
    top_seg: str | None = None
    if by_segment_drift:
        top_seg = max(
            by_segment_drift.keys(),
            key=lambda s: abs(by_segment_drift[s]["approval_rate_delta"]),
        )

    warnings: list[str] = []
    if predicted_source is None:
        warnings.append(
            "No impact run was found for the current production version — "
            "predicted distribution shown as zeros. Run impact analysis to baseline."
        )
    if not loans:
        warnings.append("No loan records in corpus — observed distribution is empty.")

    return {
        "repository_id": str(repository_id),
        "production_version_id": str(version.id),
        "production_version_number": version.version_number,
        "computed_at": datetime.utcnow().isoformat(),
        "predicted_source": predicted_source,
        "observed": {
            "loan_count": len(loans),
            "decision_distribution": observed_dist,
            "by_segment": {
                seg: {
                    **dist,
                    "approval_rate": round(
                        dist.get("APPROVED", 0) / (sum(dist.values()) or 1), 4
                    ),
                }
                for seg, dist in by_segment_obs.items()
            },
        },
        "drift": {
            "decision_distribution": drift_dist,
            "by_segment": by_segment_drift,
            "max_abs_delta_pct": round(max_abs, 4),
            "top_drifting_segment": top_seg,
        },
        "warnings": warnings,
    }
