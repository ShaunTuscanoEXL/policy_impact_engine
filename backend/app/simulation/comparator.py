import pandas as pd
import numpy as np

# Probability of Default tiers by bureau score
PD_TIERS = [
    (800, 999, 0.01),   # Excellent credit
    (750, 799, 0.03),   # Good
    (720, 749, 0.05),   # Fair-good
    (700, 719, 0.08),   # Fair
    (650, 699, 0.12),   # Below average
    (0,   649, 0.15),   # Poor
]
LGD = 0.40  # Loss Given Default
LOAN_TENURE_YEARS = 3
ORIGINATION_FEE_RATE = 0.02


def _get_pd(score: float, pd_tiers=None) -> float:
    """Get probability of default for a given bureau score."""
    tiers = pd_tiers if pd_tiers is not None else PD_TIERS
    for lo, hi, pd_val in tiers:
        if lo <= score <= hi:
            return pd_val
    return 0.15


def _calculate_interest_income(amounts: pd.Series, rates: pd.Series, tenure=None) -> float:
    """Total interest income = sum(amount * rate * tenure)."""
    t = tenure if tenure is not None else LOAN_TENURE_YEARS
    return float((amounts * rates * t).sum())


def _calculate_expected_loss(amounts: pd.Series, scores: pd.Series, pd_tiers=None, lgd=None) -> float:
    """Total expected loss = sum(amount * PD(score) * LGD)."""
    effective_lgd = lgd if lgd is not None else LGD
    pds = scores.apply(lambda s: _get_pd(s, pd_tiers=pd_tiers))
    return float((amounts * pds * effective_lgd).sum())


def compare_results(baseline_df: pd.DataFrame, simulated_df: pd.DataFrame, conflict_log: list[dict], config=None):
    """Compare baseline vs simulated to produce impact analysis."""
    from app.simulation.engine import SimulationOutput

    # Extract config values with fallbacks to module-level defaults
    cfg_pd_tiers = [tuple(t) for t in config.get("pd_tiers", [])] if config and config.get("pd_tiers") else PD_TIERS
    cfg_lgd = config.get("lgd", LGD) if config else LGD
    cfg_tenure = config.get("loan_tenure_years", LOAN_TENURE_YEARS) if config else LOAN_TENURE_YEARS
    cfg_orig_rate = config.get("origination_fee_rate", ORIGINATION_FEE_RATE) if config else ORIGINATION_FEE_RATE

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

    # Amount changes
    b_amt = baseline_df["baseline_eligible_amount"]
    s_amt = simulated_df["sim_eligible_amount"]
    amount_delta = s_amt - b_amt

    amount_changes = {
        "increased": int((amount_delta > 0).sum()),
        "decreased": int((amount_delta < 0).sum()),
        "unchanged": int((amount_delta == 0).sum()),
        "avg_delta": round(float(amount_delta.mean(skipna=True) or 0), 2),
        "total_delta": round(float(amount_delta.sum(skipna=True) or 0), 2),
        "total_increase": round(float(amount_delta[amount_delta > 0].sum()), 2),
        "total_decrease": round(float(amount_delta[amount_delta < 0].sum()), 2),
    }

    # Rate changes
    b_rate = baseline_df["baseline_interest_rate"]
    s_rate = simulated_df["sim_interest_rate"]
    rate_delta = s_rate - b_rate
    both_approved = (b_dec == "APPROVED") & (s_dec == "APPROVED")

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
    segment_breakdown = _build_segment_breakdown(baseline_df, simulated_df, affected, tenure=cfg_tenure)

    # Financial impact
    financial_impact = _calculate_financial_impact(
        baseline_df, simulated_df, decision_changes, amount_changes,
        pd_tiers=cfg_pd_tiers, lgd=cfg_lgd, tenure=cfg_tenure, orig_rate=cfg_orig_rate,
    )

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


def _build_segment_breakdown(baseline_df, simulated_df, affected, tenure=None):
    """Break down impact by key segments with financial metrics."""
    effective_tenure = tenure if tenure is not None else LOAN_TENURE_YEARS
    segments = {}
    baseline_df = baseline_df.copy()

    b_amt = baseline_df["baseline_eligible_amount"]
    s_amt = simulated_df["sim_eligible_amount"]
    b_rate = baseline_df["baseline_interest_rate"]
    s_rate = simulated_df["sim_interest_rate"]

    def _segment_stats(mask):
        total_in = int(mask.sum())
        affected_in = int((mask & affected).sum())
        exp_baseline = float(b_amt[mask].sum())
        exp_simulated = float(s_amt[mask].sum())
        ii_baseline = float((b_amt[mask] * b_rate[mask] * effective_tenure).sum())
        ii_simulated = float((s_amt[mask] * s_rate[mask] * effective_tenure).sum())
        return {
            "total": total_in,
            "affected": affected_in,
            "affected_pct": round(affected_in / total_in * 100, 2) if total_in > 0 else 0,
            "exposure_baseline": round(exp_baseline, 2),
            "exposure_simulated": round(exp_simulated, 2),
            "exposure_delta": round(exp_simulated - exp_baseline, 2),
            "interest_income_delta": round(ii_simulated - ii_baseline, 2),
        }

    # Bureau score bands
    bins = [0, 650, 700, 720, 750, 800, 1000]
    labels = ["<650", "650-699", "700-719", "720-749", "750-799", "800+"]
    baseline_df["bureau_score_band"] = pd.cut(baseline_df["bureau_score"], bins=bins, labels=labels, right=False)

    segments["by_bureau_score"] = {}
    for band in labels:
        mask = baseline_df["bureau_score_band"] == band
        segments["by_bureau_score"][band] = _segment_stats(mask)

    # Income brackets
    income_bins = [0, 30000, 50000, 75000, 100000, 150000, 999999]
    income_labels = ["<30K", "30K-50K", "50K-75K", "75K-100K", "100K-150K", "150K+"]
    baseline_df["income_bracket"] = pd.cut(baseline_df["monthly_income"], bins=income_bins, labels=income_labels, right=False)

    segments["by_income"] = {}
    for bracket in income_labels:
        mask = baseline_df["income_bracket"] == bracket
        segments["by_income"][bracket] = _segment_stats(mask)

    # City tier
    if "city_tier" in baseline_df.columns:
        segments["by_city_tier"] = {}
        for tier in baseline_df["city_tier"].unique():
            mask = baseline_df["city_tier"] == tier
            segments["by_city_tier"][str(tier)] = _segment_stats(mask)

    # Employment type
    if "employment_type" in baseline_df.columns:
        segments["by_employment_type"] = {}
        for emp_type in baseline_df["employment_type"].unique():
            mask = baseline_df["employment_type"] == emp_type
            segments["by_employment_type"][str(emp_type)] = _segment_stats(mask)

    return segments


