from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import simulation_service, dataset_service, rule_service
from app.schemas.simulation import (
    SimulationCreateRequest,
    SimulationResponse,
    SimulationResultResponse,
)

router = APIRouter(prefix="/simulations", tags=["Simulations"])


async def _build_response(sim, db: AsyncSession) -> SimulationResponse:
    """Build a SimulationResponse with resolved dataset and rule set names."""
    dataset_name = None
    rule_set_name = None
    try:
        ds = await dataset_service.get_dataset(str(sim.dataset_id), db)
        if ds:
            dataset_name = ds.filename
    except Exception:
        pass
    try:
        rs = await rule_service.get_rule_set(str(sim.rule_set_id), db)
        if rs:
            rule_set_name = rs.name
    except Exception:
        pass
    return SimulationResponse(
        id=str(sim.id),
        scenario_name=sim.scenario_name,
        dataset_id=str(sim.dataset_id),
        rule_set_id=str(sim.rule_set_id),
        dataset_name=dataset_name,
        rule_set_name=rule_set_name,
        version=sim.version,
        status=sim.status.value,
        created_at=sim.created_at.isoformat(),
        completed_at=sim.completed_at.isoformat() if sim.completed_at else None,
    )


@router.post("", response_model=SimulationResponse, status_code=201)
async def create_simulation(body: SimulationCreateRequest, db: AsyncSession = Depends(get_db)):
    sim = await simulation_service.create_simulation(
        scenario_name=body.scenario_name,
        dataset_id=body.dataset_id,
        rule_set_id=body.rule_set_id,
        parameters=body.parameters,
        db=db,
    )
    return await _build_response(sim, db)


@router.get("", response_model=list[SimulationResponse])
async def list_simulations(db: AsyncSession = Depends(get_db)):
    sims = await simulation_service.list_simulations(db)
    return [await _build_response(s, db) for s in sims]


@router.get("/{sim_id}", response_model=SimulationResponse)
async def get_simulation(sim_id: str, db: AsyncSession = Depends(get_db)):
    sim = await simulation_service.get_simulation(sim_id, db)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    return await _build_response(sim, db)


@router.get("/{sim_id}/results", response_model=list[SimulationResultResponse])
async def get_simulation_results(sim_id: str, db: AsyncSession = Depends(get_db)):
    sim = await simulation_service.get_simulation(sim_id, db)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    results = await simulation_service.get_simulation_results(sim_id, db)
    return [
        SimulationResultResponse(
            id=str(r.id),
            simulation_id=str(r.simulation_id),
            summary_stats=r.summary_stats,
            segment_analysis=r.segment_analysis,
            financial_impact=r.financial_impact,
            conflict_report=r.conflict_report,
            created_at=r.created_at.isoformat(),
        )
        for r in results
    ]


@router.delete("/{sim_id}")
async def delete_simulation(sim_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await simulation_service.delete_simulation(sim_id, db)
    if not deleted:
        raise HTTPException(404, "Simulation not found")
    return {"status": "deleted"}
