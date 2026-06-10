"""One-shot helper: turns the Repeat Customer Offer BRD text into a
.docx file so it can be uploaded via the BRDs API. Run once, then
upload the produced file via the UI or curl.
"""
from pathlib import Path
from docx import Document

OUT = Path(__file__).resolve().parents[1] / "data" / "uploads" / "BRD_Repeat_Customer_Offer_Framework.docx"
OUT.parent.mkdir(parents=True, exist_ok=True)

BRD_TEXT = """BUSINESS REQUIREMENTS DOCUMENT (BRD)
Repeat Customer Offer, Pricing & Experimentation Framework (V1.0)

Applies To: Existing / Repeat Customers
Scope: Offer Generation, Pricing Optimization, Risk Control, Experimentation

1. Objective

The objective of this framework is to:
- Provide enhanced loan offers to repeat customers based on demonstrated repayment behavior
- Enable controlled increase in exposure (ticket size)
- Introducing flexibility in pricing (coupon/APR) and tenure
- Drive higher conversion, retention, and portfolio profitability
- Continuously optimize strategy through Champion vs Challenger experimentation

The framework ensures:
- Strong customers are rewarded appropriately
- Risk is controlled through segmentation and affordability filters
- Decisioning remains consistent, explainable, and scalable

2. Definition of Repeat Good Customer

A repeat customer is classified as "Good" if all the following conditions are satisfied:
- repeat_type = REPEAT
- No missed or delayed repayments in recent loan history
- Stable or improving debt-to-income profile (debt_to_income_ratio <= 0.20)
- Positive and sustainable monthly surplus after obligations (net_monthly_surplus > 0)
- Consistent banking behavior and income flows (salary_credit_consistency_6m > 0.75)
- No adverse credit bureau signals in the last 12 months (overdue_accounts = 0)

3. Customer Segmentation (4-Tier Structure)

Customers are segmented into four groups based on credit quality, repayment capacity, and financial stability:

Segment A - Elite Customers
- Excellent credit profile
- Low leverage (low debt-to-income)
- High surplus income
- credit_risk_band = LOW
- Risk Profile: Low

Segment B - Prime Customers
- Strong creditworthiness
- Moderate leverage
- Stable income
- credit_risk_band = MEDIUM
- Risk Profile: Medium

Segment C - Near Prime Customers
- Moderate credit profile
- Higher leverage but manageable
- Improving repayment behavior
- credit_risk_band = HIGH
- Risk Profile: HIGH

4. Exposure (Loan Amount) Strategy

Repeat customers are eligible for enhanced loan eligibility compared to new customers.

Maximum Loan Eligibility Adjustment:
- Segment A: Up to 40% increase
- Segment B: Up to 25% increase
- Segment C: Up to 10% reduction

Key Principle:
- Exposure increases are not uniform
- They are strictly aligned with repayment capacity and past behavior

5. Tenure Flexibility Strategy

To improve affordability and enable higher ticket sizes:
- Segment A: Up to 72 months
- Segment B: Up to 60 months
- Segment C: Up to 36 months

Guideline:
- Tenure extension must ensure monthly payment remains affordable
- Longer tenure is primarily used for high-quality segments

6. Pricing Strategy (Coupon / APR Flexibility)

Repeat customers receive preferential pricing based on segment:
- Segment A: Significant reduction (up to ~2.5%)
- Segment B: Moderate reduction (up to ~1.5%)
- Segment C: No pricing benefit

Objective:
- Reward loyalty
- Improve acceptance rates
- Retain high-value customers
"""

doc = Document()
for para in BRD_TEXT.strip().split("\n"):
    p = para.strip()
    if not p:
        doc.add_paragraph("")
        continue
    if p[0].isdigit() and (". " in p[:4]):
        doc.add_heading(p, level=1)
    elif p.startswith("Segment ") and "-" in p[:25]:
        doc.add_heading(p, level=2)
    elif p.endswith(":") and len(p) < 80:
        doc.add_heading(p, level=3)
    elif p.startswith("- "):
        doc.add_paragraph(p[2:], style="List Bullet")
    else:
        doc.add_paragraph(p)

doc.save(OUT)
print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
