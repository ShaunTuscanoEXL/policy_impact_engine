"""Maps rule field names to JSON paths in the loan record request_payload.

The field registry provides two key functions:
1. resolve_field_path: Maps a rule condition field name (e.g., "bureau_score") to its
   JSON path within request_payload (e.g., "borrower_credit_model.bureau_credits.bureau_score")
2. json_path_to_sql: Converts a dot-separated path to a PostgreSQL JSONB accessor string
"""

# Manual registry for known field aliases (rule field name -> request_payload path)
FIELD_REGISTRY: dict[str, str] = {
    # Direct top-level fields
    "desired_amount": "desired_amount",
    "application_type": "application_type",
    "repeat_type": "repeat_type",
    "credit_policy": "credit_policy",
    # ── Guard-field aliases ─────────────────────────────────────────────
    # The LLM frequently emits scoping conditions like
    # `loan_type == "PERSONAL"` first in a rule. None of those guard
    # field names exist verbatim on the loan record, but their VALUES
    # match real top-level fields. Aliasing these makes the guard
    # condition evaluate truthfully so the rest of the rule chain
    # actually fires (otherwise the field-not-found path returns False
    # and the rule never matches anything).
    "loan_type":         "credit_policy",
    "product":           "credit_policy",
    "product_type":      "credit_policy",
    "loan_product":      "credit_policy",
    "borrower_segment":  "repeat_type",
    "customer_segment":  "repeat_type",
    "segment":           "repeat_type",
    "application_channel": "application_type",
    "channel":           "application_type",
    "purpose":           "loan_purpose",
    "loan_intent":       "loan_purpose",
    "currency":          "currency",
    "country":           "borrower_credit_model.customer_inputs.state",
    "state":             "borrower_credit_model.customer_inputs.state",
    "us_state":          "borrower_credit_model.customer_inputs.state",
    # ── Field-name variants ────────────────────────────────────────────
    "fico_score":        "borrower_credit_model.bureau_credits.bureau_score",
    "credit_score":      "borrower_credit_model.bureau_credits.bureau_score",
    "credit_bureau":     "borrower_credit_model.bureau_credits.bureau_source",
    "bureau":            "borrower_credit_model.bureau_credits.bureau_source",
    "salary":            "borrower_credit_model.customer_inputs.monthly_income",
    "monthly_salary":    "borrower_credit_model.customer_inputs.monthly_income",
    "gross_monthly_income": "borrower_credit_model.customer_inputs.monthly_income",
    "annual_salary":     "borrower_credit_model.customer_inputs.annual_income",
    "tenure":            "borrower_credit_model.customer_inputs.employment_tenure_months",
    "employer":          "borrower_credit_model.customer_inputs.employer_type",
    "employment":        "borrower_credit_model.customer_inputs.employment_type",
    "marital":           "borrower_credit_model.customer_inputs.marital_status",
    "city":              "borrower_credit_model.customer_inputs.city_tier",
    "loan_amount":       "desired_amount",
    "amount":            "desired_amount",
    "requested_amount":  "desired_amount",
    "principal":         "desired_amount",
    "loan_value":        "desired_amount",
    "inquiries_3m":      "borrower_credit_model.bureau_credits.inquiries_last_3m",
    "inquiries_12m":     "borrower_credit_model.bureau_credits.inquiries_last_12m",
    "credit_inquiries_3m": "borrower_credit_model.bureau_credits.inquiries_last_3m",
    "hard_inquiries_3m": "borrower_credit_model.bureau_credits.inquiries_last_3m",
    "max_dpd_12m":       "borrower_credit_model.bureau_credits.max_dpd_last_12m",
    "max_dpd":           "borrower_credit_model.bureau_credits.max_dpd_last_12m",
    "dpd":               "borrower_credit_model.bureau_credits.max_dpd_last_12m",
    "tradeline_age":     "borrower_credit_model.bureau_credits.oldest_trade_line_months",
    "credit_history_length": "borrower_credit_model.bureau_credits.oldest_trade_line_months",
    "revolving_utilization": "borrower_credit_model.bureau_credits.credit_utilization_ratio",
    "utilization":       "borrower_credit_model.bureau_credits.credit_utilization_ratio",
    "credit_util":       "borrower_credit_model.bureau_credits.credit_utilization_ratio",
    "nsf_returns_6m":    "borrower_credit_model.banking_inputs.cheque_bounces_6m",
    "nsf_count_6m":      "borrower_credit_model.banking_inputs.cheque_bounces_6m",
    "returned_items_6m": "borrower_credit_model.banking_inputs.cheque_bounces_6m",
    "bounced_payments_12m": "borrower_credit_model.banking_inputs.loan_repayment_bounces_12m",
    "loan_payment_bounces_12m": "borrower_credit_model.banking_inputs.loan_repayment_bounces_12m",
    "monthly_payment":   "borrower_credit_model.banking_inputs.emi_obligation_amount",
    "monthly_obligations": "borrower_credit_model.banking_inputs.emi_obligation_amount",
    "monthly_emi":       "borrower_credit_model.banking_inputs.emi_obligation_amount",
    "direct_deposit":    "borrower_credit_model.banking_inputs.monthly_salary_credit",
    "direct_deposit_consistency": "borrower_credit_model.banking_inputs.salary_credit_consistency_6m",
    "salary_consistency": "borrower_credit_model.banking_inputs.salary_credit_consistency_6m",
    "bankruptcy":        "borrower_credit_model.bureau_credits.bankruptcy_flag",
    "bankruptcy_filed":  "borrower_credit_model.bureau_credits.bankruptcy_flag",
    "tax_lien":          "borrower_credit_model.bureau_credits.tax_lien_flag",
    "charge_offs":       "borrower_credit_model.bureau_credits.charge_offs_24m",
    "active_credit_lines": "borrower_credit_model.bureau_credits.credit_cards_active",
    "credit_lines":      "borrower_credit_model.bureau_credits.credit_cards_active",
    "trade_lines":       "borrower_credit_model.bureau_credits.credit_cards_active",
    "open_loans":        "borrower_credit_model.bureau_credits.active_loans",
    # Calculated
    "ndi":               "calculated_attributes.net_monthly_surplus",
    "net_disposable_income": "calculated_attributes.net_monthly_surplus",
    "surplus":           "calculated_attributes.net_monthly_surplus",
    "risk_band":         "calculated_attributes.credit_risk_band",
    "risk_tier":         "calculated_attributes.credit_risk_band",

    # Customer inputs
    "age": "borrower_credit_model.customer_inputs.age",
    "monthly_income": "borrower_credit_model.customer_inputs.monthly_income",
    "income": "borrower_credit_model.customer_inputs.monthly_income",
    "employment_type": "borrower_credit_model.customer_inputs.employment_type",
    "employer_type": "borrower_credit_model.customer_inputs.employer_type",
    "employment_tenure_months": "borrower_credit_model.customer_inputs.employment_tenure_months",
    "employment_tenure": "borrower_credit_model.customer_inputs.employment_tenure_months",
    "residence_type": "borrower_credit_model.customer_inputs.residence_type",
    "city_tier": "borrower_credit_model.customer_inputs.city_tier",
    "marital_status": "borrower_credit_model.customer_inputs.marital_status",
    "dependents": "borrower_credit_model.customer_inputs.dependents",

    # Banking inputs
    "account_vintage_months": "borrower_credit_model.banking_inputs.account_vintage_months",
    "current_account_balance": "borrower_credit_model.banking_inputs.current_account_balance",
    "average_monthly_balance_6m": "borrower_credit_model.banking_inputs.average_monthly_balance_6m",
    "average_monthly_balance_12m": "borrower_credit_model.banking_inputs.average_monthly_balance_12m",
    "monthly_salary_credit": "borrower_credit_model.banking_inputs.monthly_salary_credit",
    "salary_credit_consistency_6m": "borrower_credit_model.banking_inputs.salary_credit_consistency_6m",
    "cheque_bounces_6m": "borrower_credit_model.banking_inputs.cheque_bounces_6m",
    "low_balance_instances_6m": "borrower_credit_model.banking_inputs.low_balance_instances_6m",
    "emi_auto_debits_per_month": "borrower_credit_model.banking_inputs.emi_auto_debits_per_month",
    "emi_obligation_amount": "borrower_credit_model.banking_inputs.emi_obligation_amount",
    "loan_repayment_bounces_12m": "borrower_credit_model.banking_inputs.loan_repayment_bounces_12m",

    # Bureau credits
    "bureau_score": "borrower_credit_model.bureau_credits.bureau_score",
    "cibil_score": "borrower_credit_model.bureau_credits.bureau_score",
    "active_loans": "borrower_credit_model.bureau_credits.active_loans",
    "closed_loans": "borrower_credit_model.bureau_credits.closed_loans",
    "secured_loans": "borrower_credit_model.bureau_credits.secured_loans",
    "unsecured_loans": "borrower_credit_model.bureau_credits.unsecured_loans",
    "credit_cards_active": "borrower_credit_model.bureau_credits.credit_cards_active",
    "total_credit_limit": "borrower_credit_model.bureau_credits.total_credit_limit",
    "credit_utilization_ratio": "borrower_credit_model.bureau_credits.credit_utilization_ratio",
    "overdue_accounts": "borrower_credit_model.bureau_credits.overdue_accounts",
    "max_dpd_last_12m": "borrower_credit_model.bureau_credits.max_dpd_last_12m",
    "inquiries_last_3m": "borrower_credit_model.bureau_credits.inquiries_last_3m",
    "inquiries_last_12m": "borrower_credit_model.bureau_credits.inquiries_last_12m",
    "oldest_trade_line_months": "borrower_credit_model.bureau_credits.oldest_trade_line_months",
    "average_account_age_months": "borrower_credit_model.bureau_credits.average_account_age_months",

    # Calculated attributes
    "dti_ratio": "calculated_attributes.debt_to_income_ratio",
    "debt_to_income_ratio": "calculated_attributes.debt_to_income_ratio",
    "dti": "calculated_attributes.debt_to_income_ratio",
    "net_monthly_surplus": "calculated_attributes.net_monthly_surplus",
    "banking_stability_index": "calculated_attributes.banking_stability_index",
    "credit_risk_band": "calculated_attributes.credit_risk_band",
    "income_stability_score": "calculated_attributes.income_stability_score",
    "transaction_volatility_index": "calculated_attributes.transaction_volatility_index",
    "g5_score": "calculated_attributes.scores.g5.score",
    "g6_score": "calculated_attributes.scores.g6.score",

    # Decision context
    "policy_eligible": "decision_context.policy_eligible",
    "max_eligible_amount": "decision_context.max_eligible_amount",
    "risk_segment": "decision_context.risk_segment",
    "pricing_tier": "decision_context.pricing_tier",
    "decision_status": "decision_context.decision_status",
    "interest_rate": "decision_context.interest_rate",

    # Bureau — additional
    "settled_accounts": "borrower_credit_model.bureau_credits.settled_accounts",
    "write_offs_bureau_history": "borrower_credit_model.bureau_credits.write_offs",
    "write_offs": "borrower_credit_model.bureau_credits.write_offs",

    # Banking — additional
    "cash_deposits_6m": "borrower_credit_model.banking_inputs.cash_deposits_6m",

    # Fraud / AML
    "same_pan_applications_30d": "borrower_credit_model.fraud_signals.same_pan_applications_30d",
    "geographic_risk_flag": "borrower_credit_model.fraud_signals.geographic_risk_flag",

    # Derived flags
    "employment_stability_passed": "calculated_attributes.employment_stability_passed",
    "exception_requested": "decision_context.exception_requested",
}


