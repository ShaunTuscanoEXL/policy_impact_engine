import pandas as pd
from app.schemas.rule import RuleDefinition, Condition, Action


class CompiledRule:
    """A rule compiled into executable Pandas operations."""

    def __init__(self, rule_def: RuleDefinition, condition_func, actions: list[Action]):
        self.rule_def = rule_def
        self.rule_id = rule_def.rule_id
        self.rule_name = rule_def.rule_name
        self.priority = rule_def.priority
        self.condition_func = condition_func
        self.actions = actions

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        """Returns boolean mask of rows matching all conditions."""
        return self.condition_func(df)

    def apply(self, df: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
        """Apply actions to rows matching the mask."""
        result = df.copy()
        for action in self.actions:
            if action.action_type == "REJECT":
                result.loc[mask, "sim_decision"] = "REJECTED"
            elif action.action_type == "SET":
                target = action.target_field
                # Map common field names to sim-prefixed columns
                if target == "decision_status":
                    target = "sim_decision"
                elif target == "eligible_amount":
                    target = "sim_eligible_amount"
                elif target == "interest_rate":
                    target = "sim_interest_rate"
                result.loc[mask, target] = action.value
            elif action.action_type == "ADJUST":
                target = action.target_field
                if target == "interest_rate":
                    target = "sim_interest_rate"
                elif target == "eligible_amount":
                    target = "sim_eligible_amount"
                result.loc[mask, target] = result.loc[mask, target] + action.value
            elif action.action_type == "FLAG":
                flag_col = f"flag_{action.target_field}"
                if flag_col not in result.columns:
                    result[flag_col] = False
                result.loc[mask, flag_col] = True
        return result


def compile_rule(rule: RuleDefinition) -> CompiledRule:
    """Convert a RuleDefinition into a CompiledRule with executable condition function."""
    condition_func = _build_condition_func(rule.conditions)
    return CompiledRule(rule, condition_func, rule.actions)


def compile_rules(rules: list[RuleDefinition]) -> list[CompiledRule]:
    """Compile a list of rules, sorted by priority."""
    compiled = [compile_rule(r) for r in rules]
    compiled.sort(key=lambda r: r.priority)
    return compiled


def _build_condition_func(conditions: list[Condition]):
    """Build a function that evaluates conditions against a DataFrame."""

    def evaluate(df: pd.DataFrame) -> pd.Series:
        if not conditions:
            return pd.Series([True] * len(df), index=df.index)

        # Start with all True
        result = pd.Series([True] * len(df), index=df.index)
        current_logic = "AND"

        for i, cond in enumerate(conditions):
            single_result = _evaluate_single_condition(df, cond)

            if i == 0:
                result = single_result
            else:
                if current_logic == "AND":
                    result = result & single_result
                else:  # OR
                    result = result | single_result

            # The logic field on current condition specifies how to combine with the NEXT condition
            current_logic = cond.logic

        return result

    return evaluate


def _evaluate_single_condition(df: pd.DataFrame, cond: Condition) -> pd.Series:
    """Evaluate a single condition against a DataFrame."""
    field = cond.field

    # Check if field exists in DataFrame
    if field not in df.columns:
        # Return all False if field doesn't exist
        return pd.Series([False] * len(df), index=df.index)

    col = df[field]
    value = cond.value

    # Try to convert value to appropriate type
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            pass  # Keep as string

    op = cond.operator

    if op == ">=":
        return col >= value
    elif op == "<=":
        return col <= value
    elif op == ">":
        return col > value
    elif op == "<":
        return col < value
    elif op == "==":
        return col == value
    elif op == "!=":
        return col != value
    elif op == "in":
        if isinstance(value, list):
            return col.isin(value)
        return col.isin([value])
    elif op == "not_in":
        if isinstance(value, list):
            return ~col.isin(value)
        return ~col.isin([value])
    elif op == "between":
        if isinstance(value, list) and len(value) == 2:
            return (col >= value[0]) & (col <= value[1])
        return pd.Series([False] * len(df), index=df.index)
    else:
        # Unknown operator — return all False
        return pd.Series([False] * len(df), index=df.index)
