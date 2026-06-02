/**
 * field-glossary — Slice 5 plain-English data dictionary.
 *
 * Rule conditions and actions reference low-level loan-record fields
 * like `bureau_score`, `debt_to_income_ratio`, `decision_status`. A
 * policy-team viewer doesn't always know what those mean or what
 * sensible thresholds are, so every field with an entry here gets a
 * hover tooltip via the FieldHelp component.
 *
 * Adding a field: append an entry below. Keys MUST match the exact
 * `field` value the extractor emits (case-sensitive). For per-product
 * definitions, suffix the key with `__PERSONAL` or `__SECURED` etc.
 */

export interface FieldDefinition {
  /** Friendly label shown in the tooltip header. */
  label: string;
  /** 1-2 sentence plain-English description. */
  description: string;
  /** Typical observed range or category list. Free-form string. */
  range?: string;
  /** Source / where this gets computed in the loan pipeline. */
  source?: string;
  /** Type hint — drives the icon shown in the tooltip. */
  kind: "score" | "ratio" | "currency" | "categorical" | "boolean" | "decision";
}

const G: Record<string, FieldDefinition> = {
  // ── Bureau ─────────────────────────────────────────────────────────
  bureau_score: {
    label: "Bureau credit score",
    description:
      "Aggregated credit score pulled from the bureau at decision time.",
    range: "300–850 (300 worst, 850 best). Sub-prime ≤ 620, prime ≥ 720.",
    source: "borrower_credit_model.bureau_credits.bureau_score",
    kind: "score",
  },
  inquiries_last_3m: {
    label: "Hard inquiries in last 3 months",
    description: "Number of hard credit pulls on the borrower's file in the prior 90 days.",
    range: "0–10+. Three or more often signals credit-shopping risk.",
    source: "borrower_credit_model.bureau_credits.inquiries_last_3m",
    kind: "score",
  },

  // ── Income / employment ─────────────────────────────────────────────
  monthly_income: {
    label: "Monthly gross income",
    description: "Borrower-stated monthly gross (pre-tax) income in USD.",
    range: "$1,500 – $25,000. Median around $5,500.",
    source: "borrower_credit_model.customer_inputs.monthly_income",
    kind: "currency",
  },
  annual_income: {
    label: "Annual gross income",
    description: "Borrower-stated annual gross income (typically monthly_income × 12).",
    range: "$18K – $300K.",
    source: "borrower_credit_model.customer_inputs.annual_income",
    kind: "currency",
  },
  employment_status: {
    label: "Employment status",
    description: "Borrower's self-reported employment classification.",
    range: "EMPLOYED · SELF_EMPLOYED · UNEMPLOYED · RETIRED · STUDENT",
    source: "borrower_credit_model.customer_inputs.employment_status",
    kind: "categorical",
  },
  months_at_employer: {
    label: "Months at current employer",
    description: "Tenure (in months) at the borrower's stated current job.",
    range: "0–360+. Under 6 months often flagged for additional review.",
    kind: "score",
  },

  // ── DTI / capacity ─────────────────────────────────────────────────
  debt_to_income_ratio: {
    label: "Debt-to-income ratio (DTI)",
    description:
      "Total monthly debt payments ÷ gross monthly income, computed at decision time.",
    range:
      "0.0–1.5. Under 0.36 is comfortable, 0.36–0.43 acceptable, > 0.43 risky.",
    source: "calculated_attributes.debt_to_income_ratio",
    kind: "ratio",
  },
  dti_ratio: {
    label: "Debt-to-income ratio (DTI)",
    description: "Synonym for `debt_to_income_ratio`.",
    range: "0.0–1.5. Threshold ladders typically pivot at 0.36 / 0.43 / 0.50.",
    kind: "ratio",
  },

  // ── Loan request ───────────────────────────────────────────────────
  desired_amount: {
    label: "Requested loan amount (USD)",
    description: "Principal the borrower is asking for, before any cap or adjustment.",
    range: "$1,000 – $100,000.",
    source: "desired_amount",
    kind: "currency",
  },
  loan_term_months: {
    label: "Loan term (months)",
    description: "Repayment period the borrower selected.",
    range: "12 / 24 / 36 / 48 / 60 / 72 months.",
    kind: "score",
  },
  application_type: {
    label: "Application channel",
    description: "How the borrower submitted the application.",
    range: "DIGITAL · BRANCH · CALL_CENTER · PARTNER",
    kind: "categorical",
  },
  credit_policy: {
    label: "Credit policy product",
    description: "Which lending product the application is being scored against.",
    range: "PERSONAL · SECURED · STUDENT · AUTO · HOME_EQUITY",
    kind: "categorical",
  },

  // ── Decision context ───────────────────────────────────────────────
  risk_segment: {
    label: "Risk segment",
    description: "Pre-computed risk band the application falls into.",
    range: "PRIME · NEAR_PRIME · SUBPRIME · DEEP_SUBPRIME",
    source: "decision_context.risk_segment",
    kind: "categorical",
  },

  // ── Behavioural / fraud ────────────────────────────────────────────
  banking_avg_balance: {
    label: "Average bank balance (90d)",
    description: "Average end-of-day balance across the borrower's verified deposit accounts in the last 90 days.",
    range: "$0 – $250K+.",
    kind: "currency",
  },
  fraud_score: {
    label: "Fraud risk score",
    description: "Internal fraud-model score for this application. Higher = riskier.",
    range: "0.0 – 1.0. > 0.6 typically flagged for manual review.",
    kind: "score",
  },

  // ── Action targets ─────────────────────────────────────────────────
  decision_status: {
    label: "Final decision",
    description:
      "Terminal decision the engine emits for this application.",
    range: "APPROVED · REJECTED · FLAGGED",
    kind: "decision",
  },
  interest_rate: {
    label: "Offered APR",
    description: "Annual percentage rate the engine quotes the borrower.",
    range: "5% – 36% depending on product + risk segment.",
    kind: "ratio",
  },
  approved_amount: {
    label: "Approved loan amount",
    description: "Principal the engine is willing to lend (may differ from desired_amount).",
    range: "$0 – $100,000.",
    kind: "currency",
  },
};

const NORMALIZED: Record<string, string> = Object.fromEntries(
  Object.keys(G).map((k) => [k.toLowerCase(), k]),
);

/** Look up a field's definition. Case-insensitive; returns null when
 *  the field isn't in the glossary so the caller can render the
 *  raw token without a tooltip. */
export function lookupField(name: string | null | undefined): FieldDefinition | null {
  if (!name) return null;
  const key = NORMALIZED[name.toLowerCase()];
  return key ? G[key] : null;
}

/** Quick boolean for the wrapper component. */
export function hasGlossaryEntry(name: string | null | undefined): boolean {
  return lookupField(name) !== null;
}
