"""API endpoints for triggering and managing the BRD processing pipeline."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.dataset import DatasetFileType
from app.models.rule import Rule, RuleSet, RuleSetStatus
from app.models.simulation import SimulationStatus
from app.pipeline.graph import run_pipeline
from app.pipeline.rule_compiler import compile_rules
from app.schemas.rule import RuleDefinition
from app.services import brd_service, dataset_service, rule_service, simulation_service
from app.simulation.engine import SimulationOutput, run_simulation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class PipelineRunRequest(BaseModel):
    brd_id: str
    dataset_id: str
    scenario_name: str = "Default Scenario"
    auto_approve: bool = False


class PipelineRunResponse(BaseModel):
    status: str
    simulation_id: str
    rule_set_id: str
    impact_summary: dict | None = None
    extracted_rules: list[dict] | None = None
    validation_result: dict | None = None
    rules_extracted: int
    error: str | None = None


class PipelineApproveResponse(BaseModel):
    status: str
    simulation_id: str
    rule_set_id: str
    impact_summary: dict
    rules_compiled: int


class PipelineStatusResponse(BaseModel):
    simulation_id: str
    status: str
    scenario_name: str
    rule_set_id: str
    result_summary: dict | None = None
    created_at: str
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simulation_output_to_summary(output: SimulationOutput) -> dict:
    """Convert a SimulationOutput dataclass to a JSON-safe summary dict."""
    return {
        "total_customers": output.total_customers,
        "affected_customers": output.affected_customers,
        "affected_percentage": output.affected_percentage,
        "decision_changes": output.decision_changes,
        "amount_changes": output.amount_changes,
        "segment_breakdown": output.segment_breakdown,
        "financial_impact": output.financial_impact,
    }


async def _save_extracted_rules(
    rule_set_id: str,
    extracted_rules: list[RuleDefinition],
    db: AsyncSession,
) -> None:
    """Persist extracted RuleDefinition objects as Rule DB records."""
    for rule_def in extracted_rules:
        rule = Rule(
            rule_set_id=uuid.UUID(rule_set_id) if isinstance(rule_set_id, str) else rule_set_id,
            rule_id=rule_def.rule_id,
            rule_name=rule_def.rule_name,
            description=rule_def.description,
            rule_type=rule_def.rule_type.value,
            conditions=[c.model_dump() for c in rule_def.conditions],
            actions=[a.model_dump() for a in rule_def.actions],
            priority=rule_def.priority,
            confidence=rule_def.confidence,
            source_section=rule_def.source_section,
        )
        db.add(rule)
    await db.flush()


async def _save_simulation_results(
    sim_id: str,
    sim_output: SimulationOutput,
    db: AsyncSession,
) -> None:
    """Persist simulation results to the DB."""
    summary = _simulation_output_to_summary(sim_output)
    await simulation_service.save_simulation_result(
        sim_id=sim_id,
        summary_stats=summary,
        segment_analysis=sim_output.segment_breakdown,
        customer_diffs_path=None,
        financial_impact=sim_output.financial_impact,
        conflict_report={"conflicts": sim_output.conflict_log} if sim_output.conflict_log else None,
        db=db,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/run", response_model=PipelineRunResponse, status_code=200)
async def pipeline_run(body: PipelineRunRequest, db: AsyncSession = Depends(get_db)):
    """Trigger the BRD processing pipeline.

    Reads the BRD and dataset from disk, runs parse -> extract -> validate,
    and optionally compiles + simulates (when auto_approve is True).
    """
    # 1. Look up BRD and dataset
    brd = await brd_service.get_brd(body.brd_id, db)
    if not brd:
        raise HTTPException(status_code=404, detail="BRD document not found")

    dataset = await dataset_service.get_dataset(body.dataset_id, db)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # 2. Read BRD file bytes from disk
    brd_path = Path(brd.file_path)
    if not brd_path.exists():
        raise HTTPException(status_code=404, detail="BRD file not found on disk")
    brd_content = brd_path.read_bytes()

    # 3. Read dataset as DataFrame
    dataset_path = Path(dataset.file_path)
    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail="Dataset file not found on disk")

    if dataset.file_type == DatasetFileType.CSV:
        dataset_df = pd.read_csv(dataset_path)
    else:
        dataset_df = pd.read_json(dataset_path)

    # 4. Create RuleSet record (DRAFT)
    rule_set = RuleSet(
        brd_document_id=brd.id,
        name=f"Rules from {brd.filename}",
        description=f"Auto-extracted rules for scenario: {body.scenario_name}",
        status=RuleSetStatus.DRAFT,
    )
    db.add(rule_set)
    await db.flush()
    await db.refresh(rule_set)

    # 5. Create Simulation record (PENDING)
    sim = await simulation_service.create_simulation(
        scenario_name=body.scenario_name,
        dataset_id=body.dataset_id,
        rule_set_id=str(rule_set.id),
        parameters={"auto_approve": body.auto_approve},
        db=db,
    )

    # 6. Update simulation to RUNNING
    await simulation_service.update_simulation_status(str(sim.id), SimulationStatus.RUNNING, db)

    # 7. Run the pipeline (synchronous / CPU-bound — Celery in Phase 6)
    try:
        result = run_pipeline(
            brd_content=brd_content,
            brd_filename=brd.filename,
            dataset_df=dataset_df,
            auto_approve=body.auto_approve,
        )
    except Exception as exc:
        logger.exception("Pipeline execution failed")
        await simulation_service.update_simulation_status(str(sim.id), SimulationStatus.FAILED, db)
        return PipelineRunResponse(
            status="FAILED",
            simulation_id=str(sim.id),
            rule_set_id=str(rule_set.id),
            rules_extracted=0,
            error=str(exc),
        )

    # 8. Check for pipeline-level errors
    if result.get("error"):
        await simulation_service.update_simulation_status(str(sim.id), SimulationStatus.FAILED, db)
        return PipelineRunResponse(
            status="FAILED",
            simulation_id=str(sim.id),
            rule_set_id=str(rule_set.id),
            rules_extracted=len(result.get("extracted_rules", [])),
            error=result["error"],
        )

    extracted_rules: list[RuleDefinition] = result.get("extracted_rules", [])
    validation_result = result.get("validation_result")

    # 9. Auto-approve path: full completion
    if body.auto_approve and result.get("simulation_result") is not None:
        sim_output: SimulationOutput = result["simulation_result"]

        # Save extracted rules to rule_set
        await _save_extracted_rules(str(rule_set.id), extracted_rules, db)

        # Approve rule set
        rule_set.status = RuleSetStatus.APPROVED
        await db.flush()

        # Save simulation results
        await _save_simulation_results(str(sim.id), sim_output, db)

        # Mark simulation completed
        await simulation_service.update_simulation_status(str(sim.id), SimulationStatus.COMPLETED, db)

        await db.commit()

        return PipelineRunResponse(
            status="COMPLETED",
            simulation_id=str(sim.id),
            rule_set_id=str(rule_set.id),
            impact_summary=_simulation_output_to_summary(sim_output),
            rules_extracted=len(extracted_rules),
        )

    # 10. Human review path: pause after validation
    await _save_extracted_rules(str(rule_set.id), extracted_rules, db)
    await db.commit()

    return PipelineRunResponse(
        status="AWAITING_REVIEW",
        simulation_id=str(sim.id),
        rule_set_id=str(rule_set.id),
        extracted_rules=[r.model_dump() for r in extracted_rules],
        validation_result=validation_result.model_dump() if validation_result else None,
        rules_extracted=len(extracted_rules),
    )


@router.post("/{simulation_id}/approve", response_model=PipelineApproveResponse, status_code=200)
async def pipeline_approve(simulation_id: str, db: AsyncSession = Depends(get_db)):
    """Approve extracted rules and run compilation + simulation.

    Called after human review of the AWAITING_REVIEW pipeline output.
    """
    # Retrieve simulation
    sim = await simulation_service.get_simulation(simulation_id, db)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    if sim.status not in (SimulationStatus.RUNNING, SimulationStatus.PENDING):
        if sim.status == SimulationStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Simulation already completed")
        if sim.status == SimulationStatus.FAILED:
            raise HTTPException(status_code=400, detail="Simulation has failed — re-run the pipeline")

    # Retrieve associated rule set with its rules
    rule_set = await rule_service.get_rule_set(str(sim.rule_set_id), db)
    if not rule_set:
        raise HTTPException(status_code=404, detail="Rule set not found")

    if not rule_set.rules:
        raise HTTPException(status_code=400, detail="No rules found in rule set")

    # Approve rule set
    rule_set.status = RuleSetStatus.APPROVED
    await db.flush()

    # Reconstruct RuleDefinition objects from DB Rule records
    rule_definitions: list[RuleDefinition] = []
    for rule in rule_set.rules:
        rule_definitions.append(
            RuleDefinition(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                description=rule.description or "",
                rule_type=rule.rule_type.value,
                conditions=rule.conditions,
                actions=rule.actions,
                priority=rule.priority,
                source_section=rule.source_section or "",
                confidence=rule.confidence,
            )
        )

    # Compile rules
    compiled = compile_rules(rule_definitions)

    # Read dataset for simulation
    dataset = await dataset_service.get_dataset(str(sim.dataset_id), db)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    dataset_path = Path(dataset.file_path)
    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail="Dataset file not found on disk")

    if dataset.file_type == DatasetFileType.CSV:
        dataset_df = pd.read_csv(dataset_path)
    else:
        dataset_df = pd.read_json(dataset_path)

    # Run simulation
    await simulation_service.update_simulation_status(simulation_id, SimulationStatus.RUNNING, db)
    try:
        sim_output = run_simulation(dataset_df, compiled)
    except Exception as exc:
        logger.exception("Simulation failed during approval")
        await simulation_service.update_simulation_status(simulation_id, SimulationStatus.FAILED, db)
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}")

    # Persist results
    await _save_simulation_results(simulation_id, sim_output, db)
    await simulation_service.update_simulation_status(simulation_id, SimulationStatus.COMPLETED, db)
    await db.commit()

    return PipelineApproveResponse(
        status="COMPLETED",
        simulation_id=simulation_id,
        rule_set_id=str(rule_set.id),
        impact_summary=_simulation_output_to_summary(sim_output),
        rules_compiled=len(compiled),
    )


@router.get("/{simulation_id}/status", response_model=PipelineStatusResponse, status_code=200)
async def pipeline_status(simulation_id: str, db: AsyncSession = Depends(get_db)):
    """Return current pipeline / simulation status and result summary if completed."""
    sim = await simulation_service.get_simulation(simulation_id, db)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    result_summary = None
    if sim.status == SimulationStatus.COMPLETED and sim.results:
        latest_result = sim.results[-1]
        result_summary = latest_result.summary_stats

    return PipelineStatusResponse(
        simulation_id=str(sim.id),
        status=sim.status.value,
        scenario_name=sim.scenario_name,
        rule_set_id=str(sim.rule_set_id),
        result_summary=result_summary,
        created_at=sim.created_at.isoformat(),
        completed_at=sim.completed_at.isoformat() if sim.completed_at else None,
    )
