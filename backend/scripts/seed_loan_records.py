"""Seed script to generate 2000+ synthetic loan records with full payload structures."""
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


# --- Constants ---

APPLICATION_TYPES = ["DIGITAL", "BRANCH", "PARTNER"]
APPLICATION_TYPE_WEIGHTS = [0.55, 0.30, 0.15]

REPEAT_TYPES = ["FIRST_TIME", "REPEAT", "CONCURRENT"]
REPEAT_TYPE_WEIGHTS = [0.45, 0.35, 0.20]

EMPLOYMENT_TYPES = ["SALARIED", "SELF_EMPLOYED", "BUSINESS"]
EMPLOYMENT_WEIGHTS = [0.60, 0.25, 0.15]

EMPLOYER_TYPES = ["PRIVATE", "GOVERNMENT", "PSU", "MNC"]
EMPLOYER_WEIGHTS = [0.45, 0.15, 0.15, 0.25]

RESIDENCE_TYPES = ["OWNED", "RENTED", "FAMILY"]
RESIDENCE_WEIGHTS = [0.30, 0.45, 0.25]

CITY_TIERS = ["TIER_1", "TIER_2", "TIER_3"]
CITY_TIER_WEIGHTS = [0.40, 0.35, 0.25]

MARITAL_STATUSES = ["MARRIED", "SINGLE", "DIVORCED", "WIDOWED"]
MARITAL_WEIGHTS = [0.55, 0.30, 0.10, 0.05]

BANKS = ["ICICI Bank", "HDFC Bank", "SBI", "Axis Bank", "Kotak Bank", "PNB", "Bank of Baroda"]

ACCOUNT_TYPES = ["SAVINGS", "CURRENT"]
ACCOUNT_TYPE_WEIGHTS = [0.75, 0.25]

BUREAU_SOURCES = ["CIBIL", "EXPERIAN", "EQUIFAX"]
BUREAU_SOURCE_WEIGHTS = [0.60, 0.25, 0.15]

# Approval reason codes
POSITIVE_REASON_CODES = [
    "HIGH_BUREAU_SCORE", "LOW_DTI_RATIO", "STABLE_SALARY_CREDIT",
    "LOW_CREDIT_UTILIZATION", "ELIGIBLE_FOR_REQUESTED_AMOUNT",
    "INCOME_SUFFICIENT_FOR_EMI", "POSITIVE_BANKING_BEHAVIOR",
    "GOOD_REPAYMENT_HISTORY", "AMOUNT_WITHIN_POLICY_CAP",
    "LONG_CREDIT_HISTORY", "LOW_INQUIRY_COUNT", "STRONG_CASHFLOW",
    "STABLE_EMPLOYMENT", "HIGH_ACCOUNT_VINTAGE",
]

# Rejection reason codes
REJECTION_REASON_CODES = [
    "LOW_BUREAU_SCORE", "HIGH_DTI_RATIO", "INSUFFICIENT_INCOME",
    "EXCESSIVE_CREDIT_UTILIZATION", "HIGH_INQUIRY_COUNT",
    "SHORT_CREDIT_HISTORY", "OVERDUE_ACCOUNTS_DETECTED",
    "UNSTABLE_BANKING_BEHAVIOR", "EMPLOYMENT_TENURE_TOO_SHORT",
    "AMOUNT_EXCEEDS_POLICY_CAP", "HIGH_CHEQUE_BOUNCE_RATE",
    "SALARY_CREDIT_INCONSISTENT",
]


# --- Generators ---

def generate_bureau_score(rng: np.random.Generator) -> int:
    score = int(rng.normal(700, 80))
    return max(300, min(900, score))


def generate_monthly_income(rng: np.random.Generator) -> float:
    income = float(rng.lognormal(mean=10.8, sigma=0.6))
    return round(max(15000, min(500000, income)), 0)


def generate_age(rng: np.random.Generator) -> int:
    age = int(rng.normal(35, 8))
    return max(21, min(65, age))


def generate_desired_amount(monthly_income: float, rng: np.random.Generator) -> float:
    multiplier = rng.uniform(2, 6)
    amount = monthly_income * multiplier
    return round(max(50000, min(2000000, amount)) / 1000) * 1000


def get_risk_segment(bureau_score: int) -> str:
    if bureau_score >= 750:
        return "LOW_RISK"
    elif bureau_score >= 650:
        return "MEDIUM_RISK"
    else:
        return "HIGH_RISK"


