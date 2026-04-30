"""Seed script to generate 100000 synthetic US-fintech personal loan records.

Mirrors the data shape consumed by the policy impact engine (field_registry +
loan_record_service stats queries) but populates it with US-market values:

    - FICO score range 300-850 (Equifax / Experian / TransUnion)
    - USD income, balances, loan amounts
    - US banks and credit unions
    - US payment rails (ACH / Wire / Zelle / debit / credit card)
    - US employer categories (private / federal / state / non-profit / self-employed)
    - US loan purposes (debt consolidation, home improvement, medical, etc.)
    - APR ranges typical of fintech personal loans (5.99 % - 35.99 %)
    - LendingClub-style loan grades (A-G with sub-grades)
"""
import asyncio
import sys
import random
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import async_session
from app.models.loan_record import LoanRecord
from sqlalchemy import select, func


# ---------------------------------------------------------------------------
# US-fintech reference data
# ---------------------------------------------------------------------------

APPLICATION_TYPES = ["DIGITAL", "BRANCH", "PARTNER"]
APPLICATION_TYPE_WEIGHTS = [0.70, 0.18, 0.12]  # US fintech is digital-first

REPEAT_TYPES = ["FIRST_TIME", "REPEAT", "CONCURRENT"]
REPEAT_TYPE_WEIGHTS = [0.55, 0.32, 0.13]

EMPLOYMENT_TYPES = ["W2_FULL_TIME", "W2_PART_TIME", "SELF_EMPLOYED_1099", "BUSINESS_OWNER", "RETIRED"]
EMPLOYMENT_WEIGHTS = [0.62, 0.10, 0.15, 0.08, 0.05]

EMPLOYER_TYPES = ["PRIVATE", "GOVERNMENT_FEDERAL", "GOVERNMENT_STATE_LOCAL", "NON_PROFIT", "EDUCATION", "HEALTHCARE"]
EMPLOYER_WEIGHTS = [0.55, 0.08, 0.12, 0.06, 0.09, 0.10]

# US residence categories — MORTGAGE is treated as a separate category in US underwriting
RESIDENCE_TYPES = ["OWN", "MORTGAGE", "RENT", "FAMILY"]
RESIDENCE_WEIGHTS = [0.18, 0.34, 0.40, 0.08]

# Map "city tier" to US MSA size buckets so existing rules still work
CITY_TIERS = ["TIER_1", "TIER_2", "TIER_3"]  # T1 = top-25 MSA, T2 = mid MSA, T3 = small MSA / rural
CITY_TIER_WEIGHTS = [0.45, 0.38, 0.17]

MARITAL_STATUSES = ["MARRIED", "SINGLE", "DIVORCED", "WIDOWED", "DOMESTIC_PARTNER"]
MARITAL_WEIGHTS = [0.48, 0.36, 0.10, 0.04, 0.02]

# US states (top by population — covers ~70% of borrowers)
US_STATES = ["CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI",
             "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI",
             "CO", "MN", "SC", "AL", "LA", "KY", "OR", "OK", "CT", "UT"]

# Top US banks + credit unions + neobanks
BANKS = [
    "Chase", "Bank of America", "Wells Fargo", "Citibank", "U.S. Bank",
    "PNC Bank", "Truist", "Capital One", "TD Bank", "Goldman Sachs (Marcus)",
    "Ally Bank", "Discover Bank", "USAA", "Navy Federal Credit Union",
    "SoFi Bank", "Chime", "Charles Schwab Bank",
]

ACCOUNT_TYPES = ["CHECKING", "SAVINGS", "MONEY_MARKET"]
ACCOUNT_TYPE_WEIGHTS = [0.72, 0.22, 0.06]

# US credit bureaus
BUREAU_SOURCES = ["EXPERIAN", "EQUIFAX", "TRANSUNION"]
BUREAU_SOURCE_WEIGHTS = [0.40, 0.32, 0.28]

