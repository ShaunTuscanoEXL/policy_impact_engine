from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import brd_service
from app.schemas.brd import BrdUploadResponse, BrdListResponse
from app.models.rule import RuleSet, Rule
from app.models.simulation import Simulation

router = APIRouter(prefix="/brds", tags=["BRDs"])


@router.post("/upload", response_model=BrdUploadResponse)
async def upload_brd(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename.endswith((".pdf", ".docx")):
        raise HTTPException(400, "Only PDF and DOCX files are supported")
    brd = await brd_service.upload_brd(file, db)
    return BrdUploadResponse(
        id=str(brd.id),
        filename=brd.filename,
        file_type=brd.file_type.value,
        created_at=brd.created_at.isoformat(),
    )


@router.get("", response_model=list[BrdListResponse])
async def list_brds(db: AsyncSession = Depends(get_db)):
    brds = await brd_service.list_brds(db)
    return [BrdListResponse(
        id=str(b.id), filename=b.filename, file_type=b.file_type.value,
        created_at=b.created_at.isoformat(),
    ) for b in brds]


@router.get("/{brd_id}")
async def get_brd(brd_id: str, db: AsyncSession = Depends(get_db)):
    brd = await brd_service.get_brd(brd_id, db)
    if not brd:
        raise HTTPException(404, "BRD not found")
    return {
        "id": str(brd.id),
        "filename": brd.filename,
        "file_type": brd.file_type.value,
        "parsed_content": brd.parsed_content,
        "metadata": brd.metadata_json,
        "created_at": brd.created_at.isoformat(),
    }


@router.get("/{brd_id}/workflow")
async def get_brd_workflow(brd_id: str, db: AsyncSession = Depends(get_db)):
    """Get workflow status for a BRD: latest rule set and simulation."""
    brd = await brd_service.get_brd(brd_id, db)
    if not brd:
        raise HTTPException(404, "BRD not found")

    # Get latest rule set for this BRD
    rs_result = await db.execute(
        select(RuleSet)
        .where(RuleSet.brd_document_id == brd.id)
        .order_by(RuleSet.version.desc())
        .limit(1)
    )
    rule_set = rs_result.scalar_one_or_none()

    rule_set_data = None
    simulation_data = None

    if rule_set:
        rules_count = await db.execute(
            select(func.count()).select_from(Rule).where(Rule.rule_set_id == rule_set.id)
        )
        rule_set_data = {
            "id": str(rule_set.id),
            "status": rule_set.status.value,
            "rules_count": rules_count.scalar() or 0,
        }

        # Get latest simulation for this rule set
        sim_result = await db.execute(
            select(Simulation)
            .where(Simulation.rule_set_id == rule_set.id)
            .order_by(Simulation.created_at.desc())
            .limit(1)
        )
        simulation = sim_result.scalar_one_or_none()
        if simulation:
            simulation_data = {
                "id": str(simulation.id),
                "status": simulation.status.value,
                "scenario_name": simulation.scenario_name,
            }

    return {
        "brd_id": brd_id,
        "rule_set": rule_set_data,
        "simulation": simulation_data,
    }


@router.delete("/{brd_id}")
async def delete_brd(brd_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await brd_service.delete_brd(brd_id, db)
    if not deleted:
        raise HTTPException(404, "BRD not found")
    return {"status": "deleted"}
