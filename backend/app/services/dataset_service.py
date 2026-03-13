import uuid
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.dataset import Dataset, DatasetFileType


async def upload_dataset(
    file: UploadFile, name: str, description: str | None, db: AsyncSession
) -> Dataset:
    file_ext = Path(file.filename).suffix.lower()
    file_type = DatasetFileType.CSV if file_ext == ".csv" else DatasetFileType.JSON

    file_id = str(uuid.uuid4())
    upload_dir = Path(settings.upload_dir) / "datasets"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{file_id}{file_ext}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Read with Pandas for profiling
    if file_type == DatasetFileType.CSV:
        df = pd.read_csv(file_path)
    else:
        df = pd.read_json(file_path)

    # Generate column schema
    column_schema = {}
    for col in df.columns:
        column_schema[col] = {
            "dtype": str(df[col].dtype),
            "non_null_count": int(df[col].notna().sum()),
            "null_count": int(df[col].isna().sum()),
            "unique_count": int(df[col].nunique()),
        }

    # Generate data profile for numeric columns
    data_profile = {}
    for col in df.select_dtypes(include="number").columns:
        data_profile[col] = {
            "min": round(float(df[col].min()), 4),
            "max": round(float(df[col].max()), 4),
            "mean": round(float(df[col].mean()), 4),
            "median": round(float(df[col].median()), 4),
            "std": round(float(df[col].std()), 4),
            "q25": round(float(df[col].quantile(0.25)), 4),
            "q75": round(float(df[col].quantile(0.75)), 4),
        }

    # For categorical columns, add value counts
    for col in df.select_dtypes(include=["object", "category"]).columns:
        data_profile[col] = {
            "value_counts": df[col].value_counts().head(10).to_dict(),
        }

    # Sample data (first 10 rows as dict)
    sample_data = df.head(10).to_dict(orient="records")
    # Convert numpy types to Python native for JSON serialization
    sample_data = _convert_numpy_types(sample_data)

    dataset = Dataset(
        name=name,
        description=description,
        file_path=str(file_path),
        file_type=file_type,
        row_count=len(df),
        column_schema=column_schema,
        sample_data=sample_data,
        data_profile=data_profile,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


def _convert_numpy_types(obj):
    """Recursively convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    return obj


async def list_datasets(db: AsyncSession) -> list[Dataset]:
    result = await db.execute(select(Dataset).order_by(Dataset.created_at.desc()))
    return list(result.scalars().all())


async def get_dataset(dataset_id: str, db: AsyncSession) -> Dataset | None:
    result = await db.execute(
        select(Dataset).where(Dataset.id == uuid.UUID(dataset_id))
    )
    return result.scalar_one_or_none()


async def delete_dataset(dataset_id: str, db: AsyncSession) -> bool:
    ds = await get_dataset(dataset_id, db)
    if not ds:
        return False
    file_path = Path(ds.file_path)
    if file_path.exists():
        file_path.unlink()
    await db.delete(ds)
    await db.commit()
    return True