# Common US personal loan purposes
LOAN_PURPOSES = [
    "DEBT_CONSOLIDATION", "CREDIT_CARD_REFINANCE", "HOME_IMPROVEMENT",
    "MEDICAL", "MAJOR_PURCHASE", "AUTO", "MOVING", "VACATION",
    "WEDDING", "BUSINESS", "OTHER",
]
LOAN_PURPOSE_WEIGHTS = [0.34, 0.16, 0.12, 0.08, 0.07, 0.06, 0.04, 0.04, 0.03, 0.03, 0.03]

# Approval reason codes (US underwriting)
POSITIVE_REASON_CODES = [
    "PRIME_FICO_SCORE", "LOW_DTI_RATIO", "STABLE_W2_INCOME",
    "LOW_REVOLVING_UTILIZATION", "ELIGIBLE_FOR_REQUESTED_AMOUNT",
    "INCOME_SUFFICIENT_FOR_PAYMENT", "POSITIVE_BANKING_BEHAVIOR",
    "ON_TIME_PAYMENT_HISTORY", "AMOUNT_WITHIN_POLICY_CAP",
    "LONG_CREDIT_HISTORY", "LOW_HARD_INQUIRY_COUNT", "STRONG_CASHFLOW",
    "STABLE_EMPLOYMENT_TENURE", "HIGH_ACCOUNT_VINTAGE", "NO_RECENT_DELINQUENCY",
    "VERIFIED_INCOME", "HOMEOWNER",
]

# Rejection reason codes (US underwriting / FCRA-style adverse action codes)
REJECTION_REASON_CODES = [
    "SUBPRIME_FICO_SCORE", "HIGH_DTI_RATIO", "INSUFFICIENT_INCOME",
    "EXCESSIVE_REVOLVING_UTILIZATION", "TOO_MANY_RECENT_INQUIRIES",
    "INSUFFICIENT_CREDIT_HISTORY", "DELINQUENT_ACCOUNTS_REPORTED",
    "NSF_RETURN_HISTORY", "EMPLOYMENT_TENURE_TOO_SHORT",
    "AMOUNT_EXCEEDS_POLICY_CAP", "RECENT_BANKRUPTCY",
    "INCOME_NOT_VERIFIABLE", "CHARGE_OFF_REPORTED",
    "TAX_LIEN_OR_JUDGMENT", "FRAUD_ALERT_ON_FILE",
]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def generate_fico_score(rng: np.random.Generator) -> int:
    """FICO range 300-850. Skewed toward US median ~720."""
    score = int(rng.normal(720, 70))
    return max(300, min(850, score))


def generate_monthly_income(rng: np.random.Generator) -> float:
    """USD monthly income. Lognormal centered roughly on US median household
    monthly income (~$6,000) with a long right tail for prime borrowers."""
    income = float(rng.lognormal(mean=8.7, sigma=0.55))  # ~ median exp(8.7) ≈ 6,000
    return round(max(2000, min(50000, income)), 0)


def generate_age(rng: np.random.Generator) -> int:
    age = int(rng.normal(40, 11))
    return max(21, min(75, age))


def generate_desired_amount(monthly_income: float, rng: np.random.Generator) -> float:
    """US personal loans: $1,000 - $100,000. Most fintechs cap at $50k."""
    multiplier = rng.uniform(2, 8)
    amount = monthly_income * multiplier
    return round(max(1000, min(100000, amount)) / 500) * 500


def get_risk_segment(fico: int) -> str:
    """US FICO segmentation."""
    if fico >= 740:
        return "SUPER_PRIME"
    if fico >= 670:
        return "PRIME"
    if fico >= 580:
        return "NEAR_PRIME"
    return "SUBPRIME"


def get_pricing_tier(fico: int, g5_score: float) -> str:
    combined = fico / 850 * 0.6 + g5_score * 0.4
    if combined >= 0.78:
        return "TIER_1"
    if combined >= 0.60:
        return "TIER_2"
    return "TIER_3"