def resolve_field_path(field_name: str) -> str | None:
    """Resolve a rule field name to its JSON path in request_payload.

    Tries: exact match → normalized → alias lookup → substring match.
    Returns None only if no mapping exists.
    """
    # 1. Exact match
    if field_name in FIELD_REGISTRY:
        return FIELD_REGISTRY[field_name]

    # 2. Normalized match (lowercase, underscored)
    normalized = field_name.lower().strip().replace(" ", "_").replace("-", "_")
    if normalized in FIELD_REGISTRY:
        return FIELD_REGISTRY[normalized]

    # 3. Alias lookup — handles LLM field name variations
    from app.pipeline.rule_extractor import FIELD_ALIASES
    canonical = FIELD_ALIASES.get(normalized)
    if canonical and canonical in FIELD_REGISTRY:
        return FIELD_REGISTRY[canonical]

    # 4. Substring match — last resort for close matches
    for key, path in FIELD_REGISTRY.items():
        if normalized in key or key in normalized:
            return path

    return None


def json_path_to_sql(json_path: str) -> str:
    """Convert a dot-separated JSON path to PostgreSQL JSONB accessor.

    Example: 'borrower_credit_model.bureau_credits.bureau_score'
    Returns: "request_payload->'borrower_credit_model'->'bureau_credits'->>'bureau_score'"

    The final segment uses ->> (text extraction) for value comparison.
    """
    parts = json_path.split(".")
    if len(parts) == 1:
        return f"request_payload->>'{parts[0]}'"
    arrows = "->".join(f"'{p}'" for p in parts[:-1])
    return f"request_payload->{arrows}->>'{parts[-1]}'"


def auto_discover_fields(sample_payload: dict, prefix: str = "") -> dict[str, str]:
    """Walk a JSON payload and register all leaf fields not already in FIELD_REGISTRY.

    Returns a dict of {field_name: json_path} for newly discovered fields.
    """
    discovered = {}
    for key, value in sample_payload.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            discovered.update(auto_discover_fields(value, path))
        else:
            leaf_name = key.lower()
            if leaf_name not in FIELD_REGISTRY:
                discovered[leaf_name] = path
    return discovered


def get_all_fields() -> dict[str, str]:
    """Return a copy of the full field registry."""
    return dict(FIELD_REGISTRY)
