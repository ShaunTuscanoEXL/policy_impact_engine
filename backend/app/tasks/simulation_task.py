"""Async Celery task for running simulations."""
import logging
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=1)
def run_simulation_async(
    self,
    simulation_id: str,
    brd_file_path: str,
    brd_filename: str,
    dataset_file_path: str,
    dataset_file_type: str,
    rule_set_id: str,
):
    """Run a simulation asynchronously via Celery.

    This task:
    1. Reads BRD file and dataset from disk
    2. Runs the pipeline (parse -> extract -> validate -> compile -> simulate)
    3. Saves results to DB
    4. Updates simulation status
    """
    import uuid
    from datetime import datetime
    from pathlib import Path

    import pandas as pd
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.config import settings
    from app.models.rule import Rule, RuleSet, RuleSetStatus
    from app.models.simulation import Simulation, SimulationResult, SimulationStatus
    from app.pipeline.graph import run_pipeline

    # Use sync database connection for Celery (not async)
    sync_url = settings.database_url.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    try:
        # Read files
        brd_content = Path(brd_file_path).read_bytes()

        if dataset_file_type == "CSV":
            dataset_df = pd.read_csv(dataset_file_path)
        else:
            dataset_df = pd.read_json(dataset_file_path)

        # Update status to RUNNING
        with Session(engine) as session:
            sim = session.get(Simulation, uuid.UUID(simulation_id))
            if sim:
                sim.status = SimulationStatus.RUNNING
                session.commit()

        # Run pipeline
        result = run_pipeline(
            brd_content=brd_content,
            brd_filename=brd_filename,
            dataset_df=dataset_df,
            auto_approve=True,
        )

        if result.get("error"):
            with Session(engine) as session:
                sim = session.get(Simulation, uuid.UUID(simulation_id))
                if sim:
                    sim.status = SimulationStatus.FAILED
                    session.commit()
            return {"status": "FAILED", "error": result["error"]}

        # Save results
        sim_output = result.get("simulation_result")
        if sim_output:
            summary = {
                "total_customers": sim_output.total_customers,
                "affected_customers": sim_output.affected_customers,
                "affected_percentage": sim_output.affected_percentage,
                "decision_changes": sim_output.decision_changes,
                "amount_changes": sim_output.amount_changes,
                "segment_breakdown": sim_output.segment_breakdown,
                "financial_impact": sim_output.financial_impact,
            }

            with Session(engine) as session:
                # Save extracted rules
                extracted_rules = result.get("extracted_rules", [])
                for rule_def in extracted_rules:
                    rule = Rule(
                        rule_set_id=uuid.UUID(rule_set_id),
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
                    session.add(rule)

                # Approve rule set
                rs = session.get(RuleSet, uuid.UUID(rule_set_id))
                if rs:
                    rs.status = RuleSetStatus.APPROVED

                # Save simulation result
                sim_result = SimulationResult(
                    simulation_id=uuid.UUID(simulation_id),
                    summary_stats=summary,
                    segment_analysis=sim_output.segment_breakdown,
                    financial_impact=sim_output.financial_impact,
                    conflict_report=(
                        {"conflicts": sim_output.conflict_log}
                        if sim_output.conflict_log
                        else None
                    ),
                )
                session.add(sim_result)

                # Complete simulation
                sim = session.get(Simulation, uuid.UUID(simulation_id))
                if sim:
                    sim.status = SimulationStatus.COMPLETED
                    sim.completed_at = datetime.utcnow()

                session.commit()

        return {"status": "COMPLETED", "simulation_id": simulation_id}

    except Exception as exc:
        logger.exception("Async simulation failed: %s", exc)
        with Session(engine) as session:
            sim = session.get(Simulation, uuid.UUID(simulation_id))
            if sim:
                sim.status = SimulationStatus.FAILED
                session.commit()
        raise
    finally:
        engine.dispose()
