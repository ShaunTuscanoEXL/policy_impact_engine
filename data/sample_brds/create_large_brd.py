"""Generate a large, realistic BRD (simulating 40+ pages) to stress-test extraction.

This creates BRD_Large_Comprehensive.docx with ~30-40 distinct rules spread across
multiple product lines, segments, and sections — typical of a quarterly policy overhaul.
"""

from docx import Document
from docx.shared import Pt
from pathlib import Path


def create_large_brd():
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # Title
    doc.add_heading("BRD-2026-Q2: Comprehensive Lending Policy Overhaul", level=0)
    doc.add_paragraph("Credit Policy Committee — Quarterly Review")
    doc.add_paragraph("Effective Date: May 1, 2026")
    doc.add_paragraph("Classification: Confidential")
    doc.add_paragraph("")

    # ─── Section 1: Executive Summary ───
    doc.add_heading("1.0 Executive Summary", level=1)
    doc.add_paragraph(
        "This document captures all lending policy changes approved during the Q2 2026 "
        "Credit Policy Committee meeting. The changes span personal loans, business loans, "
        "and top-up loans across all customer segments (salaried, self-employed, NRI). "
        "Key themes include tightening underwriting for high-risk segments, introducing "
        "geographic risk adjustments, implementing new fraud detection triggers, and "
        "revising pricing grids to reflect current cost of funds."
    )
    doc.add_paragraph(
        "This overhaul affects 37 distinct rules across eligibility, pricing, caps, "
        "thresholds, and scoring dimensions. All changes are mandatory and must be "
        "implemented in the decision engine by the effective date."
    )

    # ─── Section 2: Personal Loan — Eligibility ───
    doc.add_heading("2.0 Personal Loan — Eligibility Rules", level=1)

    doc.add_heading("2.1 Bureau Score Requirements", level=2)
    doc.add_paragraph(
        "The minimum bureau score for personal loan eligibility is revised as follows:\n"
        "• Salaried applicants: Minimum bureau score raised from 650 to 680\n"
        "• Self-employed applicants: Minimum bureau score raised from 680 to 720\n"
        "• NRI applicants: Minimum bureau score set at 750\n\n"
        "Applications below these thresholds must be auto-rejected with reason code "
        "'BUREAU_BELOW_SEGMENT_MINIMUM'."
    )

    doc.add_heading("2.2 Income Requirements by City Tier", level=2)
    table = doc.add_table(rows=5, cols=4)
    table.style = "Table Grid"
    for i, h in enumerate(["City Tier", "Salaried Min Income", "Self-Employed Min Income", "NRI Min Income"]):
        table.rows[0].cells[i].text = h
    data = [
        ("Tier 1 (Metro)", "₹30,000", "₹50,000", "₹75,000"),
        ("Tier 2", "₹25,000", "₹40,000", "₹60,000"),
        ("Tier 3", "₹20,000", "₹35,000", "₹50,000"),
        ("Tier 4 & Rural", "₹18,000", "₹30,000", "Not eligible"),
    ]
    for r, row_data in enumerate(data, 1):
        for c, val in enumerate(row_data):
            table.rows[r].cells[c].text = val

    doc.add_heading("2.3 Age Requirements", level=2)
    doc.add_paragraph(
        "Minimum age for personal loans is 21 years. Maximum age at loan maturity "
        "is 60 years for salaried and 65 years for self-employed.\n\n"
        "Applicants aged 21-24 are classified as 'Young Borrowers' and attract "
        "a 1.0% interest rate premium. Applicants above 55 require enhanced "
        "income verification and must be flagged for manual review."
    )

    doc.add_heading("2.4 Employment Stability", level=2)
    doc.add_paragraph(
        "• Salaried: Minimum 12 months with current employer, OR 24 months total "
        "employment history across last 3 employers\n"
        "• Self-employed: Minimum 36 months business vintage with ITR filings\n"
        "• NRI: Minimum 24 months with current overseas employer\n\n"
        "Applicants not meeting these criteria should be rejected with reason "
        "'INSUFFICIENT_EMPLOYMENT_STABILITY'."
    )

    # ─── Section 3: Personal Loan — Credit Behavior ───
    doc.add_heading("3.0 Personal Loan — Credit Behavior Gates", level=1)

    doc.add_heading("3.1 Delinquency Rules", level=2)
    doc.add_paragraph(
        "The following hard stops apply based on credit bureau delinquency indicators:\n\n"
        "Rule D-01: Max DPD > 60 days in last 12 months → Auto-reject\n"
        "Rule D-02: Max DPD > 30 days AND max DPD <= 60 days → Reduce eligible amount by 30%, "
        "flag for credit manager review\n"
        "Rule D-03: Any current overdue accounts (overdue_accounts > 0) → Auto-reject\n"
        "Rule D-04: More than 1 write-off in bureau history → Auto-reject\n"
        "Rule D-05: Settled accounts > 2 → Flag for manual review, reduce eligible "
        "amount by 20%"
    )

    doc.add_heading("3.2 Credit Inquiry Velocity", level=2)
    doc.add_paragraph(
        "Credit inquiry patterns indicate credit-seeking behavior:\n\n"
        "• More than 6 inquiries in last 3 months → Auto-reject (credit hungry)\n"
        "• 4-6 inquiries in last 3 months → Flag for enhanced due diligence\n"
        "• More than 10 inquiries in last 12 months → Auto-reject\n\n"
        "These rules apply across all product types and customer segments."
    )

    doc.add_heading("3.3 Existing Debt Load", level=2)
    doc.add_paragraph(
        "To prevent over-leveraging:\n\n"
        "• Active unsecured loans > 5 → Auto-reject\n"
        "• Active unsecured loans = 4-5 → Eligible amount reduced by 40%\n"
        "• Active unsecured loans = 3 → Eligible amount reduced by 15%\n"
        "• Total active loans (secured + unsecured) > 8 → Auto-reject\n\n"
        "Additionally, credit utilization ratio above 85% should trigger "
        "an auto-reject. Between 70-85% should reduce eligible amount by 25%."
    )

    doc.add_heading("3.4 Cheque / EMI Bounce Behavior", level=2)
    doc.add_paragraph(
        "Bounce history reflects payment discipline:\n\n"
        "• Cheque bounces in last 6 months > 3 → Auto-reject\n"
        "• Cheque bounces in last 6 months = 2-3 → Flag + reduce eligible by 25%\n"
        "• Loan repayment bounces in last 12 months > 2 → Auto-reject\n"
        "• Loan repayment bounces = 1-2 → Eligible amount reduced by 20%"
    )

    # ─── Section 4: Pricing Grid ───
    doc.add_heading("4.0 Interest Rate Pricing Grid", level=1)

    doc.add_paragraph("The tiered pricing model replaces the flat-rate system:")

    table2 = doc.add_table(rows=7, cols=4)
    table2.style = "Table Grid"
    for i, h in enumerate(["Risk Band", "Bureau Score Range", "Base Rate", "Effective Rate (with spread)"]):
        table2.rows[0].cells[i].text = h
    pricing = [
        ("Ultra-Prime", "800+", "9.5%", "10.5%"),
        ("Prime", "770-799", "10.5%", "11.5%"),
        ("Near-Prime", "740-769", "12.0%", "13.0%"),
        ("Standard", "710-739", "13.5%", "14.5%"),
        ("Sub-Standard", "680-709", "15.5%", "17.0%"),
        ("High-Risk", "650-679", "17.5%", "19.5%"),
    ]
    for r, row_data in enumerate(pricing, 1):
        for c, val in enumerate(row_data):
            table2.rows[r].cells[c].text = val

    doc.add_paragraph(
        "\nAdditional pricing adjustments:\n"
        "• Self-employed premium: +0.5% over base rate\n"
        "• Young borrower (age < 25) premium: +1.0%\n"
        "• NRI premium: +0.75%\n"
        "• Repeat customer with clean history discount: -0.5%\n"
        "• Maximum rate cap per RBI guidelines: 24.0% — any calculated rate "
        "exceeding this must be capped and flagged for compliance review\n"
        "• Loan amount > ₹15,00,000 with bureau score < 750: +0.25% risk premium"
    )

    # ─── Section 5: Amount Caps ───
    doc.add_heading("5.0 Loan Amount Caps & Exposure Limits", level=1)

    table3 = doc.add_table(rows=5, cols=4)
    table3.style = "Table Grid"
    for i, h in enumerate(["Segment", "Max Amount", "Max Multiplier (of income)", "Min Amount"]):
        table3.rows[0].cells[i].text = h
    caps = [
        ("Salaried - Tier 1", "₹25,00,000", "10x monthly income", "₹50,000"),
        ("Salaried - Tier 2/3", "₹15,00,000", "8x monthly income", "₹50,000"),
        ("Self-Employed", "₹10,00,000", "6x monthly income", "₹1,00,000"),
        ("NRI", "₹20,00,000", "8x monthly income", "₹2,00,000"),
    ]
    for r, row_data in enumerate(caps, 1):
        for c, val in enumerate(row_data):
            table3.rows[r].cells[c].text = val

    doc.add_paragraph(
        "\nThe eligible amount must be capped at the LOWER of:\n"
        "1. Segment maximum amount (table above)\n"
        "2. Income multiplier × monthly income\n"
        "3. Amount where EMI does not cause DTI to exceed the segment DTI cap\n\n"
        "If desired_amount exceeds any of these, set eligible_amount to the "
        "calculated maximum. Do NOT reject — approve for the lower amount."
    )

    # ─── Section 6: DTI & Affordability ───
    doc.add_heading("6.0 DTI Ratio & Affordability Rules", level=1)

    doc.add_paragraph(
        "Debt-to-income ratio caps by risk band:\n\n"
        "• Ultra-Prime / Prime (bureau >= 770): DTI cap at 55%\n"
        "• Near-Prime (bureau 740-769): DTI cap at 50%\n"
        "• Standard (bureau 710-739): DTI cap at 45%\n"
        "• Sub-Standard (bureau 680-709): DTI cap at 40%\n"
        "• Self-employed across all bands: DTI cap reduced by 5% from salaried\n\n"
        "Net monthly surplus after all EMIs (including proposed EMI) must be "
        "at least ₹10,000 for Tier 1 cities and ₹7,500 for Tier 2/3 cities. "
        "Applications failing this should be rejected with 'INSUFFICIENT_SURPLUS'."
    )

    # ─── Section 7: Banking Behavior ───
    doc.add_heading("7.0 Banking Behavior & Stability", level=1)

    doc.add_paragraph(
        "Banking behavior provides early warning signals:\n\n"
        "• Banking stability index < 0.50 → Auto-reject (severe instability)\n"
        "• Banking stability index 0.50-0.65 → Flag for review + reduce amount by 20%\n"
        "• Salary credit consistency < 60% (0.60) over 6 months → Auto-reject for salaried\n"
        "• Average monthly balance < 50% of EMI obligation → Flag for review\n"
        "• Account vintage < 6 months → Auto-reject (new account)\n"
        "• Low balance instances > 5 in last 6 months → Flag for review\n\n"
        "For self-employed, banking stability index minimum is 0.65 (higher bar)."
    )

    # ─── Section 8: Fraud & AML ───
    doc.add_heading("8.0 Fraud Detection & AML Triggers", level=1)

    doc.add_paragraph(
        "The following patterns must trigger fraud investigation holds:\n\n"
        "• Cash deposits in last 6 months > ₹10,00,000 → AML flag, hold for compliance\n"
        "• Transaction volatility index > 0.80 → Flag for fraud review\n"
        "• Monthly income stated > 3x of average salary credit → Income inflation flag\n"
        "• Multiple applications from same PAN in 30 days → Velocity flag, hold\n\n"
        "Flagged applications must NOT be auto-approved regardless of other criteria."
    )

    # ─── Section 9: Scoring Model ───
    doc.add_heading("9.0 Internal Scoring Model Thresholds", level=1)

    doc.add_paragraph(
        "Our internal scoring models (G5 and G6) provide additional risk signals:\n\n"
        "• G5 score < 400 → Auto-reject\n"
        "• G5 score 400-500 → Reduce eligible amount by 20%, flag for review\n"
        "• G5 score > 700 → Qualifies for premium pricing tier\n\n"
        "• G6 score < 450 → Auto-reject\n"
        "• G6 score 450-550 → Flag for enhanced review\n"
        "• G6 score > 750 → Additional 10% eligible amount increase\n\n"
        "Both G5 and G6 must be above their minimum thresholds. Failure on either "
        "triggers the corresponding action."
    )

    # ─── Section 10: Top-Up Loan Rules ───
    doc.add_heading("10.0 Top-Up Loan Specific Rules", level=1)

    doc.add_paragraph(
        "For top-up loans on existing personal loans:\n\n"
        "• Must have completed at least 12 EMI payments on existing loan\n"
        "• No DPD > 0 in last 6 months on existing loan\n"
        "• Top-up amount limited to 50% of original loan amount\n"
        "• Bureau score must be at or above original approval score\n"
        "• Interest rate for top-up = original rate + 0.5%\n"
        "• Not available for self-employed applicants with banking stability < 0.70"
    )

    # ─── Section 11: Geographic Risk ───
    doc.add_heading("11.0 Geographic Risk Adjustments", level=1)

    doc.add_paragraph(
        "Based on regional portfolio performance:\n\n"
        "• Tier 4 and rural areas: Maximum loan amount capped at ₹3,00,000\n"
        "• Tier 4: Employment tenure minimum increased to 36 months\n"
        "• Tier 4: Bureau score minimum increased to 720\n"
        "• High-default pin codes (list maintained separately): +1.5% rate premium, "
        "maximum amount reduced by 30%\n\n"
        "• Tier 1 metro applicants with bureau > 780 and income > ₹1,00,000: "
        "Eligible for express approval (bypass manual review)"
    )

    # ─── Section 12: Implementation ───
    doc.add_heading("12.0 Implementation & Timeline", level=1)

    doc.add_paragraph(
        "Phase 1 (Week 1-2): Rule engine configuration\n"
        "Phase 2 (Week 3): Integration testing with sample portfolio\n"
        "Phase 3 (Week 4): UAT with business stakeholders\n"
        "Phase 4 (Week 5): Shadow mode — parallel run with existing rules\n"
        "Phase 5 (Week 6): Production deployment with monitoring\n\n"
        "Rollback plan: Maintain ability to revert to previous rule set for 90 days."
    )

    # ─── Section 13: Approval ───
    doc.add_heading("13.0 Approval & Sign-Off", level=1)

    doc.add_paragraph(
        "This BRD has been reviewed and approved by:\n"
        "• Chief Risk Officer — Risk & Compliance\n"
        "• Head of Credit Policy — Underwriting\n"
        "• Chief Technology Officer — Implementation\n"
        "• Head of Products — Business Impact\n\n"
        "All changes are mandatory. Exceptions require CRO approval."
    )

    output = Path(__file__).parent / "BRD_Large_Comprehensive.docx"
    doc.save(str(output))
    print(f"Created: {output} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    create_large_brd()
