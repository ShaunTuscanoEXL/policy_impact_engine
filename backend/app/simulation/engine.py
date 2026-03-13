import pandas as pd
from dataclasses import dataclass, field
from app.pipeline.rule_compiler import CompiledRule
from app.simulation.baseline import apply_baseline
from app.simulation.comparator import compare_results


@dataclass
class SimulationOutput:
    total_customers: int
    affected_customers: int
    affected_percentage: float
    decision_changes: dict
    amount_changes: dict
    segment_breakdown: dict
    financial_impact: dict
    conflict_log: list[dict]
    baseline_df: pd.DataFrame
    simulated_df: pd.DataFrame


def run_simulation(
    df: pd.DataFrame,
    new_rules: list[CompiledRule],
) -> SimulationOutput:
    """Run simulation: baseline -> apply new rules -> compare."""

    # Phase 1: Baseline
    baseline_df = apply_baseline(df)

    # Phase 2: Initialize simulation columns from baseline
    simulated_df = baseline_df.copy()
    simulated_df["sim_decision"] = simulated_df["baseline_decision"].copy()
    simulated_df["sim_eligible_amount"] = simulated_df["baseline_eligible_amount"].copy()
    simulated_df["sim_interest_rate"] = simulated_df["baseline_interest_rate"].copy()

    # Apply new rules in priority order
    conflict_log = []
    for rule in sorted(new_rules, key=lambda r: r.priority):
        mask = rule.evaluate(simulated_df)
        affected_count = mask.sum()

        if affected_count > 0:
            # Track decision state before applying rule
            prev_decisions = simulated_df.loc[mask, "sim_decision"].copy()

            # Apply the rule
            simulated_df = rule.apply(simulated_df, mask)

            # Check for decision flips (potential conflicts with previous rules)
            new_decisions = simulated_df.loc[mask, "sim_decision"]
            flipped = prev_decisions != new_decisions
            if flipped.any():
                conflict_log.append({
                    "rule_id": rule.rule_id,
                    "rule_name": rule.rule_name,
                    "affected_count": int(affected_count),
                    "decision_flips": int(flipped.sum()),
                })

    # Phase 3: Compare
    return compare_results(baseline_df, simulated_df, conflict_log)
