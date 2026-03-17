import pandas as pd
from app.simulation.baseline import apply_baseline


def _make_df():
    return pd.DataFrame({
        "bureau_score": [750, 680, 600],
        "monthly_income": [50000, 30000, 20000],
        "desired_amount": [500000, 200000, 100000],
        "dti_ratio": [0.3, 0.35, 0.5],
    })


def test_default_config_unchanged():
    df = _make_df()
    result = apply_baseline(df)
    assert result.loc[0, "baseline_decision"] == "APPROVED"
    assert result.loc[1, "baseline_decision"] == "REJECTED"
    assert result.loc[2, "baseline_decision"] == "REJECTED"


def test_custom_lower_score_threshold():
    df = _make_df()
    config = {"min_score": 650, "max_dti": 0.40, "min_income": 25000}
    result = apply_baseline(df, config=config)
    assert result.loc[0, "baseline_decision"] == "APPROVED"
    assert result.loc[1, "baseline_decision"] == "APPROVED"


def test_custom_rate_tiers():
    df = _make_df()
    config = {
        "min_score": 600,
        "max_dti": 0.60,
        "min_income": 15000,
        "rate_tiers": [[700, 999, 0.08], [600, 699, 0.14]],
        "default_rate": 0.20,
    }
    result = apply_baseline(df, config=config)
    assert result.loc[0, "baseline_interest_rate"] == 0.08
    assert result.loc[1, "baseline_interest_rate"] == 0.14
    assert result.loc[2, "baseline_interest_rate"] == 0.14
