"""Seed script to generate 2000+ synthetic loan records."""
import asyncio
import sys
import random
import uuid
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import async_session
from app.models.loan_record import LoanRecord
from sqlalchemy import select, func


# --- Constants ---

EMPLOYMENT_TYPES = ["SALARIED", "SELF_EMPLOYED", "BUSINESS"]
EMPLOYMENT_WEIGHTS = [0.60, 0.25, 0.15]

CITY_TIERS = ["TIER_1", "TIER_2", "TIER_3"]
CITY_TIER_WEIGHTS = [0.40, 0.35, 0.25]

TIER_1_CITIES = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Pune", "Kolkata"]
TIER_2_CITIES = ["Jaipur", "Lucknow", "Chandigarh", "Ahmedabad", "Indore", "Bhopal", "Nagpur", "Coimbatore"]
TIER_3_CITIES = ["Ranchi", "Raipur", "Dehradun", "Mysore", "Udaipur", "Jodhpur", "Agra", "Varanasi"]

LOAN_PURPOSES = ["HOME_PURCHASE", "HOME_RENOVATION", "PERSONAL", "VEHICLE", "EDUCATION", "BUSINESS_EXPANSION"]

PRODUCT_TYPES = ["HOME_LOAN", "PERSONAL_LOAN", "LAP", "VEHICLE_LOAN", "EDUCATION_LOAN"]

MARITAL_STATUSES = ["MARRIED", "SINGLE", "DIVORCED", "WIDOWED"]
MARITAL_WEIGHTS = [0.55, 0.30, 0.10, 0.05]

GENDERS = ["MALE", "FEMALE"]
GENDER_WEIGHTS = [0.60, 0.40]

EDUCATION_LEVELS = ["POST_GRADUATE", "GRADUATE", "UNDER_GRADUATE", "DIPLOMA", "HIGH_SCHOOL"]
EDUCATION_WEIGHTS = [0.20, 0.40, 0.20, 0.10, 0.10]

REJECTION_REASONS = [
    "Bureau score below threshold",
    "DTI ratio exceeds maximum",
    "Insufficient income for requested amount",
    "Negative credit history detected",
    "Employment stability insufficient",
]


# --- Generators ---

def generate_bureau_score(rng: np.random.Generator) -> int:
    score = int(rng.normal(700, 80))
    return max(300, min(900, score))


def generate_monthly_income(rng: np.random.Generator) -> float:
    income = float(rng.lognormal(mean=10.8, sigma=0.6))
    return round(max(15000, min(500000, income)), 2)


def generate_age(rng: np.random.Generator) -> int:
    age = int(rng.normal(35, 8))
    return max(21, min(65, age))


def generate_dti(rng: np.random.Generator) -> float:
    dti = float(rng.beta(2, 5) * 0.75 + 0.05)
    return round(max(0.05, min(0.80, dti)), 2)


def generate_g5_score(bureau_score: int, rng: np.random.Generator) -> int:
    offset = int(rng.normal(0, 30))
    return max(300, min(900, bureau_score + offset))


def generate_g6_score(bureau_score: int, rng: np.random.Generator) -> int:
    offset = int(rng.normal(-10, 25))
    return max(300, min(900, bureau_score + offset))


def generate_desired_amount(monthly_income: float, rng: np.random.Generator) -> float:
    multiplier = rng.uniform(12, 60)
    amount = monthly_income * multiplier
    return round(max(50000, min(2000000, amount)), 0)


def generate_offers(bureau_score: int, desired_amount: float, monthly_income: float, rng: np.random.Generator) -> list:
    """Generate 2-4 offers for approved applications."""
    num_offers = rng.integers(2, 5)
    offers = []
    for i in range(num_offers):
        amount_factor = rng.uniform(0.7, 1.1)
        offered_amount = round(desired_amount * amount_factor, 0)

        # Better scores get better rates
        base_rate = 12.0 - (bureau_score - 300) * 0.01
        rate_variation = rng.uniform(-1.5, 1.5)
        interest_rate = round(max(6.5, min(18.0, base_rate + rate_variation)), 2)

        tenure_months = int(rng.choice([12, 24, 36, 48, 60, 72, 84, 120, 180, 240]))

        monthly_emi = round(
            offered_amount * (interest_rate / 1200) * (1 + interest_rate / 1200) ** tenure_months
            / ((1 + interest_rate / 1200) ** tenure_months - 1),
            2,
        )

        offers.append({
            "offer_id": f"OFF-{uuid.uuid4().hex[:8].upper()}",
            "offered_amount": offered_amount,
            "interest_rate": interest_rate,
            "tenure_months": tenure_months,
            "monthly_emi": monthly_emi,
            "processing_fee_pct": round(rng.uniform(0.5, 2.5), 2),
        })

    return offers


