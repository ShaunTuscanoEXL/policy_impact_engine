"""LangGraph pipeline assembling all processing nodes.

Wires together: document parsing -> rule extraction -> validation ->
(optional human review) -> compilation -> simulation.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from app.pipeline.document_parser import parse_document
from app.pipeline.rule_compiler import CompiledRule, compile_rules
from app.pipeline.rule_extractor import extract_rules
from app.pipeline.rule_validator import validate_rules
from app.pipeline.schemas import DocumentSection, ValidationResult
from app.schemas.rule import RuleDefinition
from app.simulation.engine import SimulationOutput, run_simulation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------


class PipelineState(TypedDict, total=False):
    """Shared state flowing through the LangGraph pipeline."""

    brd_document: bytes
    brd_filename: str
    dataset_df: pd.DataFrame
    auto_approve: bool
    baseline_config: dict | None

    parsed_sections: list[DocumentSection]
    extracted_rules: list[RuleDefinition]
    validation_result: ValidationResult | None
    compiled_rules: list[CompiledRule]
    simulation_result: SimulationOutput | None
    error: str | None


# ---------------------------------------------------------------------------
# Node wrapper functions
# ---------------------------------------------------------------------------


def parse_document_node(state: PipelineState) -> dict[str, Any]:
    """Parse the BRD document into structured sections."""
    try:
        sections = parse_document(state["brd_document"], state["brd_filename"])
        logger.info("Parsed %d sections from '%s'", len(sections), state["brd_filename"])
        return {"parsed_sections": sections}
    except Exception as exc:
        logger.error("Document parsing failed: %s", exc)
        return {"parsed_sections": [], "error": f"Document parsing failed: {exc}"}


def extract_rules_node(state: PipelineState) -> dict[str, Any]:
    """Extract business rules from parsed sections using LLM."""
    if state.get("error"):
        return {"extracted_rules": []}
    try:
        rules = extract_rules(state["parsed_sections"])
        logger.info("Extracted %d rules", len(rules))
        return {"extracted_rules": rules}
    except Exception as exc:
        logger.error("Rule extraction failed: %s", exc)
        return {"extracted_rules": [], "error": f"Rule extraction failed: {exc}"}


def validate_rules_node(state: PipelineState) -> dict[str, Any]:
    """Validate extracted rules for completeness and conflicts."""
    if state.get("error"):
        return {"validation_result": None}
    try:
        result = validate_rules(state["extracted_rules"])
        logger.info(
            "Validation complete: valid=%s, warnings=%d, conflicts=%d",
            result.is_valid,
            len(result.warnings),
            len(result.potential_conflicts),
        )
        return {"validation_result": result}
    except Exception as exc:
        logger.error("Rule validation failed: %s", exc)
        return {"validation_result": None, "error": f"Rule validation failed: {exc}"}


def compile_rules_node(state: PipelineState) -> dict[str, Any]:
    """Compile validated rules into executable form."""
    if state.get("error"):
        return {"compiled_rules": []}
    try:
        compiled = compile_rules(state["extracted_rules"])
        logger.info("Compiled %d rules", len(compiled))
        return {"compiled_rules": compiled}
    except Exception as exc:
        logger.error("Rule compilation failed: %s", exc)
        return {"compiled_rules": [], "error": f"Rule compilation failed: {exc}"}


def simulation_node(state: PipelineState) -> dict[str, Any]:
    """Run simulation with compiled rules against the dataset."""
    if state.get("error"):
        return {"simulation_result": None}
    try:
        result = run_simulation(state["dataset_df"], state["compiled_rules"], config=state.get("baseline_config"))
        logger.info(
            "Simulation complete: %d/%d customers affected (%.1f%%)",
            result.affected_customers,
            result.total_customers,
            result.affected_percentage,
        )
        return {"simulation_result": result}
    except Exception as exc:
        logger.error("Simulation failed: %s", exc)
        return {"simulation_result": None, "error": f"Simulation failed: {exc}"}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def should_auto_approve(state: PipelineState) -> str:
    """Route after validation: skip human review if auto_approve is set."""
    if state.get("error"):
        return END
    if state.get("auto_approve", False):
        return "compile_rules"
    # Human review interrupt — pipeline stops here and can be resumed later.
    return END


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------


def build_pipeline() -> StateGraph:
    """Build and compile the LangGraph pipeline.

    Returns a compiled StateGraph ready for invocation.
    """
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("parse_document", parse_document_node)
    graph.add_node("extract_rules", extract_rules_node)
    graph.add_node("validate_rules", validate_rules_node)
    graph.add_node("compile_rules", compile_rules_node)
    graph.add_node("run_simulation", simulation_node)

    # Set entry point
    graph.set_entry_point("parse_document")

    # Linear edges
    graph.add_edge("parse_document", "extract_rules")
    graph.add_edge("extract_rules", "validate_rules")

    # Conditional edge: auto-approve or human-review interrupt
    graph.add_conditional_edges(
        "validate_rules",
        should_auto_approve,
        {
            "compile_rules": "compile_rules",
            END: END,
        },
    )

    graph.add_edge("compile_rules", "run_simulation")
    graph.add_edge("run_simulation", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------


def run_pipeline(
    brd_content: bytes,
    brd_filename: str,
    dataset_df: pd.DataFrame,
    auto_approve: bool = False,
    baseline_config: dict | None = None,
) -> dict[str, Any]:
    """Create and run the full pipeline, returning the final state dict.

    Args:
        brd_content: Raw bytes of the BRD document.
        brd_filename: Original filename (used to detect format).
        dataset_df: Customer dataset to simulate against.
        auto_approve: If True, skip the human-review checkpoint.

    Returns:
        The final pipeline state dictionary.
    """
    pipeline = build_pipeline()

    initial_state: PipelineState = {
        "brd_document": brd_content,
        "brd_filename": brd_filename,
        "dataset_df": dataset_df,
        "auto_approve": auto_approve,
        "baseline_config": baseline_config,
    }

    result = pipeline.invoke(initial_state)
    return result
