from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import brd_service
from app.schemas.brd import BrdUploadResponse, BrdListResponse

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


@router.delete("/{brd_id}")
async def delete_brd(brd_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await brd_service.delete_brd(brd_id, db)
    if not deleted:
        raise HTTPException(404, "BRD not found")
    return {"status": "deleted"}
