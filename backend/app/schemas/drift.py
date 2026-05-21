"""Slice 10 drift report schema."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DriftReportResponse(BaseModel):
    repository_id: str
    production_version_id: str
    production_version_number: int
    computed_at: str
    predicted_source: dict[str, Any] | None = None
    observed: dict[str, Any]
    drift: dict[str, Any]
    warnings: list[str] = []