def get_loan_grade(fico: int, rng: np.random.Generator) -> str:
    """LendingClub-style A1-G5 sub-grades by FICO."""
    if fico >= 780:
        letter = rng.choice(["A", "A", "B"])
    elif fico >= 740:
        letter = rng.choice(["A", "B", "B"])
    elif fico >= 700:
        letter = rng.choice(["B", "C", "C"])
    elif fico >= 660:
        letter = rng.choice(["C", "D", "D"])
    elif fico >= 620:
        letter = rng.choice(["D", "E", "E"])
    elif fico >= 580:
        letter = rng.choice(["E", "F"])
    else:
        letter = rng.choice(["F", "G"])
    sub = int(rng.integers(1, 6))
    return f"{letter}{sub}"


def determine_decision(fico: int, dti: float) -> str:
    """US underwriting decision. CFPB QM rule caps DTI at 43% for QM,
    but fintechs commonly approve up to 50% for prime borrowers."""
    if fico >= 670 and dti <= 0.43:
        return "APPROVED"
    if fico >= 600 and dti <= 0.50:
        return "APPROVED_WITH_CONDITIONS"
    return "REJECTED"


def compute_monthly_payment(principal: float, annual_rate: float, term_months: int) -> float:
    """US-style monthly payment formula (same math as EMI)."""
    if annual_rate <= 0 or term_months <= 0:
        return round(principal / max(term_months, 1), 0)
    monthly_rate = annual_rate / 12
    payment = principal * monthly_rate * (1 + monthly_rate) ** term_months / (
        (1 + monthly_rate) ** term_months - 1
    )
    return round(payment, 2)


def pick_reason_codes(fico: int, dti: float, g5_score: float,
                      revolving_util: float, rng: np.random.Generator) -> list[str]:
    codes = []
    if fico >= 700:
        codes.append("PRIME_FICO_SCORE")
    if dti < 0.36:
        codes.append("LOW_DTI_RATIO")
    if g5_score >= 0.75:
        codes.append("STABLE_W2_INCOME")
    if revolving_util < 0.30:
        codes.append("LOW_REVOLVING_UTILIZATION")
    codes.append("ELIGIBLE_FOR_REQUESTED_AMOUNT")
    codes.append("INCOME_SUFFICIENT_FOR_PAYMENT")

    remaining = [c for c in POSITIVE_REASON_CODES if c not in codes]
    extra_count = max(0, int(rng.integers(0, 3)))
    if extra_count > 0 and remaining:
        extras = rng.choice(remaining, size=min(extra_count, len(remaining)), replace=False).tolist()
        codes.extend(extras)
    return codes[:6]


def pick_reject_rules(fico: int, dti: float, rng: np.random.Generator) -> list[str]:
    rules = []
    if fico < 600:
        rules.append("SUBPRIME_FICO_SCORE")
    if dti > 0.50:
        rules.append("HIGH_DTI_RATIO")
    if not rules:
        rules.append("INSUFFICIENT_INCOME")

    remaining = [c for c in REJECTION_REASON_CODES if c not in rules]
    extra = max(0, int(rng.integers(0, 2)))
    if extra > 0 and remaining:
        extras = rng.choice(remaining, size=min(extra, len(remaining)), replace=False).tolist()
        rules.extend(extras)
    return rules[:4]


# ---------------------------------------------------------------------------
# Record builder
# ---------------------------------------------------------------------------

