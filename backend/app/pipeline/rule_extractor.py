"""LLM-powered rule extractor.

Philosophy: The LLM does ALL the thinking. We give it the full document
text exactly as extracted (no reordering, no filtering, no labels) and
let it find every rule. Our code only handles:
  1. Building the LLM client
  2. Sending the prompt
  3. Parsing the JSON response
  4. Mapping field names to our registry (best-effort, not restrictive)

Key design decisions:
  - temperature=0 for deterministic, consistent output across runs
  - Full document text sent in original order (not split/filtered)
  - Field names are SUGGESTED, not enforced — LLM can use any name
  - Post-processing maps LLM field names to our registry where possible
  - Two-pass extraction for dense documents:
      Pass 1 (Enumerate): Lightweight scan to list every rule
      Pass 2 (Extract):   Batched detail extraction using the enumeration as checklist
  - Single-pass for smaller/simpler documents
  - Retry with backoff on API failures
"""

from __future__ import annotations

import json
import logging
import re
import time

from openai import AzureOpenAI, OpenAI

from app.config import settings
from app.pipeline.schemas import DocumentSection
from app.schemas.rule import Action, Condition, RuleDefinition, RuleTypeEnum

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2

# Token budget management
# GPT-4o: 128K context, 16K max output tokens
# Rough estimate: 1 token ≈ 4 chars for English text
CHARS_PER_TOKEN = 4
MAX_OUTPUT_TOKENS = 16384
MAX_INPUT_TOKENS = 100_000  # Leave headroom from 128K for system prompt + output
MAX_INPUT_CHARS = MAX_INPUT_TOKENS * CHARS_PER_TOKEN  # ~400K chars
CHUNK_OVERLAP_CHARS = 500  # Overlap between chunks to avoid splitting mid-rule

# ---------------------------------------------------------------------------
# Prompt — the entire brain of extraction lives here
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a senior lending policy analyst. You read Business Requirement Documents (BRDs) \
for banks and NBFCs, and you extract every business rule into structured JSON.

A "rule" is any statement that affects a lending decision:
- Eligibility criteria (who gets approved/rejected)
- Pricing rules (interest rate changes)
- Amount caps (maximum/minimum loan amounts)
- Threshold rules (minimum scores, maximum ratios)
- Scoring rules (risk band assignments, score cutoffs)
- Flags/reviews (conditions that trigger manual review)

IMPORTANT — read the entire document carefully:
- Rules can appear ANYWHERE: in tables, bullet points, paragraphs, even footnotes
- If the document describes "current state" vs "proposed changes", extract the PROPOSED rules
- Each distinct condition-action pair is a separate rule
- A table row with a threshold and an action is a rule
- "Applications with X should be Y" is a rule
- If a rule applies only to a segment (e.g., self-employed, Tier 3 cities), \
encode the segment as a condition

CRITICAL — TIERED TABLES MUST BE SPLIT INTO INDEPENDENT RULES:
A table that maps score / amount / income BANDS to different OUTPUT VALUES
(e.g., "score 680-719 → 16.99%, score 720-749 → 14.99%, …") is N RULES,
not one rule with N OR'd conditions and N actions. NEVER combine tier
rows. Each row gets its own rule with ONE condition and ONE action.

WRONG (do NOT do this):
{
  "rule_id": "RULE-002", "rule_name": "Tiered Interest Rate",
  "conditions": [
    {"field":"bureau_score","operator":"between","value":[680,719],"logic":"OR"},
    {"field":"bureau_score","operator":"between","value":[720,749],"logic":"OR"},
    {"field":"bureau_score","operator":">=","value":800,"logic":"OR"}
  ],
  "actions": [
    {"action_type":"SET","target_field":"interest_rate","value":0.1699,...},
    {"action_type":"SET","target_field":"interest_rate","value":0.1499,...},
    {"action_type":"SET","target_field":"interest_rate","value":0.0999,...}
  ]
}
This collapses the table — every loan would receive ALL the SET actions
and the engine would simply keep the last value, defeating the tiers.

RIGHT (emit one rule per tier row):
[
  {"rule_id":"RULE-002A","rule_name":"Interest Rate — Tier 680-719",
   "conditions":[{"field":"bureau_score","operator":"between","value":[680,719]}],
   "actions":[{"action_type":"SET","target_field":"interest_rate","value":0.1699,...}]},
  {"rule_id":"RULE-002B","rule_name":"Interest Rate — Tier 720-749",
   "conditions":[{"field":"bureau_score","operator":"between","value":[720,749]}],
   "actions":[{"action_type":"SET","target_field":"interest_rate","value":0.1499,...}]},
  {"rule_id":"RULE-002C","rule_name":"Interest Rate — Tier 800+",
   "conditions":[{"field":"bureau_score","operator":">=","value":800}],
   "actions":[{"action_type":"SET","target_field":"interest_rate","value":0.0999,...}]}
]

For each rule, return a JSON object:

{
  "rule_id": "RULE-001",
  "rule_name": "Short name (e.g., Minimum Bureau Score)",
  "description": "What this rule does and why, in plain English",
  "rule_type": "ELIGIBILITY | PRICING | CAP | THRESHOLD | SCORING",
  "conditions": [
    {
      "field": "bureau_score",
      "operator": ">= | <= | > | < | == | != | in | not_in | between",
      "value": 680,
      "logic": "AND | OR"
    }
  ],
  "actions": [
    {
      "action_type": "SET | REJECT | ADJUST | FLAG",
      "target_field": "decision_status",
      "value": "REJECTED",
      "description": "Human-readable description of the action"
    }
  ],
  "priority": 1,
  "source_section": "Which part of the document this came from",
  "confidence": 0.95
}

FIELD NAME GUIDANCE (use these when they fit, but you may use other descriptive names too):
bureau_score, dti_ratio, monthly_income, employment_type, employment_tenure_months,
active_loans, unsecured_loans, credit_utilization_ratio, inquiries_last_3m,
salary_credit_consistency_6m, banking_stability_index, desired_amount, cash_deposits_6m,
city_tier, max_dpd_last_12m, cheque_bounces_6m, age, residence_type,
account_vintage_months, overdue_accounts, net_monthly_surplus, credit_risk_band,
g5_score, g6_score, interest_rate, eligible_amount, decision_status,
loan_repayment_bounces_12m, repeat_type, closed_loans, transaction_volatility_index

For ratio/percentage fields: use decimals (40% = 0.40), not whole numbers.
For currency: use raw numbers without symbols (₹5,00,000 = 500000).

CONFIDENCE:
- 0.95-1.0: Explicitly stated with exact numbers
- 0.85-0.94: Clearly stated but some interpretation needed
- 0.70-0.84: Implied or partially ambiguous
- Below 0.70: Inferred from context

RULE RETIREMENTS (optional but valuable when present):
If the BRD explicitly retires/replaces an existing rule, ALSO emit a
"retires_pattern" object on the rule that supersedes it. Signals to look for:
  - "previously enforced", "currently set to", "is replaced by"
  - "Current State" tables that show old rules being modified
  - "no longer enforced", "deprecated", "removed in this revision"
  - A tier table (e.g. 3-tier) being replaced wholesale by another (e.g. 5-tier)
Shape:
  "retires_pattern": {
    "subsystem": "DTI_GATE | BUREAU_GATE | PRICING_TIER | ...",
    "field": "dti_ratio",
    "operator_class": "GT | LT | EQ | RANGE | IN",
    "basis": "explicit_replacement | supersedes_full_table | deprecated",
    "evidence_section": "Section 4.1"
  }
The retirement is about the OLD rule being removed; the rule object itself
describes the NEW rule that takes its place.

Return ONLY a JSON array. No markdown fences. No explanations. Just [...].
"""

# ---------------------------------------------------------------------------
# Two-pass prompts — for dense documents with many rules
# ---------------------------------------------------------------------------

ENUMERATE_PROMPT = """\
You are a senior lending policy analyst. You read Business Requirement Documents (BRDs) \
and identify every single business rule.

A "rule" is any statement that affects a lending decision:
- Eligibility criteria (who gets approved/rejected)
- Pricing rules (interest rate changes)
- Amount caps (maximum/minimum loan amounts)
- Threshold rules (minimum scores, maximum ratios)
- Scoring rules (risk band assignments, score cutoffs)
- Flags/reviews (conditions that trigger manual review or fraud hold)
- Geographic adjustments (city tier or region-specific rules)
- Segment-specific overrides (different rules per customer type)
- Behavioral gates (delinquency, bounce history, inquiry velocity)

IMPORTANT:
- Each DISTINCT condition-action pair is a SEPARATE rule
- A table row with a threshold and an action is a rule
- "If X then Y" is a rule, even if buried in a paragraph
- Segment-specific variations are separate rules (e.g., "bureau >= 680 for salaried" \
and "bureau >= 720 for self-employed" are TWO rules)
- Pricing tiers: each tier row is a separate rule
- DO NOT merge or consolidate — enumerate EVERY individual rule

Return a JSON array of lightweight rule summaries:
[
  {"rule_id": "R001", "rule_name": "Short name", "source_section": "Section heading or number"},
  ...
]

Return ONLY the JSON array. No markdown fences. No explanations.
"""

DETAIL_EXTRACT_PROMPT = """\
You are a senior lending policy analyst. I will give you a BRD document and a list of \
rules that were identified in it. For EACH listed rule, extract the full structured details.

You MUST produce output for EVERY rule in the list. Do not skip, merge, or consolidate any rules.

For each rule, return:
{
  "rule_id": "RULE-001",
  "rule_name": "Short name",
  "description": "What this rule does and why",
  "rule_type": "ELIGIBILITY | PRICING | CAP | THRESHOLD | SCORING",
  "conditions": [
    {"field": "bureau_score", "operator": ">= | <= | > | < | == | != | in | not_in | between", "value": 680, "logic": "AND | OR"}
  ],
  "actions": [
    {"action_type": "SET | REJECT | ADJUST | FLAG", "target_field": "decision_status", "value": "REJECTED", "description": "Human-readable description"}
  ],
  "priority": 1,
  "source_section": "Which part of the document",
  "confidence": 0.95
}

