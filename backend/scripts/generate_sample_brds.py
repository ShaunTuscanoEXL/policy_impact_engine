"""
Generate 4 sample Business Requirement Documents (BRDs) as .docx files.

These BRDs simulate real corporate policy change requests for the
Policy Impact Engine. Each document contains clearly specified rules
with field names, operators, and threshold values so that an LLM-based
parser can extract structured conditions and actions.

Usage:
    python generate_sample_brds.py
"""

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from pathlib import Path
import datetime


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_brds"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_cell_shading(cell, color_hex: str):
    """Apply background shading to a table cell."""
    shading = cell._element.get_or_add_tcPr()
    shd = shading.makeelement(qn("w:shd"), {
        qn("w:fill"): color_hex,
        qn("w:val"): "clear",
    })
    shading.append(shd)


def _add_styled_paragraph(doc, text, style="Normal", bold=False,
                          font_size=None, alignment=None, space_after=None):
    """Add a paragraph with optional inline formatting."""
    p = doc.add_paragraph(style=style)
    run = p.add_run(text)
    if bold:
        run.bold = True
    if font_size:
        run.font.size = Pt(font_size)
    if alignment is not None:
        p.alignment = alignment
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    return p


def _add_heading(doc, text, level=1):
    """Add a numbered-style heading."""
    return doc.add_heading(text, level=level)


def _add_table(doc, headers, rows, col_widths=None):
    """Add a formatted table with header row shading."""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Header row
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _set_cell_shading(cell, "2F5496")

    # Data rows
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            cell = table.rows[r_idx + 1].cells[c_idx]
            cell.text = str(val)
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(10)
            if r_idx % 2 == 1:
                _set_cell_shading(cell, "D6E4F0")

    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Inches(w)

    doc.add_paragraph("")  # spacer
    return table