def get_pricing_tier(bureau_score: int, g5_score: float) -> str:
    combined = bureau_score / 900 * 0.6 + g5_score * 0.4
    if combined >= 0.75:
        return "TIER_1"
    elif combined >= 0.55:
        return "TIER_2"
    else:
        return "TIER_3"


def get_loan_grade(bureau_score: int, rng: np.random.Generator) -> str:
    if bureau_score >= 800:
        return rng.choice(["P1", "P2"])
    elif bureau_score >= 750:
        return rng.choice(["P2", "P3"])
    elif bureau_score >= 700:
        return rng.choice(["P3", "P4"])
    elif bureau_score >= 650:
        return rng.choice(["P4", "P5"])
    elif bureau_score >= 600:
        return rng.choice(["P5", "P6"])
    else:
        return rng.choice(["P6", "P7"])


def determine_decision(bureau_score: int, dti: float) -> str:
    if bureau_score >= 700 and dti < 0.40:
        return "APPROVED"
    elif bureau_score >= 600 and dti <= 0.55:
        return "APPROVED_WITH_CONDITIONS"
    else:
        return "REJECTED"


def compute_emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    """Compute EMI using standard formula."""
    if annual_rate <= 0 or tenure_months <= 0:
        return round(principal / max(tenure_months, 1), 0)
    monthly_rate = annual_rate / 12
    emi = principal * monthly_rate * (1 + monthly_rate) ** tenure_months / (
        (1 + monthly_rate) ** tenure_months - 1
    )
    return round(emi, 0)


def pick_reason_codes(bureau_score: int, dti: float, g5_score: float,
                      credit_util: float, rng: np.random.Generator) -> list[str]:
    """Pick 3-5 realistic positive reason codes based on attributes."""
    codes = []
    if bureau_score >= 700:
        codes.append("HIGH_BUREAU_SCORE")
    if dti < 0.35:
        codes.append("LOW_DTI_RATIO")
    if g5_score >= 0.75:
        codes.append("STABLE_SALARY_CREDIT")
    if credit_util < 0.40:
        codes.append("LOW_CREDIT_UTILIZATION")
    codes.append("ELIGIBLE_FOR_REQUESTED_AMOUNT")
    codes.append("INCOME_SUFFICIENT_FOR_EMI")

    remaining = [c for c in POSITIVE_REASON_CODES if c not in codes]
    extra_count = max(0, rng.integers(0, 3))
    if extra_count > 0 and remaining:
        extras = rng.choice(remaining, size=min(extra_count, len(remaining)), replace=False).tolist()
        codes.extend(extras)

    return codes[:6]


def pick_reject_rules(bureau_score: int, dti: float, rng: np.random.Generator) -> list[str]:
    """Pick 1-3 rejection rules based on attributes."""
    rules = []
    if bureau_score < 600:
        rules.append("LOW_BUREAU_SCORE")
    if dti > 0.55:
        rules.append("HIGH_DTI_RATIO")
    if not rules:
        rules.append("INSUFFICIENT_INCOME")

    remaining = [c for c in REJECTION_REASON_CODES if c not in rules]
    extra = max(0, rng.integers(0, 2))
    if extra > 0 and remaining:
        extras = rng.choice(remaining, size=min(extra, len(remaining)), replace=False).tolist()
        rules.extend(extras)

    return rules[:4]