FIELD NAME GUIDANCE (use these when they fit, but you may use other descriptive names too):
bureau_score, dti_ratio, monthly_income, employment_type, employment_tenure_months,
active_loans, unsecured_loans, credit_utilization_ratio, inquiries_last_3m,
salary_credit_consistency_6m, banking_stability_index, desired_amount, cash_deposits_6m,
city_tier, max_dpd_last_12m, cheque_bounces_6m, age, residence_type,
account_vintage_months, overdue_accounts, net_monthly_surplus, credit_risk_band,
g5_score, g6_score, interest_rate, eligible_amount, decision_status,
loan_repayment_bounces_12m, repeat_type, closed_loans, transaction_volatility_index

For ratio/percentage fields: use decimals (40% = 0.40), not whole numbers.
For currency: use raw numbers without symbols (₹5,00,000 = 500000).

CONFIDENCE:
- 0.95-1.0: Explicitly stated with exact numbers
- 0.85-0.94: Clearly stated but some interpretation needed
- 0.70-0.84: Implied or partially ambiguous

Return ONLY a JSON array. No markdown fences. No explanations. Just [...].
"""

# Threshold: if enumeration finds more than this many rules, use two-pass
TWO_PASS_RULE_THRESHOLD = 15
# Batch size for detail extraction in pass 2
DETAIL_BATCH_SIZE = 20


def _build_client():
    """Build the LLM client based on provider configuration."""
    if settings.llm_provider.lower() == "azure":
        if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
            logger.error("Azure OpenAI: missing API key or endpoint")
            return None, None
        client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        model = settings.azure_openai_deployment
        logger.info("LLM: Azure OpenAI (%s)", model)
    else:
        if not settings.openai_api_key:
            logger.error("OpenAI: missing API key")
            return None, None
        client = OpenAI(api_key=settings.openai_api_key)
        model = settings.openai_model
        logger.info("LLM: OpenAI (%s)", model)
    return client, model


# ---------------------------------------------------------------------------
# JSON parsing — multiple fallback strategies
# ---------------------------------------------------------------------------

def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _parse_json(response_text: str) -> list[dict]:
    """Parse JSON array from LLM response with multiple fallbacks."""
    cleaned = _strip_fences(response_text)

    # 1. Direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    return val
            return [data]
    except json.JSONDecodeError:
        pass

    # 2. Find outermost JSON array
    match = re.search(r"\[.*]", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            # Try fixing trailing commas
            fixed = re.sub(r",\s*([}\]])", r"\1", match.group())
            try:
                data = json.loads(fixed)
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

    # 3. Find individual rule objects
    objects = []
    for m in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned):
        try:
            obj = json.loads(m.group())
            if isinstance(obj, dict) and ("rule_id" in obj or "rule_name" in obj):
                objects.append(obj)
        except json.JSONDecodeError:
            continue
    if objects:
        return objects

    logger.error("JSON parse failed. First 500 chars: %s", cleaned[:500])
    return []


# ---------------------------------------------------------------------------
# Rule post-processing
# ---------------------------------------------------------------------------

# Common aliases the LLM might use → our canonical field names
FIELD_ALIASES: dict[str, str] = {
    "cibil_score": "bureau_score",
    "credit_score": "bureau_score",
    "fico_score": "bureau_score",
    "income": "monthly_income",
    "salary": "monthly_income",
    "monthly_salary": "monthly_income",
    "dti": "dti_ratio",
    "debt_to_income_ratio": "dti_ratio",
    "debt_to_income": "dti_ratio",
    "employment_tenure": "employment_tenure_months",
    "tenure_months": "employment_tenure_months",
    "loan_amount": "desired_amount",
    "requested_amount": "desired_amount",
    "amount": "desired_amount",
    "dpd": "max_dpd_last_12m",
    "max_dpd": "max_dpd_last_12m",
    "dpd_last_12m": "max_dpd_last_12m",
    "inquiries": "inquiries_last_3m",
    "credit_inquiries": "inquiries_last_3m",
    "credit_inquiries_last_3m": "inquiries_last_3m",
    "cheque_bounces": "cheque_bounces_6m",
    "bounces": "cheque_bounces_6m",
    "cash_deposits": "cash_deposits_6m",
    "account_vintage": "account_vintage_months",
    "banking_stability": "banking_stability_index",
    "salary_consistency": "salary_credit_consistency_6m",
    "salary_credit_consistency": "salary_credit_consistency_6m",
    "utilization_ratio": "credit_utilization_ratio",
    "credit_utilization": "credit_utilization_ratio",
    "surplus": "net_monthly_surplus",
    "risk_band": "credit_risk_band",
    "volatility_index": "transaction_volatility_index",
    "transaction_volatility": "transaction_volatility_index",
    "repayment_bounces": "loan_repayment_bounces_12m",
    "loan_repayment_bounces": "loan_repayment_bounces_12m",
    "emi_bounces": "loan_repayment_bounces_12m",
    "customer_type": "repeat_type",
    "borrower_type": "repeat_type",
    "application_type": "repeat_type",
}

# Fields where the value is a ratio (0-1) but LLM might return whole numbers
RATIO_FIELDS = {
    "dti_ratio", "credit_utilization_ratio", "salary_credit_consistency_6m",
    "banking_stability_index", "income_stability_score", "transaction_volatility_index",
}


def _normalize_field(raw: str) -> str:
    """Normalize a field name: lowercase, underscore, then alias lookup."""
    clean = raw.lower().strip().replace(" ", "_").replace("-", "_")
    return FIELD_ALIASES.get(clean, clean)


def _normalize_value(value, field: str):
    """Normalize a value — handle string numbers, percentages, currency.

    Also normalizes list elements for between/in/not_in operators.
    """
    if value is None:
        return value

    # Normalize list elements individually (for between, in, not_in)
    if isinstance(value, list):
        return [_normalize_value(elem, field) for elem in value]

    # String → number
    if isinstance(value, str):
        # Remove currency symbols and commas: "₹5,00,000" → "500000"
        cleaned = re.sub(r"[₹$€,\s]", "", value)
        # Handle percentage strings: "40%" → 0.40 for ratio fields
        if cleaned.endswith("%"):
            try:
                num = float(cleaned[:-1])
                if field in RATIO_FIELDS:
                    return num / 100.0
                return num
            except ValueError:
                pass
        try:
            if "." in cleaned:
                return float(cleaned)
            return int(cleaned)
        except ValueError:
            return value

    # Whole number → decimal for ratio fields
    if field in RATIO_FIELDS and isinstance(value, (int, float)) and value > 1:
        return value / 100.0

    return value


def _coerce_rule_type(raw) -> RuleTypeEnum:
    """Map any string to a RuleTypeEnum. Never returns None — always picks one."""
    if raw is None:
        return RuleTypeEnum.THRESHOLD

    raw_upper = str(raw).strip().upper()
    try:
        return RuleTypeEnum(raw_upper)
    except ValueError:
        pass

    for member in RuleTypeEnum:
        if member.value in raw_upper:
            return member

    keyword_map = {
        "QUALIFICATION": RuleTypeEnum.ELIGIBILITY,
        "APPROVAL": RuleTypeEnum.ELIGIBILITY,
        "REJECTION": RuleTypeEnum.ELIGIBILITY,
        "DECLINE": RuleTypeEnum.ELIGIBILITY,
        "RATE": RuleTypeEnum.PRICING,
        "INTEREST": RuleTypeEnum.PRICING,
        "FEE": RuleTypeEnum.PRICING,
        "LIMIT": RuleTypeEnum.CAP,
        "MAXIMUM": RuleTypeEnum.CAP,
        "MINIMUM": RuleTypeEnum.THRESHOLD,
        "FLOOR": RuleTypeEnum.THRESHOLD,
        "CEILING": RuleTypeEnum.CAP,
        "SCORE": RuleTypeEnum.SCORING,
        "RISK": RuleTypeEnum.SCORING,
        "BAND": RuleTypeEnum.SCORING,
    }
    for kw, rt in keyword_map.items():
        if kw in raw_upper:
            return rt

    return RuleTypeEnum.THRESHOLD


def _normalize_action_type(raw: str) -> str:
    """Normalize action types to our 4 canonical types."""
    upper = raw.strip().upper()
    mapping = {
        "SET": "SET", "APPROVE": "SET", "ACCEPT": "SET", "ASSIGN": "SET",
        "REJECT": "REJECT", "DENY": "REJECT", "DECLINE": "REJECT",
        "ADJUST": "ADJUST", "MODIFY": "ADJUST", "CHANGE": "ADJUST",
        "UPDATE": "ADJUST", "REDUCE": "ADJUST", "INCREASE": "ADJUST", "CAP": "ADJUST",
        "FLAG": "FLAG", "ALERT": "FLAG", "WARN": "FLAG", "REVIEW": "FLAG",
    }
    return mapping.get(upper, "FLAG")


def _fan_out_tiers(rules: list[RuleDefinition]) -> list[RuleDefinition]:
    """Detect collapsed-tier rules and split them into N independent rules.

    LLMs frequently read a tiered pricing/cap/limit table (e.g. four
    bureau-score bands each mapping to its own interest rate) and
    cram all four rows into a single rule with N OR'd conditions and
    N actions — which is semantic nonsense because every loan would
    fire all N actions and the engine would just keep the last value.

    Heuristic: a rule is a fan-out candidate when ALL of these hold:
      1. It has K >= 2 conditions on the SAME field, joined by OR.
         (Or K >= 2 SET-style actions on the same target plus exactly
         K conditions in some shape.)
      2. It has M >= 2 actions, all SET/ADJUST/CAP on the SAME
         target field with DIFFERENT values.
      3. K == M (we can pair condition[i] with action[i] 1:1).

    When all three hold, the rule is split into K rules — each with
    one condition and one action — preserving the original rule_name
    plus a tier suffix and inheriting description/priority/source.

    Idempotent: runs through every rule, returns a (possibly longer)
    list. Rules that don't match the pattern pass through unchanged.
    """
    if not rules:
        return rules

    SET_LIKE = {"SET", "ADJUST", "CAP"}
    out: list[RuleDefinition] = []
    fanout_count = 0

    for rule in rules:
        conds = list(rule.conditions or [])
        actions = list(rule.actions or [])

        # Skip if too few of either to be a tier table
        if len(conds) < 2 or len(actions) < 2:
            out.append(rule)
            continue

        # All actions must be SET-like, on the same target, with
        # distinct values — otherwise this isn't a tiered output.
        first_action = actions[0]
        if first_action.action_type not in SET_LIKE:
            out.append(rule)
            continue
        if not all(
            a.action_type == first_action.action_type
            and a.target_field == first_action.target_field
            for a in actions
        ):
            out.append(rule)
            continue
        action_values = [a.value for a in actions]
        if len(set(map(str, action_values))) != len(action_values):
            # Duplicate action values — not a true tier table
            out.append(rule)
            continue

        # All conditions must be on the same field, joined by OR.
        cond_fields = {c.field for c in conds}
        if len(cond_fields) != 1:
            out.append(rule)
            continue
        # Look at the OR/AND logic of conditions 2..N. If any is "AND",
        # this isn't a pure tier table (might be a guard + tier set).
        cond_logics = [str(c.logic or "AND").upper() for c in conds[1:]]
        if any(l != "OR" for l in cond_logics):
            out.append(rule)
            continue

        if len(conds) != len(actions):
            # Counts mismatch — can't pair 1:1, leave alone
            out.append(rule)
            continue

        # All checks passed — fan out.
        fanout_count += 1
        for tier_idx, (cond, act) in enumerate(zip(conds, actions), start=1):
            tier_label = _describe_condition_tier(cond)
            new_name = f"{rule.rule_name} — Tier {tier_idx} ({tier_label})"
            # Force this single condition to logic=AND (it's standalone now)
            new_cond = cond.model_copy(update={"logic": "AND"})
            tier_rule = rule.model_copy(update={
                "rule_id": f"{rule.rule_id}-T{tier_idx}",
                "rule_name": new_name,
                "description": (
                    rule.description
                    + f" (Tier {tier_idx}/{len(conds)}: {tier_label})"
                    if rule.description
                    else f"Tier {tier_idx}/{len(conds)}: {tier_label}"
                ),
                "conditions": [new_cond],
                "actions": [act],
            })
            out.append(tier_rule)

    if fanout_count:
        logger.info(
            "Fanned out %d collapsed-tier rule(s) into %d total rules.",
            fanout_count,
            len(out) - (len(rules) - fanout_count),
        )
    return out


def _describe_condition_tier(cond) -> str:
    """Compact human label for a single condition, used in tier rule names.
    Examples: '680-719' for between, '>= 800' for scalar, 'in [...]' for in."""
    op = str(cond.operator or "").lower()
    val = cond.value
    if op == "between" and isinstance(val, (list, tuple)) and len(val) == 2:
        return f"{val[0]}-{val[1]}"
    if op in ("in", "not_in") and isinstance(val, (list, tuple)):
        return f"{op} [{', '.join(str(v) for v in val)}]"
    return f"{cond.operator} {val}"


def _parse_rule(d: dict, index: int) -> RuleDefinition | None:
    """Parse a single rule dict from the LLM into a RuleDefinition."""
    try:
        rule_type = _coerce_rule_type(d.get("rule_type"))

        # Conditions
        conditions = []
        for c in d.get("conditions", []):
            if not isinstance(c, dict):
                continue
            field = _normalize_field(str(c.get("field", "")))
            if not field:
                continue
            value = _normalize_value(c.get("value"), field)
            conditions.append(Condition(
                field=field,
                operator=str(c.get("operator", "==")),
                value=value,
                logic=str(c.get("logic", "AND")).upper(),
            ))

        # Actions
        actions = []
        for a in d.get("actions", []):
            if not isinstance(a, dict):
                continue
            actions.append(Action(
                action_type=_normalize_action_type(str(a.get("action_type", "FLAG"))),
                target_field=_normalize_field(str(a.get("target_field", ""))),
                value=a.get("value"),
                description=str(a.get("description", "")),
            ))

        # If LLM gave conditions but no actions, generate a sensible default
        if conditions and not actions:
            if rule_type == RuleTypeEnum.ELIGIBILITY:
                actions = [Action(action_type="REJECT", target_field="decision_status",
                                  value="REJECTED", description="Does not meet eligibility criteria")]
            elif rule_type == RuleTypeEnum.PRICING:
                actions = [Action(action_type="ADJUST", target_field="interest_rate",
                                  value=0, description="Interest rate adjustment")]
            elif rule_type == RuleTypeEnum.CAP:
                actions = [Action(action_type="ADJUST", target_field="eligible_amount",
                                  value=0, description="Amount cap applied")]
            else:
                actions = [Action(action_type="FLAG", target_field="decision_status",
                                  value="REVIEW", description="Flagged for review")]

        rule_id = str(d.get("rule_id", f"RULE-{index:03d}"))
        if not rule_id.startswith("RULE"):
            rule_id = f"RULE-{index:03d}"

        return RuleDefinition(
            rule_id=rule_id,
            rule_name=str(d.get("rule_name", "Unnamed Rule")),
            description=str(d.get("description", "")),
            rule_type=rule_type,
            conditions=conditions,
            actions=actions,
            priority=int(d.get("priority", index)),
            source_section=str(d.get("source_section", "")),
            confidence=float(d.get("confidence", 0.8)),
        )
    except Exception as exc:
        logger.warning("Failed to parse rule #%d: %s", index, exc)
        return None


# ---------------------------------------------------------------------------
# LLM call with truncation handling
# ---------------------------------------------------------------------------

def _call_llm(client, model: str, messages: list[dict]) -> str:
    """Call the LLM with retry and truncation handling.

    If the response is truncated (finish_reason='length'), makes continuation
    calls to get the rest of the output. Assembles the full response.
    """
    full_response = ""
    conversation = list(messages)  # Copy so we can append continuations

    for pass_num in range(5):  # Max 5 continuation passes
        response_text = ""
        finish_reason = ""

        for attempt in range(MAX_RETRIES + 1):
            try:
                # Newer models (gpt-4.1+, gpt-5+) require max_completion_tokens
                # Older models use max_tokens. Try both.
                try:
                    response = client.chat.completions.create(
                        model=model,
                        temperature=0,
                        max_completion_tokens=MAX_OUTPUT_TOKENS,
                        messages=conversation,
                    )
                except Exception:
                    response = client.chat.completions.create(
                        model=model,
                        temperature=0,
                        max_tokens=MAX_OUTPUT_TOKENS,
                        messages=conversation,
                    )
                response_text = response.choices[0].message.content or ""
                finish_reason = response.choices[0].finish_reason or "stop"

                if response_text.strip():
                    break
                logger.warning("Empty LLM response (attempt %d/%d)", attempt + 1, MAX_RETRIES + 1)
            except Exception as exc:
                logger.error("LLM call failed (attempt %d/%d): %s", attempt + 1, MAX_RETRIES + 1, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS * (2 ** attempt))
                    continue
                return full_response

        if not response_text.strip():
            break

        full_response += response_text
        logger.info("LLM pass %d: %d chars, finish_reason=%s", pass_num + 1, len(response_text), finish_reason)

        # If the response completed normally, we're done
        if finish_reason != "length":
            break

        # Response was truncated — ask the LLM to continue
        logger.info("Response truncated, requesting continuation...")
        conversation.append({"role": "assistant", "content": response_text})
        conversation.append({"role": "user", "content": "Continue the JSON array from exactly where you stopped. Do not repeat rules already output. Continue with the next rule object."})

    return full_response


def _split_into_chunks(text: str, max_chars: int) -> list[str]:
    """Split document text into overlapping chunks that fit the context window.

    Splits on paragraph boundaries (double newlines) to avoid cutting mid-sentence.
    Each chunk overlaps with the previous by CHUNK_OVERLAP_CHARS to provide context.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        # If adding this paragraph would exceed the limit, save current chunk
        if current_chunk and len(current_chunk) + len(para) + 2 > max_chars:
            chunks.append(current_chunk)
            # Start new chunk with overlap from end of previous
            overlap = current_chunk[-CHUNK_OVERLAP_CHARS:] if len(current_chunk) > CHUNK_OVERLAP_CHARS else current_chunk
            current_chunk = overlap + "\n\n" + para
        else:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para

    if current_chunk:
        chunks.append(current_chunk)

    logger.info("Split %d char document into %d chunks (max %d chars each)",
                len(text), len(chunks), max_chars)
    return chunks