def generate_single_record(index: int, rng: np.random.Generator) -> dict:
    loan_app_id = f"LA-{index:08d}"

    # Core attributes
    fico = generate_fico_score(rng)
    monthly_income = generate_monthly_income(rng)
    age = generate_age(rng)
    desired_amount = generate_desired_amount(monthly_income, rng)

    application_type = rng.choice(APPLICATION_TYPES, p=APPLICATION_TYPE_WEIGHTS)
    repeat_type = rng.choice(REPEAT_TYPES, p=REPEAT_TYPE_WEIGHTS)
    employment_type = rng.choice(EMPLOYMENT_TYPES, p=EMPLOYMENT_WEIGHTS)
    employer_type = rng.choice(EMPLOYER_TYPES, p=EMPLOYER_WEIGHTS)
    residence_type = rng.choice(RESIDENCE_TYPES, p=RESIDENCE_WEIGHTS)
    city_tier = rng.choice(CITY_TIERS, p=CITY_TIER_WEIGHTS)
    marital_status = rng.choice(MARITAL_STATUSES, p=MARITAL_WEIGHTS)
    bank_name = str(rng.choice(BANKS))
    account_type = rng.choice(ACCOUNT_TYPES, p=ACCOUNT_TYPE_WEIGHTS)
    bureau_source = rng.choice(BUREAU_SOURCES, p=BUREAU_SOURCE_WEIGHTS)
    state_code = str(rng.choice(US_STATES))
    loan_purpose = rng.choice(LOAN_PURPOSES, p=LOAN_PURPOSE_WEIGHTS)

    dependents = int(rng.integers(0, 5))
    employment_tenure_months = max(3, int(rng.normal((age - 22) * 12 * 0.45, 28)))
    customer_id = f"CUST-{rng.integers(100000, 999999)}"

    # Banking inputs (USD, correlated with income)
    account_vintage_months = max(6, int(rng.normal(54, 22)))
    monthly_salary_credit = round(monthly_income * float(rng.uniform(0.95, 1.02)), 2)
    salary_consistency = round(float(rng.uniform(0.78, 0.99)), 2)
    avg_balance_6m = round(monthly_income * float(rng.uniform(0.6, 1.8)), 2)
    avg_balance_12m = round(avg_balance_6m * float(rng.uniform(0.85, 1.10)), 2)
    current_balance = round(avg_balance_6m * float(rng.uniform(0.5, 1.6)), 2)
    avg_monthly_credit_6m = round(monthly_income * float(rng.uniform(1.0, 1.5)), 2)
    avg_monthly_debit_6m = round(monthly_income * float(rng.uniform(0.7, 1.1)), 2)
    total_credit_6m = round(avg_monthly_credit_6m * 6, 2)
    total_debit_6m = round(avg_monthly_debit_6m * 6, 2)
    inward_txn_6m = int(rng.integers(80, 350))
    outward_txn_6m = int(rng.integers(60, 300))

    # US payment rails (replaces UPI/IMPS/NEFT/RTGS)
    ach_txn_3m = int(rng.integers(20, 200))           # ACH transfers (most common)
    zelle_txn_3m = int(rng.integers(0, 80))           # Zelle peer-to-peer
    debit_card_txn_3m = int(rng.integers(40, 350))    # Debit card swipes
    credit_card_txn_3m = int(rng.integers(10, 200))   # Credit card spend
    wire_txn_3m = int(rng.integers(0, 5))             # Wires (rare for individuals)
    check_deposits_6m = int(rng.integers(0, 10))      # Mobile/branch check deposits
    cash_withdrawals_6m = int(rng.integers(2, 20))
    max_single_credit_3m = round(monthly_income * float(rng.uniform(1.0, 2.5)), 2)
    max_single_debit_3m = round(monthly_income * float(rng.uniform(0.4, 1.2)), 2)

    # NSF returns (US equivalent of "cheque bounces" — kept under same field name
    # because it lives in field_registry and rules reference it by that key).
    nsf_returns_6m = int(rng.integers(0, 3)) if fico < 650 else 0
    low_balance_instances_6m = int(rng.integers(0, 6)) if fico < 700 else int(rng.integers(0, 3))

    # Existing obligations
    emi_auto_debits = int(rng.integers(0, 5))
    monthly_obligation = round(monthly_income * float(rng.uniform(0.05, 0.40)), 2)
    loan_repayment_bounces_12m = int(rng.integers(0, 3)) if fico < 600 else 0

    # Bureau / tradelines
    active_loans = int(rng.integers(0, 6))
    closed_loans = int(rng.integers(0, 12))
    secured_loans = int(rng.integers(0, max(active_loans, 1))) if active_loans > 0 else 0
    unsecured_loans = active_loans - secured_loans
    credit_cards_active = int(rng.integers(0, 6))
    total_credit_limit = round(monthly_income * float(rng.integers(4, 18)), 2)
    revolving_utilization = round(float(rng.uniform(0.05, 0.85)), 2)
    overdue_accounts = int(rng.integers(0, 3)) if fico < 650 else 0
    max_dpd_12m = int(rng.choice([0, 0, 0, 0, 30, 60, 90, 120])) if fico < 650 else 0
    inquiries_3m = int(rng.integers(0, 6))
    inquiries_12m = inquiries_3m + int(rng.integers(0, 8))
    oldest_trade_line_months = max(12, int(rng.normal(96, 36)))
    avg_account_age_months = max(6, int(oldest_trade_line_months * float(rng.uniform(0.4, 0.8))))

    # US-specific public-record flags
    bankruptcy_flag = bool(rng.choice([False, False, False, False, True])) if fico < 600 else False
    bankruptcy_chapter = (str(rng.choice(["CHAPTER_7", "CHAPTER_13"])) if bankruptcy_flag else None)
    months_since_bankruptcy = int(rng.integers(24, 96)) if bankruptcy_flag else None
    tax_lien_flag = bool(rng.choice([False, False, False, True])) if fico < 620 else False
    charge_offs_24m = int(rng.integers(0, 3)) if fico < 600 else 0

    # DTI
    dti = round(monthly_obligation / monthly_income, 3) if monthly_income > 0 else 0.5
    dti = max(0.05, min(0.80, dti))
    net_monthly_surplus = round(monthly_income - monthly_obligation - avg_monthly_debit_6m * 0.3, 2)
    net_monthly_surplus = max(0.0, net_monthly_surplus)

    # Internal scores (0-1, correlated with FICO)
    base_g5 = (fico - 300) / 550
    g5_score = round(max(0.10, min(0.99, base_g5 + float(rng.normal(0, 0.07)))), 2)
    base_g6 = (fico - 300) / 550 * 0.92
    g6_score = round(max(0.10, min(0.99, base_g6 + float(rng.normal(0, 0.07)))), 2)

    g5_sub_scores = {
        "income_stability_model":     round(max(0.10, min(0.99, g5_score + float(rng.normal(0, 0.05)))), 2),
        "transaction_behavior_model": round(max(0.10, min(0.99, g5_score + float(rng.normal(0, 0.06)))), 2),
        "repayment_capacity_model":   round(max(0.10, min(0.99, g5_score + float(rng.normal(0, 0.05)))), 2),
        "salary_consistency_model":   round(max(0.10, min(0.99, g5_score + float(rng.normal(0, 0.04)))), 2),
        "cashflow_surplus_model":     round(max(0.10, min(0.99, g5_score + float(rng.normal(0, 0.06)))), 2),
    }
    g6_sub_scores = {
        "bureau_risk_model":      round(max(0.10, min(0.99, g6_score + float(rng.normal(0, 0.05)))), 2),
        "fraud_detection_model":  round(max(0.10, min(0.99, g6_score + float(rng.normal(0, 0.06)))), 2),
        "device_risk_model":      round(max(0.10, min(0.99, g6_score + float(rng.normal(0, 0.07)))), 2),
        "behavioral_risk_model":  round(max(0.10, min(0.99, g6_score + float(rng.normal(0, 0.05)))), 2),
        "credit_exposure_model":  round(max(0.10, min(0.99, g6_score + float(rng.normal(0, 0.06)))), 2),
    }

    banking_stability_index = round(max(0.10, min(0.99,
        salary_consistency * 0.4 + g5_score * 0.3 + (1 - revolving_utilization) * 0.3
    )), 2)
    income_stability_score = round(max(0.10, min(0.99,
        salary_consistency * 0.6 + float(rng.normal(0.15, 0.05))
    )), 2)
    transaction_volatility = round(max(0.05, min(0.95, float(rng.beta(2, 5)))), 2)

    credit_risk_band = "LOW" if fico >= 740 else "MEDIUM" if fico >= 670 else "HIGH"
    risk_segment = get_risk_segment(fico)
    pricing_tier = get_pricing_tier(fico, g5_score)

    # Maximum eligible loan amount (offer-side)
    max_eligible = round(monthly_income * float(rng.uniform(3, 10)) / 500) * 500
    max_eligible = max(desired_amount, max_eligible)
    recommended_term_months = int(rng.choice([12, 24, 36, 48, 60, 72, 84]))

    # Timestamps
    days_ago = int(rng.integers(0, 365))
    app_timestamp = datetime.utcnow() - timedelta(days=days_ago)
    decision_timestamp = app_timestamp + timedelta(minutes=int(rng.integers(2, 90)))

    # Decision
    decision_status = determine_decision(fico, dti)

    # SPID (Sub-Product Identifier)
    spid = str(rng.integers(1000, 9999))

    annual_income = round(monthly_income * 12, 0)
    ndi_amount = round(monthly_income - monthly_obligation, 2)

    # Policy caps (USD)
    annual_amount_cap = round(max(20000, annual_income * float(rng.uniform(0.30, 0.50))) / 1000) * 1000
    ndi_cap = round(float(rng.choice([0.40, 0.45, 0.50])), 2)
    dti_cap = round(float(rng.choice([0.43, 0.45, 0.50])), 2)  # 43% = CFPB QM rule

    # ---- REQUEST PAYLOAD ----------------------------------------------------
    request_payload = {
        "loan_application_id": loan_app_id,
        "application_type": application_type,
        "repeat_type": repeat_type,
        "credit_policy": "PERSONAL",
        "credit_policy_version": "CP-PERSONAL-US-V3.2",
        "loan_purpose": loan_purpose,
        "desired_amount": desired_amount,
        "currency": "USD",
        "application_timestamp": app_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "borrower_credit_model": {
            "customer_inputs": {
                "customer_id": customer_id,
                "age": age,
                "employment_type": employment_type,
                "employer_type": employer_type,
                "monthly_income": monthly_income,
                "annual_income": annual_income,
                "employment_tenure_months": employment_tenure_months,
                "residence_type": residence_type,
                "state": state_code,
                "city_tier": city_tier,
                "marital_status": marital_status,
                "dependents": dependents,
            },
            "banking_inputs": {
                "primary_bank_name": bank_name,
                "account_type": account_type,
                "account_vintage_months": account_vintage_months,
                "current_account_balance": current_balance,
                "average_monthly_balance_6m": avg_balance_6m,
                "average_monthly_balance_12m": avg_balance_12m,
                "monthly_salary_credit": monthly_salary_credit,
                "salary_credit_consistency_6m": salary_consistency,
                "average_monthly_credit_6m": avg_monthly_credit_6m,
                "average_monthly_debit_6m": avg_monthly_debit_6m,
                "total_credit_amount_6m": total_credit_6m,
                "total_debit_amount_6m": total_debit_6m,
                "inward_transactions_count_6m": inward_txn_6m,
                "outward_transactions_count_6m": outward_txn_6m,
                "ach_transactions_3m": ach_txn_3m,
                "zelle_transactions_3m": zelle_txn_3m,
                "debit_card_transactions_3m": debit_card_txn_3m,
                "credit_card_transactions_3m": credit_card_txn_3m,
                "wire_transactions_3m": wire_txn_3m,
                "check_deposits_6m": check_deposits_6m,
                "cash_withdrawals_6m": cash_withdrawals_6m,
                "max_single_credit_3m": max_single_credit_3m,
                "max_single_debit_3m": max_single_debit_3m,
                # Kept under historical name (registered in field_registry as
                # "cheque_bounces_6m"). Semantically: NSF returns / bounced items.
                "cheque_bounces_6m": nsf_returns_6m,
                "low_balance_instances_6m": low_balance_instances_6m,
                "emi_auto_debits_per_month": emi_auto_debits,
                "emi_obligation_amount": monthly_obligation,
                "loan_repayment_bounces_12m": loan_repayment_bounces_12m,
            },
            "bureau_credits": {
                "bureau_score": fico,                 # FICO 300-850
                "bureau_score_model": "FICO_8",
                "bureau_source": bureau_source,       # Equifax / Experian / TransUnion
                "active_loans": active_loans,
                "closed_loans": closed_loans,
                "secured_loans": secured_loans,
                "unsecured_loans": unsecured_loans,
                "credit_cards_active": credit_cards_active,
                "total_credit_limit": total_credit_limit,
                "credit_utilization_ratio": revolving_utilization,
                "overdue_accounts": overdue_accounts,
                "max_dpd_last_12m": max_dpd_12m,
                "inquiries_last_3m": inquiries_3m,
                "inquiries_last_12m": inquiries_12m,
                "oldest_trade_line_months": oldest_trade_line_months,
                "average_account_age_months": avg_account_age_months,
                "bankruptcy_flag": bankruptcy_flag,
                "bankruptcy_chapter": bankruptcy_chapter,
                "months_since_bankruptcy": months_since_bankruptcy,
                "tax_lien_flag": tax_lien_flag,
                "charge_offs_24m": charge_offs_24m,
            },
        },
        "calculated_attributes": {
            "debt_to_income_ratio": dti,
            "net_monthly_surplus": net_monthly_surplus,
            "banking_stability_index": banking_stability_index,
            "credit_risk_band": credit_risk_band,
            "income_stability_score": income_stability_score,
            "transaction_volatility_index": transaction_volatility,
            "scores": {
                "g5": {
                    "score": g5_score,
                    "model_version": "g5_v3.6",
                    "sub_model_scores": g5_sub_scores,
                },
                "g6": {
                    "score": g6_score,
                    "model_version": "g6_v2.9",
                    "sub_model_scores": g6_sub_scores,
                },
            },
        },
        "decision_context": {
            "policy_eligible": decision_status != "REJECTED",
            "max_eligible_amount": max_eligible,
            "recommended_tenure_months": recommended_term_months,
            "risk_segment": risk_segment,
            "pricing_tier": pricing_tier,
        },
    }

    # ---- RESPONSE PAYLOAD ---------------------------------------------------
    choices = []
    if decision_status in ("APPROVED", "APPROVED_WITH_CONDITIONS"):
        num_offers = int(rng.integers(2, 5))
        for offer_idx in range(num_offers):
            amount_factor = float(rng.uniform(0.6, 1.05))
            offer_amount = round(desired_amount * amount_factor / 500) * 500
            offer_amount = max(1000, offer_amount)

            # APR: 5.99% (super-prime) → 35.99% (subprime). Linear interp on FICO.
            base_apr = 0.3599 - (fico - 300) / 550 * 0.30   # 0.3599 → 0.0599
            apr_variation = float(rng.uniform(-0.012, 0.012))
            interest_rate = round(max(0.0599, min(0.3599, base_apr + apr_variation)), 4)

            # APR includes origination fee amortized → typically 0.5%-2% above note rate
            apr = round(interest_rate + float(rng.uniform(0.005, 0.02)), 4)
            term_months = int(rng.choice([12, 24, 36, 48, 60, 72, 84]))
            loan_grade = get_loan_grade(fico, rng)
            origination_fee_pct = round(float(rng.uniform(0.00, 0.08)), 4)  # 0%-8% (LendingClub style)
            monthly_payment = compute_monthly_payment(offer_amount, interest_rate, term_months)

            dti_after = round(dti + (monthly_payment / monthly_income) if monthly_income > 0 else dti, 3)
            ndi_after = round(ndi_amount - monthly_payment, 2)

            reason_codes = pick_reason_codes(fico, dti, g5_score, revolving_utilization, rng)

            choices.append({
                "offer_id": f"OFFER-{offer_idx + 1}",
                "loan_amount": offer_amount,
                "interest_rate": interest_rate,
                "apr": apr,
                "maturity_months": term_months,
                "loan_grade": loan_grade,
                "origination_fee_pct": origination_fee_pct,
                "monthly_payment_estimate": monthly_payment,
                "dti_after_loan": dti_after,
                "ndi_after_loan": ndi_after,
                "reject_rules": [],
                "decision_reason_codes": reason_codes,
            })

    default_offer = None
    if choices:
        first = choices[0]
        default_offer = {
            "offer_id": first["offer_id"],
            "loan_amount": first["loan_amount"],
            "interest_rate": first["interest_rate"],
            "apr": first["apr"],
            "maturity_months": first["maturity_months"],
            "loan_grade": first["loan_grade"],
            "origination_fee_pct": first["origination_fee_pct"],
        }

    response_payload = {
        "loan_application_id": loan_app_id,
        "decision_status": decision_status,
        "application_type": application_type,
        "SPID": spid,
        "repeat_type": repeat_type,
        "credit_policy": "PERSONAL",
        "credit_policy_version": "CP-PERSONAL-US-V3.2",
        "loan_purpose": loan_purpose,
        "desired_amount": desired_amount,
        "currency": "USD",
        "bureau_variables": {
            "bureau_source": bureau_source,
            "bureau_score": fico,
            "bureau_score_model": "FICO_8",
            "risk_band": credit_risk_band,
            "active_loans": active_loans,
            "credit_utilization_ratio": revolving_utilization,
            "recent_inquiries_3m": inquiries_3m,
            "oldest_trade_line_months": oldest_trade_line_months,
            "bankruptcy_flag": bankruptcy_flag,
        },
        "calculated_attributes": {
            "g5_score": g5_score,
            "g6_score": g6_score,
            "monthly_income": monthly_income,
            "monthly_obligations": monthly_obligation,
            "annual_income": annual_income,
            "ndi_amount": ndi_amount,
            "dti_amount": dti,
            "banking_stability_index": banking_stability_index,
        },
        "policy_caps": {
            "annual_amount_cap": annual_amount_cap,
            "ndi_cap": ndi_cap,
            "dti_cap": dti_cap,    # 0.43 = CFPB QM rule cap
        },
        "choices": choices,
        "default_offer": default_offer,
        "underwriting_metadata": {
            "decision_engine_version": "UW-ENGINE-US-5.4",
            "model_versions": {
                "g5_model": "v3.6",
                "g6_model": "v2.9",
            },
            "decision_timestamp": decision_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "regulatory_framework": ["TILA", "ECOA", "FCRA"],
        },
    }

    if decision_status == "REJECTED":
        response_payload["reject_rules"] = pick_reject_rules(fico, dti, rng)
        # FCRA-compliant adverse-action notice metadata
        response_payload["adverse_action"] = {
            "notice_required": True,
            "notice_template": "AAN_FCRA_v2",
            "credit_bureau_used": bureau_source,
        }

    return {
        "loan_application_id": loan_app_id,
        "request_payload": request_payload,
        "response_payload": response_payload,
        "created_at": app_timestamp,
    }


