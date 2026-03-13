"""Rule Validator & Conflict Detector.

Validates extracted rules for completeness and detects potential conflicts
between rule pairs. Runs after the Rule Extractor and before the Human
Review Checkpoint in the LangGraph pipeline.
"""

from __future__ import annotations

from app.pipeline.schemas import RuleConflict, ValidationResult
from app.schemas.rule import Condition, RuleDefinition

# Fields that represent decision outcomes
DECISION_FIELDS = {"decision_status", "eligible_amount", "interest_rate"}

# Action types that are contradictory
CONTRADICTORY_ACTIONS = {
    ("SET", "REJECT"),
    ("REJECT", "SET"),
    ("ADJUST", "REJECT"),
    ("REJECT", "ADJUST"),
}

# Operators recognised as valid in conditions
VALID_OPERATORS = {">=", "<=", ">", "<", "==", "!=", "in", "not_in", "between"}

# Action types recognised as valid
VALID_ACTION_TYPES = {"SET", "REJECT", "ADJUST", "FLAG"}


def validate_rules(rules: list[RuleDefinition]) -> ValidationResult:
    """Validate a list of extracted rules for completeness and conflicts."""
    warnings: list[str] = []
    conflicts: list[RuleConflict] = []

    for rule in rules:
        # --- Completeness checks ---
        if not rule.conditions:
            warnings.append(
                f"{rule.rule_id} ({rule.rule_name}): No conditions defined"
            )
        if not rule.actions:
            warnings.append(
                f"{rule.rule_id} ({rule.rule_name}): No actions defined"
            )
        if rule.confidence < 0.7:
            warnings.append(
                f"{rule.rule_id} ({rule.rule_name}): "
                f"Low extraction confidence ({rule.confidence:.2f})"
            )

        # --- Operator / action-type validity ---
        for cond in rule.conditions:
            if cond.operator not in VALID_OPERATORS:
                warnings.append(
                    f"{rule.rule_id}: Invalid operator '{cond.operator}' "
                    f"in condition on field '{cond.field}'"
                )

        for action in rule.actions:
            if action.action_type not in VALID_ACTION_TYPES:
                warnings.append(
                    f"{rule.rule_id}: Invalid action type '{action.action_type}'"
                )

    # --- Pairwise conflict detection ---
    for i, r1 in enumerate(rules):
        for r2 in rules[i + 1 :]:
            conflict = _check_conflict(r1, r2)
            if conflict:
                conflicts.append(conflict)

    return ValidationResult(
        is_valid=(
            len(conflicts) == 0
            and not any(
                "No conditions" in w or "No actions" in w for w in warnings
            )
        ),
        warnings=warnings,
        potential_conflicts=conflicts,
    )


# ---- internal helpers -------------------------------------------------------


def _check_conflict(
    r1: RuleDefinition, r2: RuleDefinition
) -> RuleConflict | None:
    """Check if two rules potentially conflict."""
    # Collect the target fields touched by each rule's actions
    r1_targets = {a.target_field for a in r1.actions}
    r2_targets = {a.target_field for a in r2.actions}

    shared_targets = r1_targets & r2_targets
    if not shared_targets:
        return None

    for target in shared_targets:
        r1_actions = [a for a in r1.actions if a.target_field == target]
        r2_actions = [a for a in r2.actions if a.target_field == target]

        for a1 in r1_actions:
            for a2 in r2_actions:
                # Contradictory action types (e.g. SET vs REJECT)
                if (a1.action_type, a2.action_type) in CONTRADICTORY_ACTIONS:
                    if _conditions_could_overlap(r1.conditions, r2.conditions):
                        return RuleConflict(
                            rule_id_1=r1.rule_id,
                            rule_id_2=r2.rule_id,
                            conflict_type="CONTRADICTORY_ACTIONS",
                            description=(
                                f"Rule '{r1.rule_name}' ({a1.action_type} on "
                                f"{target}) conflicts with Rule "
                                f"'{r2.rule_name}' ({a2.action_type} on "
                                f"{target}). Both rules may apply to the "
                                f"same customers."
                            ),
                            affected_fields=list(shared_targets),
                        )

                # Same action type (SET) but competing values
                if (
                    a1.action_type == "SET"
                    and a2.action_type == "SET"
                    and a1.value != a2.value
                ):
                    if _conditions_could_overlap(r1.conditions, r2.conditions):
                        return RuleConflict(
                            rule_id_1=r1.rule_id,
                            rule_id_2=r2.rule_id,
                            conflict_type="COMPETING_VALUES",
                            description=(
                                f"Rule '{r1.rule_name}' sets "
                                f"{target}={a1.value} while Rule "
                                f"'{r2.rule_name}' sets "
                                f"{target}={a2.value}. Both rules may "
                                f"apply to the same customers."
                            ),
                            affected_fields=list(shared_targets),
                        )

    return None


def _conditions_could_overlap(
    conds1: list[Condition], conds2: list[Condition]
) -> bool:
    """Heuristic check whether two condition sets could apply to the same customer.

    The check is *conservative*: it returns ``True`` (could overlap) unless it
    can prove at least one shared field has mutually exclusive ranges.
    """
    fields1 = {c.field for c in conds1}
    fields2 = {c.field for c in conds2}

    shared_fields = fields1 & fields2

    if not shared_fields:
        # No shared fields — conditions operate on different dimensions,
        # so they CAN overlap.
        return True

    for field in shared_fields:
        c1_on_field = [c for c in conds1 if c.field == field]
        c2_on_field = [c for c in conds2 if c.field == field]

        for c1 in c1_on_field:
            for c2 in c2_on_field:
                if _ranges_are_exclusive(c1, c2):
                    return False  # At least one field is mutually exclusive

    return True  # Conservative: assume overlap unless proven exclusive


def _ranges_are_exclusive(c1: Condition, c2: Condition) -> bool:
    """Check if two conditions on the same field are mutually exclusive.

    Works for numeric comparisons (``>=``, ``>``, ``<=``, ``<``, ``==``).
    Returns ``False`` (not provably exclusive) for non-numeric values or
    operators it cannot reason about.
    """
    try:
        v1 = (
            float(c1.value)
            if not isinstance(c1.value, (list, dict))
            else None
        )
        v2 = (
            float(c2.value)
            if not isinstance(c2.value, (list, dict))
            else None
        )
    except (ValueError, TypeError):
        return False  # Can't determine numerically

    if v1 is None or v2 is None:
        return False

    # e.g. c1: field >= 750, c2: field < 700  →  exclusive (750 > 700)
    if c1.operator in (">=", ">") and c2.operator in ("<", "<="):
        return v1 > v2
    if c1.operator in ("<", "<=") and c2.operator in (">=", ">"):
        return v2 > v1

    # e.g. c1: field == 5, c2: field == 10  →  exclusive
    if c1.operator == "==" and c2.operator == "==" and v1 != v2:
        return True

    return False