def _calculate_financial_impact(baseline_df, simulated_df, decision_changes, amount_changes,
                                pd_tiers=None, lgd=None, tenure=None, orig_rate=None):
    """Full financial impact: exposure, origination fees, interest income, expected loss, net revenue."""
    effective_orig_rate = orig_rate if orig_rate is not None else ORIGINATION_FEE_RATE

    b_amt = baseline_df["baseline_eligible_amount"]
    s_amt = simulated_df["sim_eligible_amount"]
    b_rate = baseline_df["baseline_interest_rate"]
    s_rate = simulated_df["sim_interest_rate"]
    scores = baseline_df["bureau_score"]

    # --- Exposure ---
    total_baseline_exposure = float(b_amt.sum())
    total_simulated_exposure = float(s_amt.sum())
    exposure_change = total_simulated_exposure - total_baseline_exposure

    # --- Origination fees ---
    origination_baseline = float((b_amt * effective_orig_rate).sum())
    origination_simulated = float((s_amt * effective_orig_rate).sum())

    # --- Interest income ---
    interest_income_baseline = _calculate_interest_income(b_amt, b_rate, tenure=tenure)
    interest_income_simulated = _calculate_interest_income(s_amt, s_rate, tenure=tenure)

    # --- Expected loss ---
    expected_loss_baseline = _calculate_expected_loss(b_amt, scores, pd_tiers=pd_tiers, lgd=lgd)
    expected_loss_simulated = _calculate_expected_loss(s_amt, scores, pd_tiers=pd_tiers, lgd=lgd)

    # --- Net revenue = origination + interest - expected_loss ---
    net_revenue_baseline = origination_baseline + interest_income_baseline - expected_loss_baseline
    net_revenue_simulated = origination_simulated + interest_income_simulated - expected_loss_simulated

    # --- Average rates (across approved only for meaningful comparison) ---
    b_approved = baseline_df["baseline_decision"] == "APPROVED"
    s_approved = simulated_df["sim_decision"] == "APPROVED"
    baseline_avg_rate = float(b_rate[b_approved].mean()) if b_approved.any() else 0.0
    simulated_avg_rate = float(s_rate[s_approved].mean()) if s_approved.any() else 0.0

    return {
        # Exposure
        "total_baseline_exposure": round(total_baseline_exposure, 2),
        "total_simulated_exposure": round(total_simulated_exposure, 2),
        "exposure_change": round(exposure_change, 2),
        "exposure_change_pct": round(exposure_change / total_baseline_exposure * 100, 2) if total_baseline_exposure > 0 else 0,
        # Origination fees
        "origination_fee_baseline": round(origination_baseline, 2),
        "origination_fee_simulated": round(origination_simulated, 2),
        "origination_fee_delta": round(origination_simulated - origination_baseline, 2),
        # Interest income
        "interest_income_baseline": round(interest_income_baseline, 2),
        "interest_income_simulated": round(interest_income_simulated, 2),
        "interest_income_delta": round(interest_income_simulated - interest_income_baseline, 2),
        # Expected loss
        "expected_loss_baseline": round(expected_loss_baseline, 2),
        "expected_loss_simulated": round(expected_loss_simulated, 2),
        "expected_loss_delta": round(expected_loss_simulated - expected_loss_baseline, 2),
        # Net revenue
        "net_revenue_baseline": round(net_revenue_baseline, 2),
        "net_revenue_simulated": round(net_revenue_simulated, 2),
        "net_revenue_delta": round(net_revenue_simulated - net_revenue_baseline, 2),
        # Rates
        "avg_rate_baseline": round(baseline_avg_rate, 4),
        "avg_rate_simulated": round(simulated_avg_rate, 4),
        # Legacy compatibility
        "estimated_revenue_baseline": round(origination_baseline, 2),
        "estimated_revenue_simulated": round(origination_simulated, 2),
        "revenue_impact": round(origination_simulated - origination_baseline, 2),
    }