def _deduplicate_rules(rules: list[dict]) -> list[dict]:
    """Remove duplicate rules from multi-chunk extraction.

    Uses rule_name similarity as the primary dedup key.
    When two rules have the same name, keeps the one with more conditions.
    """
    seen: dict[str, dict] = {}

    for rule in rules:
        name = str(rule.get("rule_name", "")).lower().strip()
        if not name:
            # No name — keep it
            seen[f"_unnamed_{len(seen)}"] = rule
            continue

        if name in seen:
            # Keep the one with more conditions (richer extraction)
            existing_conds = len(seen[name].get("conditions", []))
            new_conds = len(rule.get("conditions", []))
            if new_conds > existing_conds:
                seen[name] = rule
        else:
            seen[name] = rule

    return list(seen.values())


# ---------------------------------------------------------------------------
# Two-pass extraction for dense documents
# ---------------------------------------------------------------------------

def _enumerate_rules(client, model: str, doc_title: str, full_text: str) -> list[dict]:
    """Pass 1: Ask the LLM to enumerate every rule as lightweight JSON.

    This is cheap (~3-4K output tokens) and reliably finds ALL rules because
    the LLM doesn't have to produce detailed structure — just names and sections.
    """
    user_message = (
        f"Document: {doc_title}\n\n"
        f"{full_text}\n\n"
        f"List EVERY single business rule in this document. "
        f"Each distinct condition-action pair is a separate rule. "
        f"Do not merge or consolidate. Return the JSON array."
    )
    logger.info("Pass 1 (enumerate): sending %d chars to LLM", len(full_text))
    response_text = _call_llm(client, model, [
        {"role": "system", "content": ENUMERATE_PROMPT},
        {"role": "user", "content": user_message},
    ])
    if not response_text.strip():
        return []

    enumerated = _parse_json(response_text)
    logger.info("Pass 1 found %d rules", len(enumerated))
    return enumerated


