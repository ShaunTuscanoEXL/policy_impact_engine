"""LLM-powered rule extractor using OpenAI or Azure OpenAI.

Takes parsed BRD document sections and uses an LLM to extract structured
business rules suitable for the downstream Rule Compiler.
Supports both OpenAI and Azure OpenAI endpoints via LLM_PROVIDER config.
"""

from __future__ import annotations

import json
import logging
import re

from openai import AzureOpenAI, OpenAI

from app.config import settings
from app.pipeline.schemas import DocumentSection, SectionType
from app.schemas.rule import Action, Condition, RuleDefinition, RuleTypeEnum

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a business rule extraction specialist for a lending/credit decisioning system.

Given sections from a Business Requirement Document (BRD), extract each business rule into a structured JSON format.

For each rule found, provide a JSON object with these fields:
- rule_id: Sequential ID like "RULE-001", "RULE-002"
- rule_name: Short descriptive name (e.g., "DTI Cap Reduction")
- description: Full description of the rule change
- rule_type: One of "ELIGIBILITY", "PRICING", "CAP", "THRESHOLD", "SCORING"
  - ELIGIBILITY: Rules that determine if a customer qualifies (approve/reject)
  - PRICING: Rules that affect interest rates
  - CAP: Rules that limit loan amounts
  - THRESHOLD: Rules that set minimum/maximum values for metrics
  - SCORING: Rules that affect risk scores
- conditions: Array of condition objects, each with:
  - field: The data field name. Use these exact field names:
    bureau_score, dti_ratio, monthly_income, employment_type, employment_tenure_months,
    active_loans, unsecured_loans, credit_utilization_ratio, inquiries_last_3m,
    salary_credit_consistency_6m, banking_stability_index, desired_amount,
    cash_deposits_6m, city_tier, max_dpd_last_12m, cheque_bounces_6m,
    interest_rate, decision_status, eligible_amount, g5_score, g6_score
  - operator: One of ">=", "<=", ">", "<", "==", "!=", "in", "not_in", "between"
  - value: The threshold value (number, string, or array for "in"/"between")
  - logic: "AND" or "OR" for chaining with the next condition (default "AND")
- actions: Array of action objects, each with:
  - action_type: One of "SET", "REJECT", "ADJUST", "FLAG"
    - SET: Set a field to a specific value
    - REJECT: Reject the application
    - ADJUST: Add/subtract from a field value (delta)
    - FLAG: Flag for manual review
  - target_field: The field to modify (e.g., "decision_status", "interest_rate", "eligible_amount")
  - value: The new value or adjustment amount
  - description: Human-readable description of what this action does
- priority: Execution order (lower number = executed first, start from 1)
- source_section: Which BRD section this rule came from
- confidence: Your confidence in the extraction accuracy (0.0 to 1.0)

IMPORTANT:
- Extract ALL rules mentioned in the document, even if similar
- Be precise with field names — use exactly the names listed above
- For compound conditions (e.g., "income < 50000 AND loan > 150000"), create multiple condition objects
- If a rule applies to a specific customer segment, encode that as a condition
- Set confidence lower (0.6-0.8) for ambiguous rules, higher (0.9-1.0) for clearly stated rules

