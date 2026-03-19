# Revamp Design: Loan Test Case Engine

**Date:** 2026-03-20
**Status:** Approved

## Overview

Revamp the Policy Impact Engine to focus on three core capabilities:
1. **BRD → Rules:** Upload any BRD document (structured or free-form) and extract lending rules via AI
2. **Loan Records Database:** A seeded PostgreSQL database of 2000+ loan application records stored as JSONB (request/response pairs)
3. **Test Case Generation with Customer Matching:** Generate test cases from extracted rules, then match real customers from the loan DB who satisfy each test case's conditions

## App Structure

### Pages

| Page | Purpose |
|------|---------|
| `/` | Dashboard — BRDs uploaded, rules generated, test suites, loan records stats |
| `/brds` | BRD list — upload BRDs, see extracted rule sets |
| `/brds/[id]` | BRD detail — workflow stepper: Extract → Review → Test Cases → Export |
| `/loan-records` | Loan DB browser — browse, search/filter, bulk-import CSV |
| `/loan-records/[id]` | Single loan record — full request/response JSON viewer |
| `/test-suites` | All test suites — list with export options |
| `/test-suites/[id]` | Test suite detail — test cases with matched customers |

### Navigation Sidebar
BRDs → Loan Records → Test Suites (3 items)

### Workflow Stepper (BRD Detail Page)
1. Upload BRD ✓
2. Extract Rules
3. Review & Approve Rules
4. Generate Test Cases (configurable counts, matches customers from loan DB)
5. Export / Download

### Removed Features
- Datasets page (replaced by Loan Records with CSV import)
- Simulations page
- Scenarios page
- Impact analysis
- Column mapping

## Data Model

### Kept Tables
- `brds` — id, filename, file_type, raw_text, created_at
- `rule_sets` — id, brd_id, name, status, created_at
- `rules` — id, rule_set_id, rule_id, rule_name, description, rule_type, conditions, actions, priority

### New Table: loan_records
```sql
CREATE TABLE loan_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_application_id VARCHAR UNIQUE NOT NULL,
    request_payload JSONB NOT NULL,
    response_payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- GIN indexes for JSONB queries
CREATE INDEX idx_loan_records_request ON loan_records USING GIN (request_payload);
CREATE INDEX idx_loan_records_response ON loan_records USING GIN (response_payload);

-- Specific path indexes for common queries
CREATE INDEX idx_loan_bureau_score ON loan_records (
    (request_payload->'borrower_credit_model'->'bureau_credits'->>'bureau_score')
);
```

### Modified Table: test_case_suites
- id, rule_set_id, total_cases, cases_by_category (JSONB), created_at

### Modified Table: test_cases
- id, suite_id, test_case_id, description, category
- `filter_logic` (JSONB) — conditions derived from rules, referencing input JSON paths
- `expected_outcome` (JSONB) — what should happen when conditions are met
- `matched_loan_ids` (JSONB array) — loan_application_ids from DB matching the filter
- created_at

### Deleted Tables
- datasets
- simulations
- simulation_results
- scenarios

## Loan Record JSON Structure