def determine_decision(bureau_score: int, dti: float, monthly_income: float) -> str:
    if bureau_score >= 700 and dti < 0.40:
        return "APPROVED"
    elif bureau_score >= 600 and dti <= 0.55:
        return "APPROVED_WITH_CONDITIONS"
    else:
        return "REJECTED"


def generate_single_record(index: int, rng: np.random.Generator) -> dict:
    loan_app_id = f"LA-{index:08d}"

    bureau_score = generate_bureau_score(rng)
    monthly_income = generate_monthly_income(rng)
    age = generate_age(rng)
    dti = generate_dti(rng)
    desired_amount = generate_desired_amount(monthly_income, rng)
    g5_score = generate_g5_score(bureau_score, rng)
    g6_score = generate_g6_score(bureau_score, rng)

    employment_type = rng.choice(EMPLOYMENT_TYPES, p=EMPLOYMENT_WEIGHTS)
    city_tier = rng.choice(CITY_TIERS, p=CITY_TIER_WEIGHTS)
    gender = rng.choice(GENDERS, p=GENDER_WEIGHTS)
    marital_status = rng.choice(MARITAL_STATUSES, p=MARITAL_WEIGHTS)
    education = rng.choice(EDUCATION_LEVELS, p=EDUCATION_WEIGHTS)
    loan_purpose = rng.choice(LOAN_PURPOSES)
    product_type = rng.choice(PRODUCT_TYPES)

    if city_tier == "TIER_1":
        city = rng.choice(TIER_1_CITIES)
    elif city_tier == "TIER_2":
        city = rng.choice(TIER_2_CITIES)
    else:
        city = rng.choice(TIER_3_CITIES)

    years_employed = max(0, int(rng.normal(age - 25, 3)))
    existing_obligations = round(float(monthly_income * dti), 2)

    # Random created_at within last 12 months
    days_ago = int(rng.integers(0, 365))
    created_at = datetime.utcnow() - timedelta(days=days_ago)

    # Build request payload
    request_payload = {
        "borrower_credit_model": {
            "customer_inputs": {
                "age": age,
                "gender": gender,
                "marital_status": marital_status,
                "education_level": education,
                "monthly_income": monthly_income,
                "employment_type": employment_type,
                "years_employed": years_employed,
                "existing_obligations": existing_obligations,
                "city": city,
                "city_tier": city_tier,
            },
            "bureau_credits": {
                "bureau_score": bureau_score,
                "g5_score": g5_score,
                "g6_score": g6_score,
                "total_accounts": int(rng.integers(1, 15)),
                "overdue_accounts": int(rng.integers(0, 4)) if bureau_score < 650 else 0,
                "credit_utilization_pct": round(float(rng.uniform(0.1, 0.9)), 2),
                "oldest_account_months": int(rng.integers(6, 240)),
                "recent_inquiries_6m": int(rng.integers(0, 8)),
            },
        },
        "loan_details": {
            "desired_amount": desired_amount,
            "loan_purpose": loan_purpose,
            "product_type": product_type,
            "requested_tenure_months": int(rng.choice([12, 24, 36, 48, 60, 120, 180, 240])),
        },
        "dti_ratio": dti,
    }

    # Determine decision
    decision_status = determine_decision(bureau_score, dti, monthly_income)

    # Build response payload
    response_payload: dict = {
        "decision_status": decision_status,
        "decision_timestamp": created_at.isoformat(),
        "risk_grade": (
            "A" if bureau_score >= 750 else
            "B" if bureau_score >= 700 else
            "C" if bureau_score >= 650 else
            "D" if bureau_score >= 600 else
            "E"
        ),
    }

    if decision_status in ("APPROVED", "APPROVED_WITH_CONDITIONS"):
        response_payload["offers"] = generate_offers(bureau_score, desired_amount, monthly_income, rng)
        if decision_status == "APPROVED_WITH_CONDITIONS":
            response_payload["conditions"] = [
                "Income proof required",
                "Additional collateral may be needed",
            ]
    else:
        reasons = rng.choice(REJECTION_REASONS, size=rng.integers(1, 3), replace=False).tolist()
        response_payload["rejection_reasons"] = reasons

    return {
        "loan_application_id": loan_app_id,
        "request_payload": request_payload,
        "response_payload": response_payload,
        "created_at": created_at,
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