def _extract_details_batch(
    client, model: str, doc_title: str, full_text: str,
    rule_summaries: list[dict], batch_num: int, total_batches: int,
) -> list[dict]:
    """Pass 2: Extract full details for a batch of enumerated rules.

    Sends the full document + a checklist of which rules to extract.
    The LLM must produce output for every listed rule — no skipping.
    """
    checklist = json.dumps(rule_summaries, indent=2)
    batch_label = f"(batch {batch_num}/{total_batches})" if total_batches > 1 else ""

    user_message = (
        f"Document: {doc_title} {batch_label}\n\n"
        f"{full_text}\n\n"
        f"--- RULES TO EXTRACT ---\n"
        f"Below are {len(rule_summaries)} rules identified in this document. "
        f"For EACH one, extract the full structured details (conditions, actions, etc). "
        f"Do NOT skip any. Do NOT merge. Produce exactly {len(rule_summaries)} rule objects.\n\n"
        f"{checklist}\n\n"
        f"Return the full JSON array for these {len(rule_summaries)} rules."
    )

    logger.info("Pass 2 %s: extracting details for %d rules",
                batch_label, len(rule_summaries))
    response_text = _call_llm(client, model, [
        {"role": "system", "content": DETAIL_EXTRACT_PROMPT},
        {"role": "user", "content": user_message},
    ])
    if not response_text.strip():
        return []

    rules = _parse_json(response_text)
    logger.info("Pass 2 %s: got %d detailed rules", batch_label, len(rules))
    return rules