### Request Payload (Input)
```json
{
  "loan_application_id": "LA-91827364",
  "application_type": "DIGITAL",
  "repeat_type": "CONCURRENT",
  "credit_policy": "PERSONAL",
  "credit_policy_version": "CP-PERSONAL-V3.2",
  "desired_amount": 220000,
  "application_timestamp": "2026-03-10T13:05:12Z",
  "borrower_credit_model": {
    "customer_inputs": {
      "customer_id": "CUST-778921",
      "age": 32,
      "employment_type": "SALARIED",
      "employer_type": "PRIVATE",
      "monthly_income": 72000,
      "employment_tenure_months": 42,
      "residence_type": "RENTED",
      "city_tier": "TIER_1",
      "marital_status": "MARRIED",
      "dependents": 2
    },
    "banking_inputs": {
      "primary_bank_name": "ICICI Bank",
      "account_type": "SAVINGS",
      "account_vintage_months": 64,
      "current_account_balance": 91350,
      "average_monthly_balance_6m": 74200,
      "average_monthly_balance_12m": 68900,
      "monthly_salary_credit": 70500,
      "salary_credit_consistency_6m": 0.92,
      "average_monthly_credit_6m": 88200,
      "average_monthly_debit_6m": 64300,
      "total_credit_amount_6m": 529200,
      "total_debit_amount_6m": 385800,
      "inward_transactions_count_6m": 210,
      "outward_transactions_count_6m": 194,
      "upi_transactions_3m": 146,
      "imps_transactions_3m": 28,
      "neft_transactions_3m": 12,
      "rtgs_transactions_3m": 2,
      "cash_deposits_6m": 4,
      "cash_withdrawals_6m": 11,
      "max_single_credit_3m": 95000,
      "max_single_debit_3m": 52000,
      "cheque_bounces_6m": 0,
      "low_balance_instances_6m": 2,
      "emi_auto_debits_per_month": 2,
      "emi_obligation_amount": 15000,
      "loan_repayment_bounces_12m": 0
    },
    "bureau_credits": {
      "bureau_score": 748,
      "bureau_source": "CIBIL",
      "active_loans": 3,
      "closed_loans": 6,
      "secured_loans": 2,
      "unsecured_loans": 1,
      "credit_cards_active": 2,
      "total_credit_limit": 560000,
      "credit_utilization_ratio": 0.31,
      "overdue_accounts": 0,
      "max_dpd_last_12m": 0,
      "inquiries_last_3m": 2,
      "inquiries_last_12m": 5,
      "oldest_trade_line_months": 78,
      "average_account_age_months": 46
    }
  },
  "calculated_attributes": {
    "debt_to_income_ratio": 0.21,
    "net_monthly_surplus": 23500,
    "banking_stability_index": 0.86,
    "credit_risk_band": "LOW",
    "income_stability_score": 0.83,
    "transaction_volatility_index": 0.27,
    "scores": {
      "g5": {
        "score": 0.82,
        "model_version": "g5_v3.6",
        "sub_model_scores": { ... }
      },
      "g6": {
        "score": 0.75,
        "model_version": "g6_v2.9",
        "sub_model_scores": { ... }
      }
    }
  },
  "decision_context": {
    "policy_eligible": true,
    "max_eligible_amount": 250000,
    "recommended_tenure_months": 24,
    "risk_segment": "LOW_RISK",
    "pricing_tier": "TIER_2"
  }
}
```

### Response Payload (Output)
Contains: decision_status, bureau_variables, calculated_attributes, policy_caps, choices (multiple offers with rates/terms/reject_rules), default_offer, underwriting_metadata.

## Test Case Generation Flow

### Step 1: Extract Rules from BRD (existing)
AI extracts rules from any document format (structured tables, numbered clauses, free-form bullet points).

### Step 2: Map Rule Fields to Input JSON Paths
Field registry maps rule field names to JSONB paths:

```python
FIELD_REGISTRY = {
    "bureau_score": "borrower_credit_model.bureau_credits.bureau_score",
    "monthly_income": "borrower_credit_model.customer_inputs.monthly_income",
    "dti_ratio": "calculated_attributes.debt_to_income_ratio",
    "debt_to_income_ratio": "calculated_attributes.debt_to_income_ratio",
    "desired_amount": "desired_amount",
    "age": "borrower_credit_model.customer_inputs.age",
    "employment_type": "borrower_credit_model.customer_inputs.employment_type",
    "g5_score": "calculated_attributes.scores.g5.score",
    "g6_score": "calculated_attributes.scores.g6.score",
    "credit_utilization_ratio": "borrower_credit_model.bureau_credits.credit_utilization_ratio",
    "active_loans": "borrower_credit_model.bureau_credits.active_loans",
    # Auto-discovered from schema for remaining fields
}
```

Auto-discovery scans the JSON structure on startup and registers all leaf fields.

### Step 3: Generate Test Cases with Configurable Counts
User specifies per-category counts:

| Category | Default | Description |
|----------|---------|-------------|
| POSITIVE | 3 | All conditions satisfied |
| NEGATIVE | 3 | One condition violated per case |
| BOUNDARY | 5 | Values at exact thresholds |
| EDGE | 3 | Extreme values |
| INTERACTION | 2 | Cross-rule combinations |

### Step 4: Match Customers from Loan DB
For each test case, query loan_records using JSONB filters:

```sql
SELECT loan_application_id, request_payload, response_payload
FROM loan_records
WHERE (request_payload->'borrower_credit_model'->'bureau_credits'->>'bureau_score')::numeric >= 700
  AND (request_payload->'calculated_attributes'->>'debt_to_income_ratio')::numeric <= 0.40
ORDER BY ABS((request_payload->'borrower_credit_model'->'bureau_credits'->>'bureau_score')::numeric - 700) ASC
LIMIT 10;
```

Filter first (exact conditions), then rank by proximity to boundary values.

## Export Formats

### CSV Export (one row per test-case × matched-customer)
| Column | Example |
|--------|---------|
| test_case_id | TC-POS-001 |
| test_case_description | Bureau score above threshold with low DTI |
| category | POSITIVE |
| filter_logic | bureau_score >= 700 AND dti <= 0.40 |
| expected_outcome | APPROVED |
| loan_application_id | LA-91827364 |
| request_payload | Full input JSON (stringified) |
| response_payload | Full output JSON (stringified) |
| match_reason | bureau_score=748 (>=700), dti=0.21 (<=0.40) |

### JSON Export (structured)
```json
{
  "test_cases": [
    {
      "test_case_id": "TC-POS-001",
      "description": "...",
      "category": "POSITIVE",
      "filter_logic": [...],
      "expected_outcome": {...},
      "matched_customers": [
        {
          "loan_application_id": "LA-91827364",
          "request_payload": {...},
          "response_payload": {...},
          "match_reason": "..."
        }
      ]
    }
  ]
}
```

### Export Scopes
- **Per test suite:** All test cases + matched customers for a rule set
- **Per BRD:** All test suites across all rule sets for a BRD
- **Per test case:** Individual test case with its matched customers

## API Endpoints

### BRDs (keep existing)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/brds/upload` | Upload BRD document |
| GET | `/api/v1/brds` | List all BRDs |
| GET | `/api/v1/brds/{id}` | Get BRD detail |
| DELETE | `/api/v1/brds/{id}` | Delete BRD + cascade |
| POST | `/api/v1/brds/{id}/extract-rules` | Extract rules from BRD |

### Rules (keep existing)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/rules/{rule_set_id}` | Get rule set with rules |
| PUT | `/api/v1/rules/{rule_set_id}/approve` | Approve rule set |

### Loan Records (new)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/loan-records` | List records (paginated, filterable) |
| GET | `/api/v1/loan-records/{id}` | Get single record |
| GET | `/api/v1/loan-records/stats` | DB stats |
| POST | `/api/v1/loan-records/upload` | Bulk import from CSV |
| POST | `/api/v1/loan-records/seed` | Trigger re-seeding |

### Test Cases (revamped)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/test-cases/generate` | Generate with configurable counts |
| GET | `/api/v1/test-cases` | List all suites |
| GET | `/api/v1/test-cases/{suite_id}` | Suite with cases + matched customers |
| GET | `/api/v1/test-cases/{suite_id}/export/{format}` | Export suite (csv/json) |
| GET | `/api/v1/test-cases/by-brd/{brd_id}/export/{format}` | Export all for a BRD |
| DELETE | `/api/v1/test-cases/{suite_id}` | Delete suite |

### Removed Endpoints
- datasets, simulations, scenarios, pipeline, column-mapping

## Seed Data Generation

Generate 2000+ synthetic loan records with realistic distributions:
- Bureau scores: 300-900 (normal distribution centered at 700)
- Monthly income: 15,000-500,000 (log-normal)
- DTI ratios: 0.05-0.80
- Employment types: SALARIED (60%), SELF_EMPLOYED (25%), BUSINESS (15%)
- City tiers: TIER_1 (40%), TIER_2 (35%), TIER_3 (25%)
- Decision outcomes: APPROVED (45%), APPROVED_WITH_CONDITIONS (30%), REJECTED (25%)
- Multiple offer choices per approved application
- Realistic correlations (higher income → higher amounts, better scores → lower rates)

## Technical Decisions

- **Storage:** PostgreSQL JSONB with GIN indexes (schema-flexible, works with existing stack)
- **BRD parsing:** AI-driven, handles any format (structured, policy docs, bullet points)
- **Field mapping:** Auto-discovered registry from JSON schema + manual overrides
- **Customer matching:** Filter-based SQL + proximity ranking for boundary cases
- **Schema flexibility:** Current JSON structure used, designed for extensibility