def _add_document_header(doc, doc_id, title, version, date_str, author,
                         department, status):
    """Add a professional document header block."""
    _add_styled_paragraph(doc, title, bold=True, font_size=18,
                          alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    _add_styled_paragraph(doc, "Business Requirement Document", bold=False,
                          font_size=12,
                          alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=12)

    meta_rows = [
        ("Document ID", doc_id),
        ("Version", version),
        ("Date", date_str),
        ("Author", author),
        ("Department", department),
        ("Status", status),
    ]
    table = doc.add_table(rows=len(meta_rows), cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (label, value) in enumerate(meta_rows):
        cell_l = table.rows[i].cells[0]
        cell_l.text = ""
        run_l = cell_l.paragraphs[0].add_run(label)
        run_l.bold = True
        run_l.font.size = Pt(10)
        _set_cell_shading(cell_l, "D6E4F0")
        cell_l.width = Inches(2.0)

        cell_r = table.rows[i].cells[1]
        cell_r.text = value
        for p in cell_r.paragraphs:
            for run in p.runs:
                run.font.size = Pt(10)
        cell_r.width = Inches(4.5)

    doc.add_paragraph("")  # spacer


def _add_approval_section(doc, approvers):
    """Add an approval table at the end of the document."""
    _add_heading(doc, "7.0 Approval", level=1)
    doc.add_paragraph(
        "This document requires approval from the following stakeholders "
        "before implementation may proceed."
    )
    headers = ["Name", "Role", "Signature", "Date"]
    rows = [(name, role, "", "") for name, role in approvers]
    _add_table(doc, headers, rows, col_widths=[2.0, 2.0, 1.5, 1.0])


# ---------------------------------------------------------------------------
# BRD-001  DTI Cap Tightening
# ---------------------------------------------------------------------------

def create_brd_001():
    doc = Document()

    _add_document_header(
        doc,
        doc_id="BRD-PL-2026-001",
        title="Personal Loan DTI Ratio Cap Revision\nand Bureau Score Threshold Update",
        version="1.0",
        date_str="2026-02-15",
        author="Michael Anderson, Senior Credit Policy Analyst",
        department="Credit Risk & Policy",
        status="Draft - Pending Approval",
    )

    # 1.0 Executive Summary
    _add_heading(doc, "1.0 Executive Summary", level=1)
    doc.add_paragraph(
        "This Business Requirement Document proposes targeted adjustments to "
        "the eligibility criteria governing unsecured personal loan origination. "
        "The primary changes involve tightening the maximum permissible "
        "debt-to-income (DTI) ratio and raising the minimum bureau score "
        "threshold for automatic approval. These revisions are designed to "
        "reduce portfolio-level default risk while maintaining adequate "
        "origination volume."
    )
    doc.add_paragraph(
        "Additionally, a new credit inquiry frequency cap is introduced to "
        "screen out applicants exhibiting credit-seeking behaviour that is "
        "correlated with elevated default probability. Together, these three "
        "rule changes are expected to improve the 90-day delinquency rate by "
        "approximately 80-120 basis points without materially impacting "
        "customer acquisition targets."
    )

    # 2.0 Background & Rationale
    _add_heading(doc, "2.0 Background & Rationale", level=1)
    doc.add_paragraph(
        "Analysis of the Q3-Q4 2025 portfolio performance reveals that "
        "personal loan delinquencies have increased by 1.4 percentage points "
        "year-over-year, with the most significant deterioration concentrated "
        "among borrowers whose DTI ratios fell between 0.36 and 0.40 at "
        "origination. Internal risk modelling suggests that tightening the "
        "DTI cap from 0.40 to 0.35 would have prevented approximately 22% "
        "of accounts that subsequently entered 90+ DPD status."
    )
    doc.add_paragraph(
        "Simultaneously, bureau-level data indicates that applicants with "
        "FICO scores in the 700-719 band exhibit a default rate 1.8x higher "
        "than those scoring 720 or above. Raising the floor to 720 aligns "
        "with peer-lender benchmarks observed in recent CFPB supervisory highlights."
    )

    # 3.0 Current State
    _add_heading(doc, "3.0 Current State", level=1)
    doc.add_paragraph(
        "The following eligibility rules are currently enforced in the "
        "personal loan underwriting engine:"
    )
    _add_table(doc,
               headers=["Rule", "Field", "Current Threshold", "Action"],
               rows=[
                   ["DTI Cap", "dti_ratio", "> 0.40", "REJECT"],
                   ["Bureau Score Floor", "bureau_score", "< 700", "REJECT"],
                   ["Inquiry Cap", "(not enforced)", "N/A", "N/A"],
               ],
               col_widths=[2.0, 1.8, 1.5, 1.2])

    # 4.0 Proposed Rule Changes
    _add_heading(doc, "4.0 Proposed Rule Changes", level=1)
    doc.add_paragraph(
        "The following rule modifications shall be applied to all personal "
        "loan applications where loan_type = \"PERSONAL\"."
    )

    # 4.1
    _add_heading(doc, "4.1 Reduce DTI Cap", level=2)
    doc.add_paragraph(
        "The maximum permissible debt-to-income ratio for unsecured personal "
        "loans shall be reduced from 0.40 to 0.35. Any application where the "
        "applicant's dti_ratio exceeds the new threshold will be automatically "
        "rejected."
    )
    _add_table(doc,
               headers=["Attribute", "Current Value", "Proposed Value"],
               rows=[
                   ["Field", "dti_ratio", "dti_ratio"],
                   ["Operator", ">", ">"],
                   ["Threshold", "0.40", "0.35"],
                   ["Action on Breach", "REJECT", "REJECT"],
                   ["Applies To", "loan_type = PERSONAL", "loan_type = PERSONAL"],
               ],
               col_widths=[2.0, 2.0, 2.0])

    # 4.2
    _add_heading(doc, "4.2 Increase Bureau Score Minimum", level=2)
    doc.add_paragraph(
        "The minimum FICO bureau score required for eligibility shall be "
        "increased from 700 to 720. Applications where bureau_score is below "
        "720 will be rejected. An FCRA-compliant adverse-action notice will "
        "be issued automatically for any rejected application."
    )
    _add_table(doc,
               headers=["Attribute", "Current Value", "Proposed Value"],
               rows=[
                   ["Field", "bureau_score", "bureau_score"],
                   ["Operator", "<", "<"],
                   ["Threshold", "700", "720"],
                   ["Action on Breach", "REJECT", "REJECT"],
               ],
               col_widths=[2.0, 2.0, 2.0])

    # 4.3
    _add_heading(doc, "4.3 Inquiry Frequency Cap", level=2)
    doc.add_paragraph(
        "A new rule shall be introduced to reject applications where the "
        "applicant has more than 3 credit inquiries recorded within the "
        "preceding 3-month period. This rule targets credit-seeking behaviour "
        "that is strongly correlated with near-term default."
    )
    _add_table(doc,
               headers=["Attribute", "Value"],
               rows=[
                   ["Field", "inquiries_last_3m"],
                   ["Operator", ">"],
                   ["Threshold", "3"],
                   ["Action on Breach", "REJECT"],
                   ["Effective Scope", "All personal loan applications"],
               ],
               col_widths=[2.5, 3.5])

    # 5.0 Expected Impact
    _add_heading(doc, "5.0 Expected Impact", level=1)
    doc.add_paragraph(
        "Based on back-testing against the Q3-Q4 2025 application dataset, "
        "the combined effect of the three proposed rule changes is estimated "
        "as follows:"
    )
    _add_table(doc,
               headers=["Metric", "Estimated Change"],
               rows=[
                   ["Approval Rate", "Decrease by 8-12 percentage points"],
                   ["90-Day Delinquency Rate", "Improve by 80-120 basis points"],
                   ["Portfolio Expected Loss", "Reduce by 15-20%"],
                   ["Average Borrower Credit Quality", "Improve (higher mean bureau score)"],
               ],
               col_widths=[3.0, 3.5])

    # 6.0 Implementation Timeline
    _add_heading(doc, "6.0 Implementation Timeline", level=1)
    _add_table(doc,
               headers=["Milestone", "Target Date"],
               rows=[
                   ["Policy Committee Approval", "2026-03-01"],
                   ["Rule Engine Configuration", "2026-03-10"],
                   ["UAT & Parallel Run", "2026-03-15 to 2026-03-25"],
                   ["Production Deployment", "2026-04-01"],
                   ["Post-Implementation Review", "2026-05-01"],
               ],
               col_widths=[3.5, 3.0])

    # 7.0 Approval
    _add_approval_section(doc, [
        ("Michael Anderson", "Senior Credit Policy Analyst"),
        ("Sarah Johnson", "Head of Credit Risk"),
        ("David Williams", "Chief Risk Officer"),
    ])

    out = OUTPUT_DIR / "BRD-001-DTI-Cap-Tightening.docx"
    doc.save(str(out))
    print(f"  Created: {out.name}")


# ---------------------------------------------------------------------------
# BRD-002  Income Verification Enhancement
# ---------------------------------------------------------------------------

def create_brd_002():
    doc = Document()

    _add_document_header(
        doc,
        doc_id="BRD-PL-2026-002",
        title="Enhanced Income and Banking Verification Standards\nfor High-Value Personal Loans",
        version="1.0",
        date_str="2026-02-20",
        author="Jennifer Martinez, Credit Policy Manager",
        department="Credit Risk & Policy",
        status="Draft - Pending Approval",
    )

    # 1.0 Executive Summary
    _add_heading(doc, "1.0 Executive Summary", level=1)
    doc.add_paragraph(
        "This document outlines proposed enhancements to the income and "
        "banking verification standards applied to personal loan applications. "
        "The changes focus on three areas: establishing a minimum income "
        "requirement for high-value loans, tightening the direct deposit "
        "consistency threshold, and introducing a banking stability floor."
    )
    doc.add_paragraph(
        "These measures are intended to strengthen the quality of income "
        "verification signals used in the underwriting process, particularly "
        "for larger loan exposures where the cost of default is proportionally "
        "higher. The changes build upon recent improvements in banking data "
        "availability through open banking aggregator (Plaid / MX / Finicity) "
        "integrations."
    )

    # 2.0 Background & Rationale
    _add_heading(doc, "2.0 Background & Rationale", level=1)
    doc.add_paragraph(
        "Post-pandemic lending data reveals a growing segment of borrowers "
        "who qualify on bureau score alone but whose income stability metrics "
        "indicate elevated repayment risk. In particular, high-value personal "
        "loans (above $7,500) originated to borrowers with monthly "
        "income below $8,000 have exhibited a 60+ DPD rate that is 2.3x "
        "the portfolio average."
    )
    doc.add_paragraph(
        "Furthermore, relaxed direct deposit consistency thresholds introduced during "
        "COVID concessions (0.80) have not been revisited despite a return to "
        "normalized labor market conditions. Restoring a higher threshold "
        "of 0.85 aligns with the pre-pandemic standard and is supported by "
        "current risk analytics."
    )

    # 3.0 Current State
    _add_heading(doc, "3.0 Current State", level=1)
    _add_table(doc,
               headers=["Rule", "Field(s)", "Current Threshold", "Action"],
               rows=[
                   ["Income Floor for High-Value Loans",
                    "monthly_income, desired_amount",
                    "(not enforced)", "N/A"],
                   ["Salary Credit Consistency",
                    "salary_credit_consistency_6m",
                    "< 0.80", "REJECT"],
                   ["Banking Stability Index",
                    "banking_stability_index",
                    "(not enforced)", "N/A"],
               ],
               col_widths=[2.0, 1.8, 1.3, 1.0])

    # 4.0 Proposed Rule Changes
    _add_heading(doc, "4.0 Proposed Rule Changes", level=1)

    # 4.1
    _add_heading(doc, "4.1 Minimum Income for High-Value Loans", level=2)
    doc.add_paragraph(
        "A new eligibility rule shall be introduced requiring that applicants "
        "requesting a loan amount (desired_amount) exceeding 7,500 must "
        "demonstrate a monthly_income of at least 8,000. Applications that "
        "do not meet this combined condition will be rejected."
    )
    _add_table(doc,
               headers=["Attribute", "Value"],
               rows=[
                   ["Condition", "desired_amount > 7500 AND monthly_income < 8000"],
                   ["Action", "REJECT"],
                   ["Rationale", "Ensure debt serviceability for large exposures"],
               ],
               col_widths=[2.0, 4.5])

    # 4.2
    _add_heading(doc, "4.2 Direct Deposit Consistency Requirement", level=2)
    doc.add_paragraph(
        "The minimum acceptable direct deposit consistency score over a "
        "trailing 6-month window shall be increased from 0.80 to 0.85. "
        "This metric measures the regularity and predictability of direct "
        "deposits into the applicant's primary bank account. Applications "
        "where salary_credit_consistency_6m is below 0.85 will be rejected."
    )
    _add_table(doc,
               headers=["Attribute", "Current Value", "Proposed Value"],
               rows=[
                   ["Field", "salary_credit_consistency_6m",
                    "salary_credit_consistency_6m"],
                   ["Operator", "<", "<"],
                   ["Threshold", "0.80", "0.85"],
                   ["Action on Breach", "REJECT", "REJECT"],
               ],
               col_widths=[2.0, 2.0, 2.0])

    # 4.3
    _add_heading(doc, "4.3 Banking Stability Floor", level=2)
    doc.add_paragraph(
        "A new minimum threshold shall be established for the banking "
        "stability index (banking_stability_index). This composite score "
        "reflects account tenure, average balance maintenance, and "
        "transaction regularity. Applications where the banking_stability_index "
        "is below 0.75 will be rejected."
    )
    _add_table(doc,
               headers=["Attribute", "Value"],
               rows=[
                   ["Field", "banking_stability_index"],
                   ["Operator", "<"],
                   ["Threshold", "0.75"],
                   ["Action on Breach", "REJECT"],
               ],
               col_widths=[2.5, 3.5])

    # 5.0 Expected Impact
    _add_heading(doc, "5.0 Expected Impact", level=1)
    doc.add_paragraph(
        "The proposed changes are expected to yield the following outcomes:"
    )
    _add_table(doc,
               headers=["Metric", "Estimated Change"],
               rows=[
                   ["Approval Rate (High-Value Segment)",
                    "Decrease by 5-8 percentage points"],
                   ["60+ DPD Rate (High-Value Segment)",
                    "Improve by 100-150 basis points"],
                   ["Income Verification Confidence",
                    "Increase from 78% to 88%"],
                   ["False Positive Rate (Income Fraud)",
                    "Reduce by approximately 30%"],
               ],
               col_widths=[3.0, 3.5])

    # 6.0 Implementation Timeline
    _add_heading(doc, "6.0 Implementation Timeline", level=1)
    _add_table(doc,
               headers=["Milestone", "Target Date"],
               rows=[
                   ["Policy Committee Approval", "2026-03-05"],
                   ["Open Banking Aggregator Data Validation", "2026-03-10"],
                   ["Rule Engine Configuration", "2026-03-15"],
                   ["UAT & Parallel Run", "2026-03-20 to 2026-03-30"],
                   ["Production Deployment", "2026-04-05"],
               ],
               col_widths=[3.5, 3.0])

    # 7.0 Approval
    _add_approval_section(doc, [
        ("Jennifer Martinez", "Credit Policy Manager"),
        ("Robert Chen", "VP - Risk Analytics"),
        ("Sarah Johnson", "Head of Credit Risk"),
    ])

    out = OUTPUT_DIR / "BRD-002-Income-Verification-Enhancement.docx"
    doc.save(str(out))
    print(f"  Created: {out.name}")


# ---------------------------------------------------------------------------
# BRD-003  Pricing Tier Restructure
# ---------------------------------------------------------------------------

def create_brd_003():
    doc = Document()

    _add_document_header(
        doc,
        doc_id="BRD-PL-2026-003",
        title="Risk-Based Pricing Tier Restructure\nfor Personal Loan Portfolio",
        version="1.0",
        date_str="2026-02-25",
        author="James Thompson, Pricing Strategy Lead",
        department="Product & Pricing",
        status="Draft - Pending Approval",
    )

    # 1.0 Executive Summary
    _add_heading(doc, "1.0 Executive Summary", level=1)
    doc.add_paragraph(
        "This document proposes a comprehensive restructuring of the "
        "risk-based pricing framework for the personal loan portfolio. "
        "The current 3-tier pricing model will be replaced with a granular "
        "5-tier structure that better differentiates borrower risk profiles "
        "and enables more competitive pricing for high-quality applicants."
    )
    doc.add_paragraph(
        "In addition, two targeted pricing adjustments are proposed: a "
        "premium tier rate reduction for top-tier borrowers to improve "
        "market competitiveness, and a multi-loan surcharge for borrowers "
        "carrying more than 2 active unsecured loans to compensate for "
        "concentration risk."
    )

    # 2.0 Background & Rationale
    _add_heading(doc, "2.0 Background & Rationale", level=1)
    doc.add_paragraph(
        "Competitive benchmarking reveals that the current 3-tier pricing "
        "model is insufficiently granular, resulting in cross-subsidisation "
        "between risk segments. High-quality borrowers (bureau score 750+) "
        "are offered rates that are 50-80 basis points above market, "
        "leading to attrition of the most profitable customer segment."
    )
    doc.add_paragraph(
        "Conversely, borrowers in the 680-719 bureau score band receive "
        "pricing that does not adequately reflect their risk profile. The "
        "proposed 5-tier structure addresses both issues while the multi-loan "
        "surcharge introduces a risk-appropriate loading for applicants with "
        "elevated unsecured credit exposure."
    )

    # 3.0 Current State
    _add_heading(doc, "3.0 Current State", level=1)
    doc.add_paragraph("The current pricing structure consists of 3 tiers:")
    _add_table(doc,
               headers=["Tier", "Bureau Score Range", "Base Interest Rate"],
               rows=[
                   ["Tier A", ">= 750", "0.115"],
                   ["Tier B", "700 - 749", "0.140"],
                   ["Tier C", "680 - 699", "0.165"],
               ],
               col_widths=[1.5, 2.5, 2.5])

    # 4.0 Proposed Rule Changes
    _add_heading(doc, "4.0 Proposed Rule Changes", level=1)

    # 4.1
    _add_heading(doc, "4.1 Premium Tier Rate Reduction", level=2)
    doc.add_paragraph(
        "Borrowers with a bureau_score of 750 or above shall receive a "
        "50 basis point (0.005) reduction to their applicable interest rate. "
        "This adjustment is applied as a post-calculation modifier to the "
        "base tier rate."
    )
    _add_table(doc,
               headers=["Attribute", "Value"],
               rows=[
                   ["Condition", "bureau_score >= 750"],
                   ["Action", "ADJUST interest_rate by -0.005"],
                   ["Type", "Rate modifier (subtracted from base rate)"],
               ],
               col_widths=[2.0, 4.5])

    # 4.2
    _add_heading(doc, "4.2 Multi-Loan Surcharge", level=2)
    doc.add_paragraph(
        "Borrowers who currently hold more than 2 active unsecured loans "
        "(unsecured_loans > 2) shall receive a 100 basis point (0.01) "
        "interest rate surcharge. This surcharge compensates for the "
        "elevated concentration risk associated with multiple unsecured "
        "credit exposures."
    )
    _add_table(doc,
               headers=["Attribute", "Value"],
               rows=[
                   ["Condition", "unsecured_loans > 2"],
                   ["Action", "ADJUST interest_rate by +0.01"],
                   ["Type", "Rate modifier (added to base rate)"],
               ],
               col_widths=[2.0, 4.5])

    # 4.3
    _add_heading(doc, "4.3 New 5-Tier Pricing Structure", level=2)
    doc.add_paragraph(
        "The existing 3-tier structure shall be replaced with the following "
        "5-tier pricing model. Each tier is defined by a bureau_score range "
        "and maps to a specific base interest rate:"
    )
    _add_table(doc,
               headers=["Tier", "Bureau Score Range", "Base Interest Rate"],
               rows=[
                   ["Tier 1 (Prime+)", "bureau_score >= 800", "0.105"],
                   ["Tier 2 (Prime)", "bureau_score 750 - 799", "0.120"],
                   ["Tier 3 (Near Prime)", "bureau_score 720 - 749", "0.135"],
                   ["Tier 4 (Standard)", "bureau_score 700 - 719", "0.155"],
                   ["Tier 5 (Sub-Standard)", "bureau_score 680 - 699", "0.175"],
               ],
               col_widths=[2.0, 2.5, 2.0])
    doc.add_paragraph(
        "Note: Applicants with a bureau_score below 680 remain ineligible "
        "under existing minimum score rules and are not assigned a pricing "
        "tier."
    )

    # 5.0 Expected Impact
    _add_heading(doc, "5.0 Expected Impact", level=1)
    _add_table(doc,
               headers=["Metric", "Estimated Change"],
               rows=[
                   ["Top-Tier Borrower Retention",
                    "Improve by 10-15%"],
                   ["Net Interest Margin (Portfolio)",
                    "Increase by 15-25 basis points"],
                   ["Risk-Adjusted Return on Capital",
                    "Improve by 8-12%"],
                   ["Competitive Position (750+ segment)",
                    "Move from P50 to P25 in market pricing"],
               ],
               col_widths=[3.0, 3.5])

    # 6.0 Implementation Timeline
    _add_heading(doc, "6.0 Implementation Timeline", level=1)
    _add_table(doc,
               headers=["Milestone", "Target Date"],
               rows=[
                   ["Pricing Committee Approval", "2026-03-10"],
                   ["Rate Engine Reconfiguration", "2026-03-15"],
                   ["Impact Simulation & Sign-off", "2026-03-20"],
                   ["Production Deployment", "2026-04-01"],
                   ["30-Day Performance Review", "2026-05-01"],
               ],
               col_widths=[3.5, 3.0])

    # 7.0 Approval
    _add_approval_section(doc, [
        ("James Thompson", "Pricing Strategy Lead"),
        ("Emily Rodriguez", "Head of Product"),
        ("David Williams", "Chief Risk Officer"),
    ])

    out = OUTPUT_DIR / "BRD-003-Pricing-Tier-Restructure.docx"
    doc.save(str(out))
    print(f"  Created: {out.name}")


# ---------------------------------------------------------------------------
# BRD-004  Post-COVID Risk Tightening
# ---------------------------------------------------------------------------

def create_brd_004():
    doc = Document()

    _add_document_header(
        doc,
        doc_id="BRD-PL-2026-004",
        title="Post-Pandemic Risk Mitigation Framework\nEnhanced Eligibility Criteria",
        version="1.0",
        date_str="2026-03-01",
        author="Sarah Johnson, Head of Credit Risk",
        department="Credit Risk & Policy",
        status="Urgent - Executive Review",
    )

    # 1.0 Executive Summary
    _add_heading(doc, "1.0 Executive Summary", level=1)
    doc.add_paragraph(
        "This document presents a comprehensive risk tightening framework "
        "designed to materially reduce portfolio exposure during the current "
        "period of macroeconomic uncertainty. The proposed rules represent "
        "the most significant eligibility revision since the onset of the "
        "COVID-19 pandemic and are intended to function as a temporary "
        "protective measure until credit conditions normalise."
    )
    doc.add_paragraph(
        "The framework introduces five rule changes spanning bureau score "
        "thresholds, DTI limits, employment tenure requirements, "
        "self-employed loan caps, and cash deposit scrutiny. Collectively, "
        "these changes are expected to increase the rejection rate by "
        "approximately 20-30 percentage points but will significantly "
        "improve portfolio resilience against projected economic headwinds."
    )
    doc.add_paragraph(
        "This is the strictest set of policy changes proposed in the current "
        "cycle and is designed to demonstrate the full impact of aggressive "
        "risk tightening on the loan portfolio."
    )

    # 2.0 Background & Rationale
    _add_heading(doc, "2.0 Background & Rationale", level=1)
    doc.add_paragraph(
        "Leading economic indicators suggest a potential contraction in "
        "consumer credit quality over the next 6-12 months. Key concerns "
        "include rising unemployment in the gig and 1099 economy, declining "
        "real wage growth, and an increase in household leverage ratios. "
        "The OCC Semiannual Risk Perspective has flagged personal loan "
        "portfolios as an area of supervisory focus."
    )
    doc.add_paragraph(
        "Internal stress-testing shows that under a moderate-adverse "
        "scenario, the existing eligibility criteria would result in a "
        "portfolio loss rate exceeding the risk appetite threshold by "
        "approximately 200 basis points. The proposed framework is "
        "calibrated to bring projected losses within acceptable bounds "
        "even under the severe-adverse scenario."
    )

    # 3.0 Current State
    _add_heading(doc, "3.0 Current State", level=1)
    _add_table(doc,
               headers=["Rule", "Field", "Current Threshold", "Action"],
               rows=[
                   ["Bureau Score Floor", "bureau_score", "< 700", "REJECT"],
                   ["DTI Cap", "dti_ratio", "> 0.40", "REJECT"],
                   ["Employment Tenure", "employment_tenure_months",
                    "(not enforced)", "N/A"],
                   ["Self-Employed Loan Cap", "desired_amount",
                    "(not enforced)", "N/A"],
                   ["Cash Deposit Scrutiny", "cash_deposits_6m",
                    "(not enforced)", "N/A"],
               ],
               col_widths=[2.0, 1.8, 1.3, 1.0])

    # 4.0 Proposed Rule Changes
    _add_heading(doc, "4.0 Proposed Rule Changes", level=1)
    doc.add_paragraph(
        "The following five rules shall be implemented simultaneously as "
        "part of the post-pandemic risk mitigation framework."
    )

    # 4.1
    _add_heading(doc, "4.1 Bureau Score Floor Raised", level=2)
    doc.add_paragraph(
        "The minimum FICO bureau score for personal loan eligibility "
        "shall be increased from 700 to 750. This is a significant "
        "tightening that will exclude a substantial portion of the "
        "current applicant pool but is deemed necessary given the "
        "projected deterioration in credit quality. Rejected applicants "
        "will receive an FCRA-compliant adverse-action notice."
    )
    _add_table(doc,
               headers=["Attribute", "Current Value", "Proposed Value"],
               rows=[
                   ["Field", "bureau_score", "bureau_score"],
                   ["Operator", "<", "<"],
                   ["Threshold", "700", "750"],
                   ["Action on Breach", "REJECT", "REJECT"],
               ],
               col_widths=[2.0, 2.0, 2.0])

    # 4.2
    _add_heading(doc, "4.2 DTI Cap Tightened", level=2)
    doc.add_paragraph(
        "The maximum permissible debt-to-income ratio shall be reduced "
        "from 0.40 to 0.30. This is the most aggressive DTI threshold in "
        "the institution's recent history and reflects the need to ensure "
        "borrowers maintain adequate income headroom for debt servicing "
        "under stress conditions."
    )
    _add_table(doc,
               headers=["Attribute", "Current Value", "Proposed Value"],
               rows=[
                   ["Field", "dti_ratio", "dti_ratio"],
                   ["Operator", ">", ">"],
                   ["Threshold", "0.40", "0.30"],
                   ["Action on Breach", "REJECT", "REJECT"],
               ],
               col_widths=[2.0, 2.0, 2.0])

    # 4.3
    _add_heading(doc, "4.3 Employment Tenure Minimum", level=2)
    doc.add_paragraph(
        "A new minimum employment tenure requirement of 24 months shall "
        "be introduced. Applicants whose employment_tenure_months is below "
        "24 will be rejected. This rule targets job-hopping behaviour and "
        "ensures a minimum level of employment stability."
    )
    _add_table(doc,
               headers=["Attribute", "Value"],
               rows=[
                   ["Field", "employment_tenure_months"],
                   ["Operator", "<"],
                   ["Threshold", "24"],
                   ["Action on Breach", "REJECT"],
               ],
               col_widths=[2.5, 3.5])

    # 4.4
    _add_heading(doc, "4.4 Self-Employed (1099) Loan Cap", level=2)
    doc.add_paragraph(
        "Self-employed (1099) applicants (employment_type == \"SELF_EMPLOYED_1099\") "
        "shall be subject to a maximum loan amount cap of $5,000. If a "
        "self-employed applicant requests a desired_amount exceeding "
        "5,000, the eligible_amount shall be set to 5,000 rather "
        "than rejecting the application outright."
    )
    _add_table(doc,
               headers=["Attribute", "Value"],
               rows=[
                   ["Condition",
                    "employment_type == \"SELF_EMPLOYED_1099\" AND desired_amount > 5000"],
                   ["Action", "SET eligible_amount to 5000"],
                   ["Type", "Amount cap (not a rejection)"],
               ],
               col_widths=[2.0, 4.5])

    # 4.5
    _add_heading(doc, "4.5 Cash Deposit Scrutiny", level=2)
    doc.add_paragraph(
        "Applications where the applicant has more than 10 cash deposits "
        "recorded in the preceding 6-month period (cash_deposits_6m > 10) "
        "shall be flagged for manual review. This rule does not result in "
        "automatic rejection but routes the application to a specialised "
        "review queue for enhanced due diligence."
    )
    _add_table(doc,
               headers=["Attribute", "Value"],
               rows=[
                   ["Condition", "cash_deposits_6m > 10"],
                   ["Action", "FLAG for_manual_review"],
                   ["Type", "Flag (routes to manual review queue)"],
               ],
               col_widths=[2.0, 4.5])

    # 5.0 Expected Impact
    _add_heading(doc, "5.0 Expected Impact", level=1)
    doc.add_paragraph(
        "This is the most aggressive tightening scenario and is expected "
        "to produce a significant shift in portfolio composition:"
    )
    _add_table(doc,
               headers=["Metric", "Estimated Change"],
               rows=[
                   ["Overall Approval Rate",
                    "Decrease by 20-30 percentage points"],
                   ["90-Day Delinquency Rate",
                    "Improve by 200-300 basis points"],
                   ["Portfolio Expected Loss",
                    "Reduce by 35-45%"],
                   ["Average Loan Ticket Size",
                    "Decrease by 15-20%"],
                   ["Manual Review Queue Volume",
                    "Increase by approximately 8-12%"],
               ],
               col_widths=[3.0, 3.5])

    # 6.0 Implementation Timeline
    _add_heading(doc, "6.0 Implementation Timeline", level=1)
    _add_table(doc,
               headers=["Milestone", "Target Date"],
               rows=[
                   ["Emergency Risk Committee Approval", "2026-03-15"],
                   ["Rule Engine Configuration", "2026-03-18"],
                   ["Accelerated UAT", "2026-03-20 to 2026-03-22"],
                   ["Production Deployment", "2026-03-25"],
                   ["Weekly Performance Monitoring", "Ongoing from 2026-03-25"],
                   ["Framework Review & Potential Relaxation", "2026-06-30"],
               ],
               col_widths=[3.5, 3.0])

    # 7.0 Approval
    _add_approval_section(doc, [
        ("Sarah Johnson", "Head of Credit Risk"),
        ("David Williams", "Chief Risk Officer"),
        ("Christopher Lee", "Managing Director - Retail Lending"),
        ("Board Risk Committee", "Governance"),
    ])

    out = OUTPUT_DIR / "BRD-004-Post-COVID-Risk-Tightening.docx"
    doc.save(str(out))
    print(f"  Created: {out.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Generating sample BRD documents...")
    create_brd_001()
    create_brd_002()
    create_brd_003()
    create_brd_004()
    print(f"\nGenerated 4 sample BRDs in {OUTPUT_DIR}")
