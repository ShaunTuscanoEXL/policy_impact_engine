"""
Generate a realistic 500-row loan application dataset for the Policy Impact Engine.

This script produces a CSV file with correlated customer demographics, bureau data,
banking data, loan request details, calculated fields, and baseline decision outcomes.

Usage:
    python generate_sample_data.py

Output:
    backend/data/sample_datasets/loan_applications_500.csv
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(42)
N = 500


def generate_dataset() -> pd.DataFrame:
    """Generate a 500-row loan application dataset with realistic distributions."""

    # ── Customer Demographics ──────────────────────────────────────────────

    customer_id = [f"CUST-{i:06d}" for i in range(1, N + 1)]

    # Age: normal distribution centered at 35, std 8, clipped to 22-60
    age = np.clip(np.random.normal(35, 8, N), 22, 60).astype(int)

    # Employment type: SALARIED 70%, SELF_EMPLOYED 20%, PROFESSIONAL 10%
    employment_type = np.random.choice(
        ["SALARIED", "SELF_EMPLOYED", "PROFESSIONAL"],
        size=N,
        p=[0.70, 0.20, 0.10],
    )

    # Employer type: only for SALARIED; PRIVATE 60%, GOVERNMENT 15%, MNC 25%
    employer_type = []
    for et in employment_type:
        if et == "SALARIED":
            employer_type.append(
                np.random.choice(
                    ["PRIVATE", "GOVERNMENT", "MNC"], p=[0.60, 0.15, 0.25]
                )
            )
        else:
            employer_type.append("N/A")
    employer_type = np.array(employer_type)

    # Monthly income: log-normal with median ~55000, clipped 25000-200000
    log_median = np.log(55000)
    log_sigma = 0.45
    monthly_income = np.clip(
        np.random.lognormal(log_median, log_sigma, N), 25000, 200000
    ).astype(int)

    # Employment tenure: correlated with age (older → longer tenure)
    base_tenure = (age - 22) * 8 + np.random.normal(0, 12, N)
    employment_tenure_months = np.clip(base_tenure, 6, 240).astype(int)

    # Residence type: RENTED 45%, OWNED 40%, COMPANY 15%
    residence_type = np.random.choice(
        ["RENTED", "OWNED", "COMPANY"], size=N, p=[0.45, 0.40, 0.15]
    )

    # City tier
    city_tier = np.random.choice(
        ["TIER_1", "TIER_2", "TIER_3"], size=N, p=[0.40, 0.35, 0.25]
    )

    # Marital status
    marital_status = np.random.choice(
        ["MARRIED", "SINGLE", "DIVORCED"], size=N, p=[0.55, 0.35, 0.10]
    )

    # Dependents: 0-4
    dependents = np.random.choice([0, 1, 2, 3, 4], size=N, p=[0.25, 0.30, 0.25, 0.15, 0.05])

    # ── Bureau Data ────────────────────────────────────────────────────────

    # Bureau score: normal centered at 735, std 55, clipped 550-850
    # Centered at 735 so ~60-70% have score >= 700 for target approval rate
    bureau_score = np.clip(np.random.normal(735, 55, N), 550, 850).astype(int)

    # Active loans: 0-8 (Poisson-ish)
    active_loans = np.clip(np.random.poisson(1.5, N), 0, 8).astype(int)

    # Closed loans: 0-12
    closed_loans = np.clip(np.random.poisson(2.5, N), 0, 12).astype(int)

    # Unsecured loans: 0-4, subset of active
    unsecured_loans = np.minimum(
        np.clip(np.random.poisson(0.8, N), 0, 4), active_loans
    ).astype(int)

    # Credit utilization ratio: 0.05-0.95
    credit_utilization_ratio = np.clip(
        np.random.beta(2, 5, N) * 0.90 + 0.05, 0.05, 0.95
    )

    # Max DPD last 12m: 0 (80%), 1-30 (15%), 31-90 (5%)
    dpd_category = np.random.choice([0, 1, 2], size=N, p=[0.80, 0.15, 0.05])
    max_dpd_last_12m = np.where(
        dpd_category == 0,
        0,
        np.where(
            dpd_category == 1,
            np.random.randint(1, 31, N),
            np.random.randint(31, 91, N),
        ),
    )

    # Inquiries last 3 months: 0-6 — ensure ~10-15% have > 3
    inquiries_last_3m = np.clip(np.random.poisson(1.5, N), 0, 6).astype(int)
    # Boost some to >3 to hit the 10-15% target
    boost_mask = np.random.random(N) < 0.08  # add ~8% extra high-inquiry cases
    inquiries_last_3m[boost_mask] = np.random.randint(4, 7, boost_mask.sum())

    # Oldest trade line months: 6-120
    oldest_trade_line_months = np.clip(
        np.random.normal(48, 24, N), 6, 120
    ).astype(int)

    # Credit cards active: 0-4
    credit_cards_active = np.clip(np.random.poisson(1.2, N), 0, 4).astype(int)

    # ── Banking Data ───────────────────────────────────────────────────────

    # Monthly salary credit: within 5% of monthly_income
    salary_variation = np.random.uniform(-0.05, 0.05, N)
    monthly_salary_credit = (monthly_income * (1 + salary_variation)).astype(int)

    # Salary credit consistency: 0.60-0.99
    salary_credit_consistency_6m = np.clip(
        np.random.beta(8, 2, N) * 0.39 + 0.60, 0.60, 0.99
    )

    # Average monthly balance: correlated with income, 10000-500000
    balance_ratio = np.random.lognormal(0, 0.4, N)
    average_monthly_balance_6m = np.clip(
        monthly_income * balance_ratio * 0.6, 10000, 500000
    ).astype(int)

    # Cheque bounces: 0 (90%), 1-3 (10%)
    has_bounce = np.random.random(N) < 0.10
    cheque_bounces_6m = np.where(has_bounce, np.random.randint(1, 4, N), 0)

    # Cash deposits: 0-20
    cash_deposits_6m = np.clip(np.random.poisson(3, N), 0, 20).astype(int)

    # Banking stability index: 0.40-0.95
    banking_stability_index = np.clip(
        0.50
        + salary_credit_consistency_6m * 0.3
        + (average_monthly_balance_6m / monthly_income) * 0.05
        - cheque_bounces_6m * 0.10
        + np.random.normal(0, 0.05, N),
        0.40,
        0.95,
    )

    # EMI obligation: correlated with active_loans, 0-40000
    emi_per_loan = np.random.uniform(3000, 12000, N)
    emi_obligation_amount = np.clip(
        (active_loans * emi_per_loan).astype(int), 0, 40000
    )

    # ── Loan Request ───────────────────────────────────────────────────────

    desired_amount = np.clip(
        np.random.lognormal(np.log(150000), 0.5, N), 50000, 500000
    ).astype(int)

    loan_type = np.full(N, "PERSONAL")

    # ── Calculated Fields ──────────────────────────────────────────────────

    dti_ratio_raw = emi_obligation_amount / monthly_income

    # Adjust DTI so ~15-20% fall in 0.35-0.40 band
    # First, compute raw distribution and tweak EMI for some applicants
    # to land in the target zone
    target_dti_band_mask = np.random.random(N) < 0.18
    target_dti_band_mask &= dti_ratio_raw < 0.35  # only adjust those below
    emi_obligation_amount[target_dti_band_mask] = (
        monthly_income[target_dti_band_mask]
        * np.random.uniform(0.35, 0.40, target_dti_band_mask.sum())
    ).astype(int)
    emi_obligation_amount = np.clip(emi_obligation_amount, 0, 40000)

    # Recalculate DTI
    dti_ratio = np.round(emi_obligation_amount / monthly_income, 4)
    dti_ratio = np.clip(dti_ratio, 0.0, 0.55)

    net_disposable_income = (monthly_income - emi_obligation_amount).astype(int)

    # G5 score: composite correlated with banking stability and income
    income_norm = (monthly_income - 25000) / (200000 - 25000)
    g5_score = np.clip(
        0.40
        + banking_stability_index * 0.35
        + income_norm * 0.20
        + np.random.normal(0, 0.04, N),
        0.40,
        0.95,
    )

    # G6 score: composite correlated with bureau score and credit behavior
    bureau_norm = (bureau_score - 550) / (850 - 550)
    credit_behavior = 1.0 - credit_utilization_ratio
    g6_score = np.clip(
        0.35
        + bureau_norm * 0.35
        + credit_behavior * 0.15
        + np.random.normal(0, 0.04, N),
        0.35,
        0.90,
    )

    # ── Baseline Decision Fields ───────────────────────────────────────────

    approved = (bureau_score >= 700) & (dti_ratio <= 0.40) & (monthly_income >= 25000)
    decision_status = np.where(approved, "APPROVED", "REJECTED")

    max_eligible = (monthly_income * 12 * 0.35).astype(int)
    eligible_amount = np.where(approved, np.minimum(desired_amount, max_eligible), 0)

    interest_rate = np.zeros(N)
    interest_rate[approved & (bureau_score >= 750)] = 0.12
    interest_rate[approved & (bureau_score >= 720) & (bureau_score < 750)] = 0.135
    interest_rate[approved & (bureau_score >= 700) & (bureau_score < 720)] = 0.155

    # ── Assemble DataFrame ─────────────────────────────────────────────────

    df = pd.DataFrame(
        {
            "customer_id": customer_id,
            "age": age,
            "employment_type": employment_type,
            "employer_type": employer_type,
            "monthly_income": monthly_income,
            "employment_tenure_months": employment_tenure_months,
            "residence_type": residence_type,
            "city_tier": city_tier,
            "marital_status": marital_status,
            "dependents": dependents,
            "bureau_score": bureau_score,
            "active_loans": active_loans,
            "closed_loans": closed_loans,
            "unsecured_loans": unsecured_loans,
            "credit_utilization_ratio": np.round(credit_utilization_ratio, 4),
            "max_dpd_last_12m": max_dpd_last_12m,
            "inquiries_last_3m": inquiries_last_3m,
            "oldest_trade_line_months": oldest_trade_line_months,
            "credit_cards_active": credit_cards_active,
            "monthly_salary_credit": monthly_salary_credit,
            "salary_credit_consistency_6m": np.round(salary_credit_consistency_6m, 4),
            "average_monthly_balance_6m": average_monthly_balance_6m,
            "cheque_bounces_6m": cheque_bounces_6m,
            "cash_deposits_6m": cash_deposits_6m,
            "banking_stability_index": np.round(banking_stability_index, 4),
            "emi_obligation_amount": emi_obligation_amount,
            "desired_amount": desired_amount,
            "loan_type": loan_type,
            "dti_ratio": np.round(dti_ratio, 4),
            "net_disposable_income": net_disposable_income,
            "g5_score": np.round(g5_score, 4),
            "g6_score": np.round(g6_score, 4),
            "decision_status": decision_status,
            "eligible_amount": eligible_amount,
            "interest_rate": interest_rate,
        }
    )

    return df


def print_stats(df: pd.DataFrame) -> None:
    """Print summary statistics for validation."""
    total = len(df)
    approved = (df["decision_status"] == "APPROVED").sum()
    approval_rate = approved / total * 100

    dti_in_band = ((df["dti_ratio"] >= 0.35) & (df["dti_ratio"] <= 0.40)).sum()
    dti_pct = dti_in_band / total * 100

    bureau_700_720 = ((df["bureau_score"] >= 700) & (df["bureau_score"] <= 720)).sum()
    bureau_pct = bureau_700_720 / total * 100

    high_inquiries = (df["inquiries_last_3m"] > 3).sum()
    inquiry_pct = high_inquiries / total * 100

    print(f"\n{'='*60}")
    print(f"  DATASET SUMMARY — {total} rows, {len(df.columns)} columns")
    print(f"{'='*60}")
    print(f"  Approval rate:              {approved}/{total} ({approval_rate:.1f}%)")
    print(f"  DTI in 0.35-0.40 band:      {dti_in_band}/{total} ({dti_pct:.1f}%)")
    print(f"  Bureau score 700-720:        {bureau_700_720}/{total} ({bureau_pct:.1f}%)")
    print(f"  Inquiries > 3 (last 3m):     {high_inquiries}/{total} ({inquiry_pct:.1f}%)")
    print()
    print("  Bureau score distribution:")
    print(f"    Mean: {df['bureau_score'].mean():.1f}  Std: {df['bureau_score'].std():.1f}")
    print(f"    Min:  {df['bureau_score'].min()}   Max: {df['bureau_score'].max()}")
    print()
    print("  Monthly income distribution:")
    print(f"    Mean:   {df['monthly_income'].mean():.0f}")
    print(f"    Median: {df['monthly_income'].median():.0f}")
    print(f"    Min:    {df['monthly_income'].min()}   Max: {df['monthly_income'].max()}")
    print()
    print("  DTI ratio distribution:")
    print(f"    Mean: {df['dti_ratio'].mean():.4f}  Std: {df['dti_ratio'].std():.4f}")
    print(f"    Min:  {df['dti_ratio'].min():.4f}   Max: {df['dti_ratio'].max():.4f}")
    print()
    print("  Employment type distribution:")
    print(df["employment_type"].value_counts().to_string(header=False))
    print()
    print("  Interest rate distribution (approved only):")
    approved_df = df[df["decision_status"] == "APPROVED"]
    print(approved_df["interest_rate"].value_counts().sort_index().to_string(header=False))
    print(f"{'='*60}\n")


def main() -> None:
    df = generate_dataset()

    # Ensure output directory exists
    output_dir = Path(__file__).resolve().parent.parent / "data" / "sample_datasets"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "loan_applications_500.csv"
    df.to_csv(output_path, index=False)
    print(f"Generated {output_path}")

    print_stats(df)


if __name__ == "__main__":
    main()
