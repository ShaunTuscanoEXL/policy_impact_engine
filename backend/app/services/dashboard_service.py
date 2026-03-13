from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.brd import BrdDocument
from app.models.dataset import Dataset
from app.models.simulation import Simulation, SimulationResult, SimulationStatus
from app.models.simulation import Scenario


async def get_dashboard_stats(db: AsyncSession) -> dict:
    # Count BRDs
    brd_count = await db.scalar(select(func.count(BrdDocument.id)))

    # Count Datasets
    dataset_count = await db.scalar(select(func.count(Dataset.id)))

    # Count Simulations
    sim_count = await db.scalar(select(func.count(Simulation.id)))

    # Count Scenarios
    scenario_count = await db.scalar(select(func.count(Scenario.id)))

    # Average impact rate from completed simulations
    completed_results = await db.execute(
        select(SimulationResult.summary_stats)
        .join(Simulation)
        .where(Simulation.status == SimulationStatus.COMPLETED)
    )
    results_data = completed_results.scalars().all()

    avg_impact = 0.0
    if results_data:
        rates = []
        for stats in results_data:
            if isinstance(stats, dict) and "affected_percentage" in stats:
                rates.append(stats["affected_percentage"])
        if rates:
            avg_impact = round(sum(rates) / len(rates), 2)

    # Recent simulations (last 10)
    recent_sims = await db.execute(
        select(Simulation)
        .order_by(Simulation.created_at.desc())
        .limit(10)
    )
    recent = [
        {
            "id": str(s.id),
            "scenario_name": s.scenario_name,
            "status": s.status.value,
            "dataset_id": str(s.dataset_id),
            "rule_set_id": str(s.rule_set_id),
            "created_at": s.created_at.isoformat(),
        }
        for s in recent_sims.scalars().all()
    ]

    return {
        "total_brds": brd_count or 0,
        "total_datasets": dataset_count or 0,
        "total_simulations": sim_count or 0,
        "active_scenarios": scenario_count or 0,
        "avg_impact_rate": avg_impact,
        "recent_simulations": recent,
    }