def _two_pass_extract(
    client, model: str, doc_title: str, full_text: str,
) -> list[dict]:
    """Two-pass extraction: enumerate then detail-extract in batches.

    Pass 1: Enumerate all rules (lightweight, ~3K tokens output).
    Pass 2: Extract full details in batches of DETAIL_BATCH_SIZE rules.

    This solves the problem of the LLM voluntarily stopping early on dense
    documents — Pass 1 is cheap enough to enumerate everything, and Pass 2
    uses the enumeration as a mandatory checklist.
    """
    # Pass 1: Enumerate
    enumerated = _enumerate_rules(client, model, doc_title, full_text)
    if not enumerated:
        logger.warning("Two-pass: enumeration returned no rules, falling back to single-pass")
        return []

    # Pass 2: Extract details in batches
    all_detailed: list[dict] = []
    total_batches = (len(enumerated) + DETAIL_BATCH_SIZE - 1) // DETAIL_BATCH_SIZE

    for batch_idx in range(0, len(enumerated), DETAIL_BATCH_SIZE):
        batch = enumerated[batch_idx:batch_idx + DETAIL_BATCH_SIZE]
        batch_num = (batch_idx // DETAIL_BATCH_SIZE) + 1

        detailed = _extract_details_batch(
            client, model, doc_title, full_text,
            batch, batch_num, total_batches,
        )
        all_detailed.extend(detailed)

    logger.info("Two-pass complete: enumerated %d, extracted %d detailed rules",
                len(enumerated), len(all_detailed))
    return all_detailed


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_rules_with_retirements(
    sections: list[DocumentSection],
) -> tuple[list[RuleDefinition], list[dict]]:
    """Same as :func:`extract_rules` but also returns the LLM-emitted
    retirement signals (Layer-1 retirement strategy).

    Returns ``(rules, retirement_signals)``. Retirement signals follow
    the shape consumed by :mod:`app.services.retirement_signals` and
    are forwarded to :func:`live_repo_service.propose_from_brd` so the
    merge engine can emit REMOVED_RULE / RETIRE items.
    """
    from app.services.retirement_signals import extract_retirement_signals

    rules, raw_dicts = _extract_rules_internal(sections)
    signals = extract_retirement_signals(raw_dicts)
    return rules, signals


def extract_rules(sections: list[DocumentSection]) -> list[RuleDefinition]:
    """Extract rules from parsed document sections.

    Handles documents of any size:
    - Small docs (< 400K chars / ~100K tokens): single LLM call
    - Large docs (> 400K chars): chunked extraction with deduplication
    - Truncated responses: automatic continuation calls

    The extractor sends FULL document text in original order. No filtering,
    no reordering, no labels. The LLM reads and extracts every rule.

    Args:
        sections: Parsed sections (typically one section with full text).

    Returns:
        List of RuleDefinition objects. Empty list on failure.
    """
    rules, _ = _extract_rules_internal(sections)
    return rules


def _extract_rules_internal(
    sections: list[DocumentSection],
) -> tuple[list[RuleDefinition], list[dict]]:
    """Inner implementation that returns BOTH the parsed RuleDefinitions
    and the raw LLM dicts (for retirement-signal extraction)."""
    if not sections:
        return [], []

    client, model = _build_client()
    if client is None:
        return [], []

    # Combine all section content in order — just raw text
    full_text = "\n\n".join(s.content for s in sections)

    if len(full_text.strip()) < 20:
        logger.warning("Document text too short (%d chars)", len(full_text))
        return [], []

    doc_title = sections[0].title if sections else "BRD Document"
    logger.info("Extracting rules from '%s' (%d chars, ~%d tokens estimated)",
                doc_title, len(full_text), len(full_text) // CHARS_PER_TOKEN)

    # Strategy selection:
    # 1. Small docs (< 3000 chars): single-pass (fast, sufficient)
    # 2. Medium+ docs (>= 3000 chars) that fit in context: enumerate first (cheap),
    #    then use two-pass if enumeration finds more rules than single-pass threshold
    # 3. Huge docs (exceed context): chunk-based, each chunk gets two-pass
    chunks = _split_into_chunks(full_text, MAX_INPUT_CHARS)
    use_chunking = len(chunks) > 1

    all_raw_rules: list[dict] = []

    if use_chunking:
        # Huge document — chunk-based extraction with two-pass per chunk
        for chunk_idx, chunk_text in enumerate(chunks):
            chunk_label = f"(chunk {chunk_idx + 1}/{len(chunks)})"
            logger.info("Processing %s (%d chars)", chunk_label, len(chunk_text))

            chunk_rules = _two_pass_extract(client, model, doc_title, chunk_text)
            if not chunk_rules:
                # Fallback to single-pass for this chunk
                user_message = (
                    f"Document: {doc_title} {chunk_label}\n\n"
                    f"This is part {chunk_idx + 1} of {len(chunks)} of a large document. "
                    f"Extract ALL business rules from THIS section.\n\n"
                    f"{chunk_text}\n\n"
                    f"Extract every rule as a JSON array."
                )
                response_text = _call_llm(client, model, [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ])
                if response_text.strip():
                    chunk_rules = _parse_json(response_text)

            if chunk_rules:
                logger.info("%s: %d rules", chunk_label, len(chunk_rules))
                all_raw_rules.extend(chunk_rules)

    elif len(full_text) >= 3000:
        # Medium+ document — enumerate first to decide strategy
        # Enumeration is cheap (~3K output tokens) and tells us the true rule count
        logger.info("Document >= 3000 chars — running enumeration to assess rule density")
        enumerated = _enumerate_rules(client, model, doc_title, full_text)
        enum_count = len(enumerated) if enumerated else 0
        logger.info("Enumeration found %d rules", enum_count)

        if enum_count > TWO_PASS_RULE_THRESHOLD:
            # Dense document — use two-pass with the enumeration we already have
            logger.info("Dense document (%d rules) — using two-pass extraction", enum_count)
            all_detailed: list[dict] = []
            total_batches = (enum_count + DETAIL_BATCH_SIZE - 1) // DETAIL_BATCH_SIZE

            for batch_idx in range(0, enum_count, DETAIL_BATCH_SIZE):
                batch = enumerated[batch_idx:batch_idx + DETAIL_BATCH_SIZE]
                batch_num = (batch_idx // DETAIL_BATCH_SIZE) + 1
                detailed = _extract_details_batch(
                    client, model, doc_title, full_text,
                    batch, batch_num, total_batches,
                )
                all_detailed.extend(detailed)

            logger.info("Two-pass complete: enumerated %d, extracted %d detailed rules",
                        enum_count, len(all_detailed))
            all_raw_rules = all_detailed
        else:
            # Not too dense — single-pass is fine
            user_message = (
                f"Document: {doc_title}\n\n"
                f"{full_text}\n\n"
                f"Extract ALL business rules from this document as a JSON array."
            )
            logger.info("Single-pass extraction: %d chars to LLM", len(full_text))
            response_text = _call_llm(client, model, [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ])
            if response_text.strip():
                all_raw_rules = _parse_json(response_text)
                logger.info("Single-pass extracted %d rules", len(all_raw_rules))
    else:
        # Small document — single-pass
        user_message = (
            f"Document: {doc_title}\n\n"
            f"{full_text}\n\n"
            f"Extract ALL business rules from this document as a JSON array."
        )
        logger.info("Small document — single-pass extraction: %d chars", len(full_text))
        response_text = _call_llm(client, model, [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ])
        if response_text.strip():
            all_raw_rules = _parse_json(response_text)
            logger.info("Single-pass extracted %d rules", len(all_raw_rules))

    if not all_raw_rules:
        logger.warning("No rules extracted from document")
        return [], []

    # Deduplicate if we used multiple chunks or passes
    if use_chunking:
        before = len(all_raw_rules)
        all_raw_rules = _deduplicate_rules(all_raw_rules)
        logger.info("Deduplication: %d → %d rules", before, len(all_raw_rules))

    # Convert to RuleDefinitions
    rules = []
    for i, d in enumerate(all_raw_rules):
        if not isinstance(d, dict):
            continue
        rule = _parse_rule(d, i + 1)
        if rule is not None:
            rules.append(rule)

    # Fan out collapsed tier rules into N independent rules (a common
    # LLM mistake when reading tiered pricing tables — see _fan_out_tiers).
    rules = _fan_out_tiers(rules)

    # Ensure unique IDs
    seen = set()
    for i, rule in enumerate(rules):
        if rule.rule_id in seen:
            rule.rule_id = f"RULE-{i + 1:03d}"
        seen.add(rule.rule_id)

    logger.info("Extracted %d rules from '%s' (%d chunks)", len(rules), doc_title, len(chunks))
    return rules, all_raw_rules
