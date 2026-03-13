import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.brd import BrdDocument, FileType
from app.config import settings


async def upload_brd(file: UploadFile, db: AsyncSession) -> BrdDocument:
    file_ext = Path(file.filename).suffix.lower()
    file_type = FileType.PDF if file_ext == ".pdf" else FileType.DOCX

    file_id = str(uuid.uuid4())
    upload_dir = Path(settings.upload_dir) / "brds"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{file_id}{file_ext}"

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    total_bytes = 0
    with open(file_path, "wb") as f:
        while chunk := file.file.read(8192):
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                f.close()
                file_path.unlink(missing_ok=True)
                from fastapi import HTTPException
                raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_size_mb}MB limit")
            f.write(chunk)

    brd = BrdDocument(
        filename=file.filename,
        file_path=str(file_path),
        file_type=file_type,
    )
    db.add(brd)
    await db.commit()
    await db.refresh(brd)
    return brd


async def list_brds(db: AsyncSession) -> list[BrdDocument]:
    result = await db.execute(select(BrdDocument).order_by(BrdDocument.created_at.desc()))
    return list(result.scalars().all())


async def get_brd(brd_id: str, db: AsyncSession) -> BrdDocument | None:
    try:
        parsed_id = uuid.UUID(brd_id)
    except ValueError:
        return None
    result = await db.execute(select(BrdDocument).where(BrdDocument.id == parsed_id))
    return result.scalar_one_or_none()


async def delete_brd(brd_id: str, db: AsyncSession) -> bool:
    brd = await get_brd(brd_id, db)
    if not brd:
        return False
    # Delete file from disk
    file_path = Path(brd.file_path)
    if file_path.exists():
        file_path.unlink()
    await db.delete(brd)
    await db.commit()
    return True
