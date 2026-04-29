"""Heuristic subsystem classifier — assigns a Subsystem enum to a rule
based on its conditions, actions, and broad RuleType.

This is a fallback for rules where the LLM extractor didn't already
assign a subsystem. Once Phase 1 is fully wired, the LLM prompt itself
will tag rules with subsystems and this classifier will mainly act as
a validator.
"""
from __future__ import annotations

from app.models.rule import RuleType, Subsystem
from app.services.canonical_key import (
    action_class,
    normalize_field,
)


# Field-name → subsystem lookup. Most rules can be classified just by
# looking at the primary field. Fall through to RuleType-based defaults.
_FIELD_TO_SUBSYSTEM: dict[str, Subsystem] = {
    # Bureau
    "bureau_score": Subsystem.BUREAU_GATE,
    "fico_score": Subsystem.BUREAU_GATE,
    "cibil_score": Subsystem.BUREAU_GATE,
    "bureau_source": Subsystem.BUREAU_GATE,
    "active_loans": Subsystem.EXPOSURE_LIMIT,
    "unsecured_loans": Subsystem.EXPOSURE_LIMIT,
    "credit_cards_active": Subsystem.EXPOSURE_LIMIT,
    "total_credit_limit": Subsystem.EXPOSURE_LIMIT,
    "credit_utilization_ratio": Subsystem.BUREAU_GATE,
    "overdue_accounts": Subsystem.BUREAU_GATE,
    "max_dpd_last_12m": Subsystem.BUREAU_GATE,
    "inquiries_last_3m": Subsystem.BUREAU_GATE,
    "inquiries_last_12m": Subsystem.BUREAU_GATE,
    "settled_accounts": Subsystem.BUREAU_GATE,
    "write_offs": Subsystem.BUREAU_GATE,
    "bankruptcy_flag": Subsystem.BUREAU_GATE,
    "tax_lien_flag": Subsystem.BUREAU_GATE,
    "charge_offs_24m": Subsystem.BUREAU_GATE,

    # Income / DTI
    "monthly_income": Subsystem.INCOME_GATE,
    "annual_income": Subsystem.INCOME_GATE,
    "income": Subsystem.INCOME_GATE,
    "dti_ratio": Subsystem.DTI_GATE,
    "debt_to_income_ratio": Subsystem.DTI_GATE,
    "dti": Subsystem.DTI_GATE,
    "net_monthly_surplus": Subsystem.DTI_GATE,

    # Employment
    "employment_type": Subsystem.EMPLOYMENT_GATE,
    "employer_type": Subsystem.EMPLOYMENT_GATE,
    "employment_tenure_months": Subsystem.EMPLOYMENT_GATE,
    "employment_tenure": Subsystem.EMPLOYMENT_GATE,

    # Banking behavior
    "salary_credit_consistency_6m": Subsystem.BANKING_BEHAVIOR,
    "monthly_salary_credit": Subsystem.BANKING_BEHAVIOR,
    "average_monthly_balance_6m": Subsystem.BANKING_BEHAVIOR,
    "average_monthly_balance_12m": Subsystem.BANKING_BEHAVIOR,
    "current_account_balance": Subsystem.BANKING_BEHAVIOR,
    "account_vintage_months": Subsystem.BANKING_BEHAVIOR,
    "cheque_bounces_6m": Subsystem.BANKING_BEHAVIOR,
    "low_balance_instances_6m": Subsystem.BANKING_BEHAVIOR,
    "loan_repayment_bounces_12m": Subsystem.BANKING_BEHAVIOR,
    "banking_stability_index": Subsystem.BANKING_BEHAVIOR,
    "transaction_volatility_index": Subsystem.BANKING_BEHAVIOR,
    "income_stability_score": Subsystem.BANKING_BEHAVIOR,

    # Amount
    "desired_amount": Subsystem.AMOUNT_CAP,
    "max_eligible_amount": Subsystem.AMOUNT_CAP,
    "eligible_amount": Subsystem.AMOUNT_CAP,
    "loan_amount": Subsystem.AMOUNT_CAP,

    # Pricing
    "interest_rate": Subsystem.RATE_MODIFIER,
    "apr": Subsystem.RATE_MODIFIER,

    # Fraud
    "same_pan_applications_30d": Subsystem.FRAUD_SIGNAL,
    "geographic_risk_flag": Subsystem.FRAUD_SIGNAL,
    "cash_deposits_6m": Subsystem.FRAUD_SIGNAL,

    # Scoring
    "g5_score": Subsystem.SCORING_MODEL,
    "g6_score": Subsystem.SCORING_MODEL,
}


def _from_action(actions: list[dict] | None) -> Subsystem | None:
    """If the action targets a pricing/amount field, that overrides the
    field-based classification (a rule on bureau_score that ADJUSTs
    interest_rate is a RATE_MODIFIER, not a BUREAU_GATE)."""
    if not actions:
        return None
    first = actions[0] if isinstance(actions[0], dict) else {}
    target = normalize_field(first.get("target_field"))
    act_class = action_class(first.get("action_type"))

    if target in ("interest_rate", "apr"):
        # SET on a tier table → PRICING_TIER; ADJUST → RATE_MODIFIER
        return Subsystem.PRICING_TIER if act_class in ("CAP", "APPROVE") else Subsystem.RATE_MODIFIER
    if target in ("desired_amount", "eligible_amount", "max_eligible_amount", "loan_amount"):
        return Subsystem.AMOUNT_CAP
    if target == "decision_status" and act_class == "REJECT":
        return None  # let primary-field classification decide
    return None


def _from_rule_type(rule_type: RuleType | None) -> Subsystem:
    """Fallback: map broad RuleType to a default subsystem."""
    if rule_type is None:
        return Subsystem.UNCLASSIFIED
    return {
        RuleType.ELIGIBILITY: Subsystem.UNCLASSIFIED,  # too broad — needs field
        RuleType.PRICING: Subsystem.PRICING_TIER,
        RuleType.CAP: Subsystem.AMOUNT_CAP,
        RuleType.THRESHOLD: Subsystem.UNCLASSIFIED,
        RuleType.SCORING: Subsystem.SCORING_MODEL,
    }.get(rule_type, Subsystem.UNCLASSIFIED)


def classify(
    conditions: list[dict] | None,
    actions: list[dict] | None,
    rule_type: RuleType | None = None,
) -> Subsystem:
    """Assign a Subsystem to a rule.

    Resolution order:
      1. Action target (interest_rate/amount fields override field-based)
      2. Primary condition field lookup
      3. Any other condition field lookup (handles rules where the
         primary field is a guard like loan_type)
      4. Fallback to RuleType default
    """
    # 1. Action target wins when it points at a pricing/amount field —
    #    a "bureau >= 750 → ADJUST interest_rate" is RATE_MODIFIER, not
    #    BUREAU_GATE.
    by_action = _from_action(actions)
    if by_action is not None:
        return by_action

    # 2. First non-guard condition field. Guards (loan_type,
    #    application_type, …) commonly appear FIRST in LLM-extracted
    #    rules; walking the full list lets us pick the actual policy
    #    field rather than the scope filter.
    for cond in conditions or []:
        if not isinstance(cond, dict):
            continue
        field = normalize_field(cond.get("field"))
        if field in _FIELD_TO_SUBSYSTEM:
            return _FIELD_TO_SUBSYSTEM[field]

    # 3. RuleType default
    return _from_rule_type(rule_type)