def generate_records(count: int = 100_000) -> list[dict]:
    """Reseed every 2000 records to create distinct population segments."""
    rng = np.random.default_rng(seed=42)
    records = []
    for i in range(1, count + 1):
        if i % 2000 == 1 and i > 1:
            rng = np.random.default_rng(seed=42 + i)
        records.append(generate_single_record(i, rng))
    return records


async def main():
    force = "--force" in sys.argv

    # Optional override: --count=N (default is 100k for a corpus large enough
    # to surface long-tail rule interactions while keeping seed time under a
    # couple of minutes on a developer laptop)
    count = 100_000
    for arg in sys.argv[1:]:
        if arg.startswith("--count="):
            try:
                count = int(arg.split("=", 1)[1])
            except ValueError:
                pass

    async with async_session() as db:
        count_result = await db.execute(select(func.count(LoanRecord.id)))
        existing_count = count_result.scalar() or 0

        if existing_count > 0 and not force:
            print(f"Database already has {existing_count} loan records. Use --force to reseed.")
            return

        if existing_count > 0 and force:
            from sqlalchemy import delete
            await db.execute(delete(LoanRecord))
            await db.commit()
            print(f"Cleared {existing_count} existing loan records.")

        print(f"Generating {count} synthetic US-fintech personal loan records...")
        records = generate_records(count)

        # Bulk-insert in chunks to keep memory and the WAL happy
        CHUNK = 500
        for start in range(0, len(records), CHUNK):
            batch = records[start:start + CHUNK]
            for rec in batch:
                db.add(LoanRecord(**rec))
            await db.commit()
            print(f"  inserted {min(start + CHUNK, len(records))} / {len(records)}")

        print(f"Seeded {len(records)} loan records successfully.")


if __name__ == "__main__":
    asyncio.run(main())
