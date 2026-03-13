import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.simulation import Scenario


async def create_scenario(
    name: str,
    description: str | None,
    simulation_ids: list[str],
    db: AsyncSession,
) -> Scenario:
    scenario = Scenario(
        name=name,
        description=description,
        simulation_ids=simulation_ids,
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return scenario


async def list_scenarios(db: AsyncSession) -> list[Scenario]:
    result = await db.execute(select(Scenario).order_by(Scenario.created_at.desc()))
    return list(result.scalars().all())


async def get_scenario(scenario_id: str, db: AsyncSession) -> Scenario | None:
    try:
        parsed_id = uuid.UUID(scenario_id)
    except ValueError:
        return None
    result = await db.execute(
        select(Scenario).where(Scenario.id == parsed_id)
    )
    return result.scalar_one_or_none()


async def delete_scenario(scenario_id: str, db: AsyncSession) -> bool:
    scenario = await get_scenario(scenario_id, db)
    if not scenario:
        return False
    await db.delete(scenario)
    await db.commit()
    return True
