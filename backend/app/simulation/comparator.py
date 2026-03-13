import pandas as pd
import numpy as np


def compare_results(baseline_df: pd.DataFrame, simulated_df: pd.DataFrame, conflict_log: list[dict]):
    """Compare baseline vs simulated to produce impact analysis."""
    from app.simulation.engine import SimulationOutput

    total = len(baseline_df)

    # Decision changes
    b_dec = baseline_df["baseline_decision"]
    s_dec = simulated_df["sim_decision"]

    approved_to_rejected = int(((b_dec == "APPROVED") & (s_dec == "REJECTED")).sum())
    rejected_to_approved = int(((b_dec == "REJECTED") & (s_dec == "APPROVED")).sum())
    unchanged = int((b_dec == s_dec).sum())

    decision_changes = {
        "approved_to_rejected": approved_to_rejected,
        "rejected_to_approved": rejected_to_approved,
        "unchanged": unchanged,
        "baseline_approved": int((b_dec == "APPROVED").sum()),
        "baseline_rejected": int((b_dec == "REJECTED").sum()),
        "simulated_approved": int((s_dec == "APPROVED").sum()),
        "simulated_rejected": int((s_dec == "REJECTED").sum()),
    }

    # Amount changes (only for customers approved in both states)
    both_approved = (b_dec == "APPROVED") & (s_dec == "APPROVED")
    b_amt = baseline_df["baseline_eligible_amount"]
    s_amt = simulated_df["sim_eligible_amount"]
    amount_delta = s_amt - b_amt

    amount_changes = {
        "increased": int((amount_delta > 0).sum()),
        "decreased": int((amount_delta < 0).sum()),
        "unchanged": int((amount_delta == 0).sum()),
        "avg_delta": round(float(amount_delta.mean(skipna=True) or 0), 2),
        "total_delta": round(float(amount_delta.sum(skipna=True) or 0), 2),
    }

    # Rate changes
    b_rate = baseline_df["baseline_interest_rate"]
    s_rate = simulated_df["sim_interest_rate"]
    rate_delta = s_rate - b_rate

    rate_changes = {
        "rate_increased": int((rate_delta > 0).sum()),
        "rate_decreased": int((rate_delta < 0).sum()),
        "avg_rate_delta": round(float(rate_delta[both_approved].mean()) if both_approved.any() else 0, 4),
    }

    # Affected customers
    decision_changed = b_dec != s_dec
    amount_changed = amount_delta.abs() > 0.01
    rate_changed = rate_delta.abs() > 0.0001
    affected = decision_changed | amount_changed | rate_changed
    affected_count = int(affected.sum())

    # Segment breakdown
    segment_breakdown = _build_segment_breakdown(baseline_df, simulated_df, affected)

    # Financial impact
    financial_impact = _calculate_financial_impact(baseline_df, simulated_df, decision_changes, amount_changes)

    return SimulationOutput(
        total_customers=total,
        affected_customers=affected_count,
        affected_percentage=round(affected_count / total * 100, 2) if total > 0 else 0,
        decision_changes=decision_changes,
        amount_changes=amount_changes | rate_changes,
        segment_breakdown=segment_breakdown,
        financial_impact=financial_impact,
        conflict_log=conflict_log,
        baseline_df=baseline_df,
        simulated_df=simulated_df,
    )


def _build_segment_breakdown(baseline_df, simulated_df, affected):
    """Break down impact by key segments."""
    segments = {}

    # Bureau score bands
    bins = [0, 650, 700, 720, 750, 800, 1000]
    labels = ["<650", "650-699", "700-719", "720-749", "750-799", "800+"]
    baseline_df = baseline_df.copy()
    baseline_df["bureau_score_band"] = pd.cut(baseline_df["bureau_score"], bins=bins, labels=labels, right=False)

    segments["by_bureau_score"] = {}
    for band in labels:
        mask = baseline_df["bureau_score_band"] == band
        total_in_band = int(mask.sum())
        affected_in_band = int((mask & affected).sum())
        segments["by_bureau_score"][band] = {
            "total": total_in_band,
            "affected": affected_in_band,
            "affected_pct": round(affected_in_band / total_in_band * 100, 2) if total_in_band > 0 else 0,
        }

    # Income brackets
    income_bins = [0, 30000, 50000, 75000, 100000, 150000, 999999]
    income_labels = ["<30K", "30K-50K", "50K-75K", "75K-100K", "100K-150K", "150K+"]
    baseline_df["income_bracket"] = pd.cut(baseline_df["monthly_income"], bins=income_bins, labels=income_labels, right=False)

    segments["by_income"] = {}
    for bracket in income_labels:
        mask = baseline_df["income_bracket"] == bracket
        total_in = int(mask.sum())
        affected_in = int((mask & affected).sum())
        segments["by_income"][bracket] = {
            "total": total_in,
            "affected": affected_in,
            "affected_pct": round(affected_in / total_in * 100, 2) if total_in > 0 else 0,
        }

    # City tier
    if "city_tier" in baseline_df.columns:
        segments["by_city_tier"] = {}
        for tier in baseline_df["city_tier"].unique():
            mask = baseline_df["city_tier"] == tier
            total_in = int(mask.sum())
            affected_in = int((mask & affected).sum())
            segments["by_city_tier"][str(tier)] = {
                "total": total_in,
                "affected": affected_in,
                "affected_pct": round(affected_in / total_in * 100, 2) if total_in > 0 else 0,
            }

    # Employment type
    if "employment_type" in baseline_df.columns:
        segments["by_employment_type"] = {}
        for emp_type in baseline_df["employment_type"].unique():
            mask = baseline_df["employment_type"] == emp_type
            total_in = int(mask.sum())
            affected_in = int((mask & affected).sum())
            segments["by_employment_type"][str(emp_type)] = {
                "total": total_in,
                "affected": affected_in,
                "affected_pct": round(affected_in / total_in * 100, 2) if total_in > 0 else 0,
            }

    return segments


def _calculate_financial_impact(baseline_df, simulated_df, decision_changes, amount_changes):
    """Estimate financial impact of the rule changes."""
    b_amt = baseline_df["baseline_eligible_amount"]
    s_amt = simulated_df["sim_eligible_amount"]

    total_baseline_exposure = float(b_amt.sum())
    total_simulated_exposure = float(s_amt.sum())

    # Revenue proxy: assume average origination fee of 2%
    origination_rate = 0.02
    baseline_revenue = total_baseline_exposure * origination_rate
    simulated_revenue = total_simulated_exposure * origination_rate

    # Expected loss proxy: assume average loss rate varies by approval volume
    baseline_avg_rate = float(baseline_df["baseline_interest_rate"].mean())
    simulated_avg_rate = float(simulated_df["sim_interest_rate"].mean())

    return {
        "total_baseline_exposure": round(total_baseline_exposure, 2),
        "total_simulated_exposure": round(total_simulated_exposure, 2),
        "exposure_change": round(total_simulated_exposure - total_baseline_exposure, 2),
        "exposure_change_pct": round((total_simulated_exposure - total_baseline_exposure) / total_baseline_exposure * 100, 2) if total_baseline_exposure > 0 else 0,
        "estimated_revenue_baseline": round(baseline_revenue, 2),
        "estimated_revenue_simulated": round(simulated_revenue, 2),
        "revenue_impact": round(simulated_revenue - baseline_revenue, 2),
        "avg_rate_baseline": round(baseline_avg_rate, 4),
        "avg_rate_simulated": round(simulated_avg_rate, 4),
    }
