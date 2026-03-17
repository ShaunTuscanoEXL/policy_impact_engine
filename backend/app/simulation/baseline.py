import pandas as pd
import numpy as np

# Current production rules (the defaults)
DEFAULT_BASELINE = {
    "min_bureau_score": 700,
    "max_dti_ratio": 0.40,
    "min_monthly_income": 25000,
}

# Interest rate tiers (current)
RATE_TIERS = [
    (800, 999, 0.105),   # Tier 1: 800+
    (750, 799, 0.120),   # Tier 2: 750-799
    (720, 749, 0.135),   # Tier 3: 720-749
    (700, 719, 0.155),   # Tier 4: 700-719
]
DEFAULT_RATE = 0.175  # Below 700


def assign_eligible_amount(row: pd.Series) -> float:
    """Calculate eligible amount for a single approved applicant."""
    return float(min(row["desired_amount"], row["monthly_income"] * 12 * 0.35))


def assign_interest_rate(
    row: pd.Series,
    rate_tiers=None,
    default_rate=None,
) -> float:
    """Calculate interest rate for a single applicant based on bureau score.

    Args:
        row: DataFrame row with a ``bureau_score`` column.
        rate_tiers: Optional list of (min_score, max_score, rate) tuples.
            Falls back to module-level ``RATE_TIERS`` when *None*.
        default_rate: Optional fallback rate when no tier matches.
            Falls back to module-level ``DEFAULT_RATE`` when *None*.
    """
    tiers = rate_tiers if rate_tiers is not None else RATE_TIERS
    fallback = default_rate if default_rate is not None else DEFAULT_RATE
    score = row["bureau_score"]
    for min_score, max_score, rate in tiers:
        if min_score <= score <= max_score:
            return rate
    return fallback


def apply_baseline(df: pd.DataFrame, config=None) -> pd.DataFrame:
    """Apply production rules to establish baseline state.

    Args:
        df: Input DataFrame with applicant data.
        config: Optional dict to override default thresholds. Supported keys:
            - ``min_score``  (default 700)
            - ``max_dti``    (default 0.40)
            - ``min_income`` (default 25000)
            - ``rate_tiers`` (list of [min, max, rate] entries)
            - ``default_rate`` (fallback interest rate)
            When *None*, module-level defaults are used.
    """
    # Resolve thresholds
    if config is not None:
        min_bureau_score = config.get("min_score", DEFAULT_BASELINE["min_bureau_score"])
        max_dti_ratio = config.get("max_dti", DEFAULT_BASELINE["max_dti_ratio"])
        min_monthly_income = config.get("min_income", DEFAULT_BASELINE["min_monthly_income"])
        rate_tiers = config.get("rate_tiers", RATE_TIERS)
        default_rate = config.get("default_rate", DEFAULT_RATE)
    else:
        min_bureau_score = DEFAULT_BASELINE["min_bureau_score"]
        max_dti_ratio = DEFAULT_BASELINE["max_dti_ratio"]
        min_monthly_income = DEFAULT_BASELINE["min_monthly_income"]
        rate_tiers = RATE_TIERS
        default_rate = DEFAULT_RATE

    result = df.copy()

    # Default: all approved
    result["baseline_decision"] = "APPROVED"

    # Apply rejection rules
    result.loc[result["bureau_score"] < min_bureau_score, "baseline_decision"] = "REJECTED"
    result.loc[result["dti_ratio"] > max_dti_ratio, "baseline_decision"] = "REJECTED"
    result.loc[result["monthly_income"] < min_monthly_income, "baseline_decision"] = "REJECTED"

    # Calculate eligible amount (for approved only)
    result["baseline_eligible_amount"] = 0.0
    approved_mask = result["baseline_decision"] == "APPROVED"
    result.loc[approved_mask, "baseline_eligible_amount"] = np.minimum(
        result.loc[approved_mask, "desired_amount"],
        result.loc[approved_mask, "monthly_income"] * 12 * 0.35
    )

    # Calculate interest rate
    result["baseline_interest_rate"] = default_rate
    for min_score, max_score, rate in rate_tiers:
        mask = (result["bureau_score"] >= min_score) & (result["bureau_score"] <= max_score)
        result.loc[mask, "baseline_interest_rate"] = rate
    # Rejected customers get 0 rate
    result.loc[~approved_mask, "baseline_interest_rate"] = 0.0

    return result
