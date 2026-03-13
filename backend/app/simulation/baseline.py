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


def apply_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """Apply current production rules to establish baseline state."""
    result = df.copy()

    # Default: all approved
    result["baseline_decision"] = "APPROVED"

    # Apply rejection rules
    result.loc[result["bureau_score"] < DEFAULT_BASELINE["min_bureau_score"], "baseline_decision"] = "REJECTED"
    result.loc[result["dti_ratio"] > DEFAULT_BASELINE["max_dti_ratio"], "baseline_decision"] = "REJECTED"
    result.loc[result["monthly_income"] < DEFAULT_BASELINE["min_monthly_income"], "baseline_decision"] = "REJECTED"

    # Calculate eligible amount (for approved only)
    result["baseline_eligible_amount"] = 0.0
    approved_mask = result["baseline_decision"] == "APPROVED"
    result.loc[approved_mask, "baseline_eligible_amount"] = np.minimum(
        result.loc[approved_mask, "desired_amount"],
        result.loc[approved_mask, "monthly_income"] * 12 * 0.35
    )

    # Calculate interest rate
    result["baseline_interest_rate"] = DEFAULT_RATE
    for min_score, max_score, rate in RATE_TIERS:
        mask = (result["bureau_score"] >= min_score) & (result["bureau_score"] <= max_score)
        result.loc[mask, "baseline_interest_rate"] = rate
    # Rejected customers get 0 rate
    result.loc[~approved_mask, "baseline_interest_rate"] = 0.0

    return result
