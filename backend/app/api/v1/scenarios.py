from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import scenario_service
from app.schemas.simulation import ScenarioCreateRequest, ScenarioResponse

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


@router.post("", response_model=ScenarioResponse, status_code=201)
async def create_scenario(body: ScenarioCreateRequest, db: AsyncSession = Depends(get_db)):
    scenario = await scenario_service.create_scenario(
        name=body.name,
        description=body.description,
        simulation_ids=body.simulation_ids,
        db=db,
    )
    return ScenarioResponse(
        id=str(scenario.id),
        name=scenario.name,
        description=scenario.description,
        simulation_ids=scenario.simulation_ids,
        comparison_result=scenario.comparison_result,
        created_at=scenario.created_at.isoformat(),
    )


@router.get("", response_model=list[ScenarioResponse])
async def list_scenarios(db: AsyncSession = Depends(get_db)):
    scenarios = await scenario_service.list_scenarios(db)
    return [
        ScenarioResponse(
            id=str(s.id),
            name=s.name,
            description=s.description,
            simulation_ids=s.simulation_ids,
            comparison_result=s.comparison_result,
            created_at=s.created_at.isoformat(),
        )
        for s in scenarios
    ]


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(scenario_id: str, db: AsyncSession = Depends(get_db)):
    scenario = await scenario_service.get_scenario(scenario_id, db)
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    return ScenarioResponse(
        id=str(scenario.id),
        name=scenario.name,
        description=scenario.description,
        simulation_ids=scenario.simulation_ids,
        comparison_result=scenario.comparison_result,
        created_at=scenario.created_at.isoformat(),
    )


@router.delete("/{scenario_id}")
async def delete_scenario(scenario_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await scenario_service.delete_scenario(scenario_id, db)
    if not deleted:
        raise HTTPException(404, "Scenario not found")
    return {"status": "deleted"}