Respond with ONLY a JSON array of rule objects. No markdown, no explanation, just the JSON array."""


def _strip_code_fences(text: str) -> str:
    """Remove markdown code-block fences (```json ... ```) from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Drop the opening fence line
        lines = lines[1:]
        # Drop the closing fence line if present
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _parse_json_response(response_text: str) -> list[dict]:
    """Robustly parse a JSON array from the LLM response text.

    Tries direct parse first, then falls back to regex extraction.
    Returns an empty list rather than raising on total failure.
    """
    cleaned = _strip_code_fences(response_text)

    # Attempt 1: direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # LLM may have wrapped the array in a top-level object
            for val in data.values():
                if isinstance(val, list):
                    return val
            return [data]
        return []
    except json.JSONDecodeError:
        pass

    # Attempt 2: regex extraction of a JSON array
    match = re.search(r"\[.*]", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse JSON from LLM response: %s", cleaned[:300])
    return []


def _coerce_rule_type(raw: str) -> RuleTypeEnum | None:
    """Try to match a raw string to a RuleTypeEnum value, returning None on failure."""
    raw_upper = raw.strip().upper()
    try:
        return RuleTypeEnum(raw_upper)
    except ValueError:
        # Fuzzy match: check if any enum member name is contained in the raw string
        for member in RuleTypeEnum:
            if member.value in raw_upper:
                return member
        logger.warning("Unknown rule_type '%s'; skipping rule", raw)
        return None


def _parse_single_rule(rule_dict: dict) -> RuleDefinition | None:
    """Convert a raw dict from the LLM into a RuleDefinition, or None on failure."""
    try:
        # -- rule_type (required) --
        raw_type = rule_dict.get("rule_type")
        if raw_type is None:
            logger.warning("Rule %s missing rule_type; skipping", rule_dict.get("rule_id", "?"))
            return None
        rule_type = _coerce_rule_type(str(raw_type))
        if rule_type is None:
            return None

        # -- conditions --
        conditions: list[Condition] = []
        for c in rule_dict.get("conditions", []):
            if not isinstance(c, dict):
                continue
            # Ensure required keys exist with safe defaults
            conditions.append(
                Condition(
                    field=str(c.get("field", "")),
                    operator=str(c.get("operator", "==")),
                    value=c.get("value"),
                    logic=str(c.get("logic", "AND")).upper(),
                )
            )

        # -- actions --
        actions: list[Action] = []
        for a in rule_dict.get("actions", []):
            if not isinstance(a, dict):
                continue
            actions.append(
                Action(
                    action_type=str(a.get("action_type", "SET")).upper(),
                    target_field=str(a.get("target_field", "")),
                    value=a.get("value"),
                    description=str(a.get("description", "")),
                )
            )

        return RuleDefinition(
            rule_id=str(rule_dict.get("rule_id", "RULE-000")),
            rule_name=str(rule_dict.get("rule_name", "Unnamed Rule")),
            description=str(rule_dict.get("description", "")),
            rule_type=rule_type,
            conditions=conditions,
            actions=actions,
            priority=int(rule_dict.get("priority", 0)),
            source_section=str(rule_dict.get("source_section", "")),
            confidence=float(rule_dict.get("confidence", 0.8)),
        )
    except Exception as exc:
        logger.warning(
            "Failed to parse rule %s: %s",
            rule_dict.get("rule_id", "unknown"),
            exc,
        )
        return None


def extract_rules(sections: list[DocumentSection]) -> list[RuleDefinition]:
    """Extract structured rules from document sections using Claude.

    Args:
        sections: Parsed document sections from the BRD parser.

    Returns:
        A list of validated RuleDefinition objects. Returns an empty list
        (rather than raising) when no rules can be extracted.
    """
    if not sections:
        logger.info("No sections provided; returning empty rule list")
        return []

    # Filter for rule-related sections, but include context sections too
    relevant_sections = [
        s
        for s in sections
        if s.section_type
        in (SectionType.RULES, SectionType.CURRENT_STATE, SectionType.EXECUTIVE_SUMMARY)
    ]

    if not relevant_sections:
        # Fall back to all sections if none classified as RULES
        logger.info(
            "No RULES/CURRENT_STATE/EXECUTIVE_SUMMARY sections found; "
            "using all %d sections",
            len(sections),
        )
        relevant_sections = sections

    combined_text = "\n\n".join(
        f"### Section: {s.title}\n{s.content}" for s in relevant_sections
    )

    # Guard against sending an effectively empty payload
    if not combined_text.strip():
        logger.warning("Combined section text is empty; returning empty rule list")
        return []

    # Build client based on provider
    if settings.llm_provider.lower() == "azure":
        if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
            logger.error("Azure OpenAI selected but AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT not set")
            return []
        client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        model = settings.azure_openai_deployment
        logger.info("Using Azure OpenAI (endpoint=%s, deployment=%s)", settings.azure_openai_endpoint, model)
    else:
        client = OpenAI(api_key=settings.openai_api_key)
        model = settings.openai_model
        logger.info("Using OpenAI (model=%s)", model)

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": f"BRD Content:\n\n{combined_text}"},
            ],
        )
    except Exception as exc:
        logger.error("LLM API call failed: %s", exc)
        return []

    response_text = response.choices[0].message.content or ""

    if not response_text.strip():
        logger.warning("LLM returned empty response")
        return []

    rules_data = _parse_json_response(response_text)

    if not rules_data:
        logger.warning("No rule objects parsed from LLM response")
        return []

    rules: list[RuleDefinition] = []
    for rule_dict in rules_data:
        if not isinstance(rule_dict, dict):
            continue
        parsed = _parse_single_rule(rule_dict)
        if parsed is not None:
            rules.append(parsed)

    logger.info("Extracted %d rules from %d sections", len(rules), len(relevant_sections))
    return rules
