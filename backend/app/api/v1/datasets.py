from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.dataset import (
    DatasetListResponse,
    DatasetMappingRequest,
    DatasetProfileResponse,
    DatasetUploadResponse,
)
from app.services import dataset_service

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.post("/upload", response_model=DatasetUploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.endswith((".csv", ".json")):
        raise HTTPException(400, "Only CSV and JSON files are supported")
    ds = await dataset_service.upload_dataset(file, name, description, db)
    # Auto-detect column mapping for immediate feedback
    detected = None
    try:
        detected = await dataset_service.detect_column_mapping(ds)
    except Exception:
        pass  # Detection failure is non-critical
    return DatasetUploadResponse(
        id=str(ds.id),
        name=ds.name,
        file_type=ds.file_type.value,
        row_count=ds.row_count,
        column_schema=ds.column_schema,
        sample_data=ds.sample_data,
        column_mapping=detected,
        created_at=ds.created_at.isoformat(),
    )


@router.get("", response_model=list[DatasetListResponse])
async def list_datasets(db: AsyncSession = Depends(get_db)):
    datasets = await dataset_service.list_datasets(db)
    return [
        DatasetListResponse(
            id=str(d.id),
            name=d.name,
            description=d.description,
            file_type=d.file_type.value,
            row_count=d.row_count,
            created_at=d.created_at.isoformat(),
            column_mapping=d.column_mapping,
        )
        for d in datasets
    ]


@router.get("/{dataset_id}", response_model=DatasetProfileResponse)
async def get_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    ds = await dataset_service.get_dataset(dataset_id, db)
    if not ds:
        raise HTTPException(404, "Dataset not found")
    return DatasetProfileResponse(
        id=str(ds.id),
        name=ds.name,
        description=ds.description,
        file_type=ds.file_type.value,
        row_count=ds.row_count,
        column_schema=ds.column_schema,
        data_profile=ds.data_profile,
        sample_data=ds.sample_data,
        column_mapping=ds.column_mapping,
        baseline_config=ds.baseline_config,
        created_at=ds.created_at.isoformat(),
    )


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await dataset_service.delete_dataset(dataset_id, db)
    if not deleted:
        raise HTTPException(404, "Dataset not found")
    return {"status": "deleted"}


@router.get("/{dataset_id}/detect-mapping")
async def detect_mapping_endpoint(dataset_id: str, db: AsyncSession = Depends(get_db)):
    ds = await dataset_service.get_dataset(dataset_id, db)
    if not ds:
        raise HTTPException(404, "Dataset not found")
    mapping = await dataset_service.detect_column_mapping(ds)
    return mapping


@router.put("/{dataset_id}/mapping")
async def save_mapping(
    dataset_id: str,
    request: DatasetMappingRequest,
    db: AsyncSession = Depends(get_db),
):
    ds = await dataset_service.get_dataset(dataset_id, db)
    if not ds:
        raise HTTPException(404, "Dataset not found")
    required = ["score_field", "income_field", "amount_field", "dti_field"]
    for field in required:
        if not request.column_mapping.get(field):
            raise HTTPException(400, f"Required field '{field}' not mapped")
    updated = await dataset_service.save_mapping(ds, request.column_mapping, request.baseline_config, db)
    return {"status": "saved", "column_mapping": updated.column_mapping, "baseline_config": updated.baseline_config}