def generate_single_record(index: int, rng: np.random.Generator) -> dict:
    loan_app_id = f"LA-{index:08d}"

    # Core attributes
    bureau_score = generate_bureau_score(rng)
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
    bank_name = rng.choice(BANKS)
    account_type = rng.choice(ACCOUNT_TYPES, p=ACCOUNT_TYPE_WEIGHTS)
    bureau_source = rng.choice(BUREAU_SOURCES, p=BUREAU_SOURCE_WEIGHTS)

    dependents = int(rng.integers(0, 5))
    employment_tenure_months = max(6, int(rng.normal((age - 22) * 12 * 0.4, 24)))
    customer_id = f"CUST-{rng.integers(100000, 999999)}"

    # Banking inputs (correlated with income)
    account_vintage_months = max(6, int(rng.normal(48, 20)))
    monthly_salary_credit = round(monthly_income * float(rng.uniform(0.95, 1.02)), 0)
    salary_consistency = round(float(rng.uniform(0.75, 0.99)), 2)
    avg_balance_6m = round(monthly_income * float(rng.uniform(0.8, 1.5)), 0)
    avg_balance_12m = round(avg_balance_6m * float(rng.uniform(0.85, 1.1)), 0)
    current_balance = round(avg_balance_6m * float(rng.uniform(0.7, 1.6)), 0)
    avg_monthly_credit_6m = round(monthly_income * float(rng.uniform(1.0, 1.5)), 0)
    avg_monthly_debit_6m = round(monthly_income * float(rng.uniform(0.7, 1.1)), 0)
    total_credit_6m = round(avg_monthly_credit_6m * 6, 0)
    total_debit_6m = round(avg_monthly_debit_6m * 6, 0)
    inward_txn_6m = int(rng.integers(80, 350))
    outward_txn_6m = int(rng.integers(60, 300))
    upi_txn_3m = int(rng.integers(30, 250))
    imps_txn_3m = int(rng.integers(5, 60))
    neft_txn_3m = int(rng.integers(2, 30))
    rtgs_txn_3m = int(rng.integers(0, 8))
    cash_deposits_6m = int(rng.integers(0, 12))
    cash_withdrawals_6m = int(rng.integers(2, 20))
    max_single_credit_3m = round(monthly_income * float(rng.uniform(1.0, 2.0)), 0)
    max_single_debit_3m = round(monthly_income * float(rng.uniform(0.4, 1.0)), 0)
    cheque_bounces_6m = int(rng.integers(0, 3)) if bureau_score < 650 else 0
    low_balance_instances_6m = int(rng.integers(0, 6)) if bureau_score < 700 else int(rng.integers(0, 3))

    # EMI / obligations
    emi_auto_debits = int(rng.integers(0, 5))
    emi_obligation = round(monthly_income * float(rng.uniform(0.05, 0.35)), 0)
    loan_repayment_bounces_12m = int(rng.integers(0, 3)) if bureau_score < 600 else 0

    # Bureau credits
    active_loans = int(rng.integers(0, 6))
    closed_loans = int(rng.integers(0, 10))
    secured_loans = max(0, int(rng.integers(0, active_loans + 1))) if active_loans > 0 else 0
    unsecured_loans = active_loans - secured_loans
    credit_cards_active = int(rng.integers(0, 5))
    total_credit_limit = round(monthly_income * float(rng.integers(4, 12)), 0)
    credit_utilization_ratio = round(float(rng.uniform(0.05, 0.85)), 2)
    overdue_accounts = int(rng.integers(0, 3)) if bureau_score < 650 else 0
    max_dpd_12m = int(rng.choice([0, 0, 0, 0, 15, 30, 60, 90])) if bureau_score < 650 else 0
    inquiries_3m = int(rng.integers(0, 6))
    inquiries_12m = inquiries_3m + int(rng.integers(0, 8))
    oldest_trade_line_months = max(12, int(rng.normal(60, 25)))
    avg_account_age_months = max(6, int(oldest_trade_line_months * float(rng.uniform(0.4, 0.8))))

    # DTI
    dti = round(emi_obligation / monthly_income, 2) if monthly_income > 0 else 0.5
    dti = max(0.05, min(0.80, dti))
    net_monthly_surplus = round(monthly_income - emi_obligation - avg_monthly_debit_6m * 0.3, 0)
    net_monthly_surplus = max(0, net_monthly_surplus)

    # Scores (0-1 floats correlated with bureau)
    base_g5 = (bureau_score - 300) / 600
    g5_score = round(max(0.1, min(0.99, base_g5 + float(rng.normal(0, 0.08)))), 2)
    base_g6 = (bureau_score - 300) / 600 * 0.9
    g6_score = round(max(0.1, min(0.99, base_g6 + float(rng.normal(0, 0.07)))), 2)

    # Sub-model scores
    g5_sub_scores = {
        "income_stability_model": round(max(0.1, min(0.99, g5_score + float(rng.normal(0, 0.05)))), 2),
        "transaction_behavior_model": round(max(0.1, min(0.99, g5_score + float(rng.normal(0, 0.06)))), 2),
        "repayment_capacity_model": round(max(0.1, min(0.99, g5_score + float(rng.normal(0, 0.05)))), 2),
        "salary_consistency_model": round(max(0.1, min(0.99, g5_score + float(rng.normal(0, 0.04)))), 2),
        "cashflow_surplus_model": round(max(0.1, min(0.99, g5_score + float(rng.normal(0, 0.06)))), 2),
    }
    g6_sub_scores = {
        "bureau_risk_model": round(max(0.1, min(0.99, g6_score + float(rng.normal(0, 0.05)))), 2),
        "fraud_detection_model": round(max(0.1, min(0.99, g6_score + float(rng.normal(0, 0.06)))), 2),
        "device_risk_model": round(max(0.1, min(0.99, g6_score + float(rng.normal(0, 0.07)))), 2),
        "behavioral_risk_model": round(max(0.1, min(0.99, g6_score + float(rng.normal(0, 0.05)))), 2),
        "credit_exposure_model": round(max(0.1, min(0.99, g6_score + float(rng.normal(0, 0.06)))), 2),
    }

    banking_stability_index = round(max(0.1, min(0.99, salary_consistency * 0.4 + g5_score * 0.3 + (1 - credit_utilization_ratio) * 0.3)), 2)
    income_stability_score = round(max(0.1, min(0.99, salary_consistency * 0.6 + float(rng.normal(0.15, 0.05)))), 2)
    transaction_volatility = round(max(0.05, min(0.95, float(rng.beta(2, 5)))), 2)

    credit_risk_band = "LOW" if bureau_score >= 750 else "MEDIUM" if bureau_score >= 650 else "HIGH"
    risk_segment = get_risk_segment(bureau_score)
    pricing_tier = get_pricing_tier(bureau_score, g5_score)

    # Max eligible amount
    max_eligible = round(monthly_income * float(rng.uniform(3, 8)) / 1000) * 1000
    max_eligible = max(desired_amount, max_eligible)
    recommended_tenure = int(rng.choice([12, 24, 36, 48, 60]))

    # Timestamps
    days_ago = int(rng.integers(0, 365))
    app_timestamp = datetime.utcnow() - timedelta(days=days_ago)
    decision_timestamp = app_timestamp + timedelta(minutes=int(rng.integers(5, 120)))

    # Decision
    decision_status = determine_decision(bureau_score, dti)

    # SPID
    spid = str(rng.integers(1000, 9999))

    # Annual income
    annual_income = round(monthly_income * 12, 0)
    ndi_amount = round(monthly_income - emi_obligation, 0)

    # Policy caps
    annual_amount_cap = round(max(200000, annual_income * float(rng.uniform(0.3, 0.5))) / 10000) * 10000
    ndi_cap = round(float(rng.choice([0.40, 0.45, 0.50])), 2)
    dti_cap = round(float(rng.choice([0.35, 0.40, 0.45])), 2)

    # ---- BUILD REQUEST PAYLOAD ----
    request_payload = {
        "loan_application_id": loan_app_id,
        "application_type": application_type,
        "repeat_type": repeat_type,
        "credit_policy": "PERSONAL",
        "credit_policy_version": "CP-PERSONAL-V3.2",
        "desired_amount": desired_amount,
        "application_timestamp": app_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "borrower_credit_model": {
            "customer_inputs": {
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
                "upi_transactions_3m": upi_txn_3m,
                "imps_transactions_3m": imps_txn_3m,
                "neft_transactions_3m": neft_txn_3m,
                "rtgs_transactions_3m": rtgs_txn_3m,
                "cash_deposits_6m": cash_deposits_6m,
                "cash_withdrawals_6m": cash_withdrawals_6m,
                "max_single_credit_3m": max_single_credit_3m,
                "max_single_debit_3m": max_single_debit_3m,
                "cheque_bounces_6m": cheque_bounces_6m,
                "low_balance_instances_6m": low_balance_instances_6m,
                "emi_auto_debits_per_month": emi_auto_debits,
                "emi_obligation_amount": emi_obligation,
                "loan_repayment_bounces_12m": loan_repayment_bounces_12m,
            },
            "bureau_credits": {
                "bureau_score": bureau_score,
                "bureau_source": bureau_source,
                "active_loans": active_loans,
                "closed_loans": closed_loans,
                "secured_loans": secured_loans,
                "unsecured_loans": unsecured_loans,
                "credit_cards_active": credit_cards_active,
                "total_credit_limit": total_credit_limit,
                "credit_utilization_ratio": credit_utilization_ratio,
                "overdue_accounts": overdue_accounts,
                "max_dpd_last_12m": max_dpd_12m,
                "inquiries_last_3m": inquiries_3m,
                "inquiries_last_12m": inquiries_12m,
                "oldest_trade_line_months": oldest_trade_line_months,
                "average_account_age_months": avg_account_age_months,
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
            "recommended_tenure_months": recommended_tenure,
            "risk_segment": risk_segment,
            "pricing_tier": pricing_tier,
        },
    }

    # ---- BUILD RESPONSE PAYLOAD ----

    # Generate choices
    choices = []
    if decision_status in ("APPROVED", "APPROVED_WITH_CONDITIONS"):
        num_offers = int(rng.integers(2, 5))
        for offer_idx in range(num_offers):
            amount_factor = float(rng.uniform(0.7, 1.05))
            offer_amount = round(desired_amount * amount_factor / 1000) * 1000
            offer_amount = max(10000, offer_amount)

            # Interest rate: better scores get better rates
            base_rate = 0.18 - (bureau_score - 300) / 600 * 0.10
            rate_variation = float(rng.uniform(-0.015, 0.015))
            interest_rate = round(max(0.085, min(0.24, base_rate + rate_variation)), 3)

            apr = round(interest_rate + float(rng.uniform(0.008, 0.02)), 3)
            maturity_months = int(rng.choice([12, 18, 24, 36, 48, 60]))
            loan_grade = get_loan_grade(bureau_score, rng)
            origination_rate = round(float(rng.uniform(0.01, 0.035)), 2)
            monthly_installment = compute_emi(offer_amount, interest_rate, maturity_months)

            dti_after = round(dti + (monthly_installment / monthly_income) if monthly_income > 0 else dti, 2)
            ndi_after = round(ndi_amount - monthly_installment, 0)

            reason_codes = pick_reason_codes(bureau_score, dti, g5_score, credit_utilization_ratio, rng)

            choices.append({
                "offer_id": f"OFFER-{offer_idx + 1}",
                "loan_amount": offer_amount,
                "interest_rate": interest_rate,
                "apr": apr,
                "maturity_months": maturity_months,
                "loan_grade": loan_grade,
                "origination_rate": origination_rate,
                "monthly_installment_estimate": monthly_installment,
                "dti_after_loan": dti_after,
                "ndi_after_loan": ndi_after,
                "reject_rules": [],
                "decision_reason_codes": reason_codes,
            })

    # Default offer
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
            "origination_rate": first["origination_rate"],
        }

    response_payload = {
        "loan_application_id": loan_app_id,
        "decision_status": decision_status,
        "application_type": application_type,
        "SPID": spid,
        "repeat_type": repeat_type,
        "credit_policy": "PERSONAL",
        "credit_policy_version": "CP-PERSONAL-V3.2",
        "desired_amount": desired_amount,
        "bureau_variables": {
            "bureau_source": bureau_source,
            "bureau_score": bureau_score,
            "risk_band": credit_risk_band,
            "active_loans": active_loans,
            "credit_utilization_ratio": credit_utilization_ratio,
            "recent_inquiries_3m": inquiries_3m,
            "oldest_trade_line_months": oldest_trade_line_months,
        },
        "calculated_attributes": {
            "g5_score": g5_score,
            "g6_score": g6_score,
            "monthly_income": monthly_income,
            "monthly_obligations": emi_obligation,
            "annual_income": annual_income,
            "ndi_amount": ndi_amount,
            "dti_amount": dti,
            "banking_stability_index": banking_stability_index,
        },
        "policy_caps": {
            "annual_amount_cap": annual_amount_cap,
            "ndi_cap": ndi_cap,
            "dti_cap": dti_cap,
        },
        "choices": choices,
        "default_offer": default_offer,
        "underwriting_metadata": {
            "decision_engine_version": "UW-ENGINE-5.4",
            "model_versions": {
                "g5_model": "v3.6",
                "g6_model": "v2.9",
            },
            "decision_timestamp": decision_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }

    # For rejected: add reject_rules to the response level (choices is empty [])
    if decision_status == "REJECTED":
        reject_rules = pick_reject_rules(bureau_score, dti, rng)
        response_payload["reject_rules"] = reject_rules

    return {
        "loan_application_id": loan_app_id,
        "request_payload": request_payload,
        "response_payload": response_payload,
        "created_at": app_timestamp,
    }


def generate_records(count: int = 2000) -> list[dict]:
    rng = np.random.default_rng(seed=42)
    records = []
    for i in range(1, count + 1):
        records.append(generate_single_record(i, rng))
    return records


async def main():
    force = "--force" in sys.argv

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

        print("Generating 2000 synthetic loan records...")
        records = generate_records(2000)

        for rec in records:
            db.add(LoanRecord(**rec))

        await db.commit()
        print(f"Seeded {len(records)} loan records successfully.")


if __name__ == "__main__":
    asyncio.run(main())
