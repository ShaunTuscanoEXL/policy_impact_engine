import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.simulation import Simulation, SimulationResult, SimulationStatus


async def create_simulation(
    scenario_name: str,
    dataset_id: str,
    rule_set_id: str,
    parameters: dict | None,
    db: AsyncSession,
) -> Simulation:
    sim = Simulation(
        scenario_name=scenario_name,
        dataset_id=uuid.UUID(dataset_id),
        rule_set_id=uuid.UUID(rule_set_id),
        parameters=parameters,
    )
    db.add(sim)
    await db.commit()
    await db.refresh(sim)
    return sim


async def list_simulations(db: AsyncSession) -> list[Simulation]:
    result = await db.execute(select(Simulation).order_by(Simulation.created_at.desc()))
    return list(result.scalars().all())


async def get_simulation(sim_id: str, db: AsyncSession) -> Simulation | None:
    try:
        parsed_id = uuid.UUID(sim_id)
    except ValueError:
        return None
    result = await db.execute(
        select(Simulation)
        .where(Simulation.id == parsed_id)
        .options(selectinload(Simulation.results))
    )
    return result.scalar_one_or_none()


async def get_simulation_results(sim_id: str, db: AsyncSession) -> list[SimulationResult]:
    try:
        parsed_id = uuid.UUID(sim_id)
    except ValueError:
        return []
    result = await db.execute(
        select(SimulationResult).where(SimulationResult.simulation_id == parsed_id)
    )
    return list(result.scalars().all())


async def update_simulation_status(
    sim_id: str, status: SimulationStatus, db: AsyncSession
) -> Simulation | None:
    sim = await get_simulation(sim_id, db)
    if not sim:
        return None
    sim.status = status
    if status == SimulationStatus.COMPLETED:
        sim.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(sim)
    return sim


async def save_simulation_result(
    sim_id: str,
    summary_stats: dict,
    segment_analysis: dict | None,
    customer_diffs_path: str | None,
    financial_impact: dict | None,
    conflict_report: dict | None,
    db: AsyncSession,
) -> SimulationResult:
    result = SimulationResult(
        simulation_id=uuid.UUID(sim_id),
        summary_stats=summary_stats,
        segment_analysis=segment_analysis,
        customer_diffs_path=customer_diffs_path,
        financial_impact=financial_impact,
        conflict_report=conflict_report,
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return result


async def delete_simulation(sim_id: str, db: AsyncSession) -> bool:
    sim = await get_simulation(sim_id, db)
    if not sim:
        return False
    await db.delete(sim)
    await db.commit()
    return True
