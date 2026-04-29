"""Live Rule Repository endpoints — list/create repos, list/get versions,
and download generated Python."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.live_repo import (
    CreateRepositoryRequest,
    RepositoryDetail,
    RepositorySummary,
    VersionDetail,
    VersionSummary,
)
from app.services import live_repo_service as svc

router = APIRouter(prefix="/live-repo", tags=["Live Rule Repository"])


def _repo_summary(r) -> RepositorySummary:
    return RepositorySummary(
        id=str(r.id),
        name=r.name,
        product=r.product,
        jurisdiction=r.jurisdiction,
        description=r.description,
        current_version=r.current_version,
        created_at=r.created_at.isoformat(),
        updated_at=r.updated_at.isoformat(),
    )


def _version_summary(v) -> VersionSummary:
    return VersionSummary(
        id=str(v.id),
        version_number=v.version_number,
        parent_version_id=str(v.parent_version_id) if v.parent_version_id else None,
        source_brd_id=str(v.source_brd_id) if v.source_brd_id else None,
        merge_proposal_id=str(v.merge_proposal_id) if v.merge_proposal_id else None,
        summary=v.summary,
        rule_count=len(v.rule_snapshot or []),
        created_at=v.created_at.isoformat(),
        created_by=v.created_by,
    )


@router.get("", response_model=list[RepositorySummary])
async def list_repos(db: AsyncSession = Depends(get_db)):
    repos = await svc.list_repositories(db)
    return [_repo_summary(r) for r in repos]


@router.post("", response_model=RepositorySummary, status_code=201)
async def create_repo(payload: CreateRepositoryRequest, db: AsyncSession = Depends(get_db)):
    repo = await svc.create_repository(
        db,
        name=payload.name,
        product=payload.product,
        jurisdiction=payload.jurisdiction,
        description=payload.description,
    )
    return _repo_summary(repo)


@router.get("/{repo_id}", response_model=RepositoryDetail)
async def get_repo(repo_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = await svc.get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return RepositoryDetail(
        **_repo_summary(repo).model_dump(),
        versions=[_version_summary(v) for v in repo.versions],
    )


@router.get("/{repo_id}/versions", response_model=list[VersionSummary])
async def list_versions(repo_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = await svc.get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return [_version_summary(v) for v in repo.versions]


@router.get("/{repo_id}/version/{n}", response_model=VersionDetail)
async def get_version(repo_id: uuid.UUID, n: int, db: AsyncSession = Depends(get_db)):
    version = await svc.get_version(db, repo_id, n)
    if version is None:
        raise HTTPException(status_code=404, detail=f"Version {n} not found")
    return VersionDetail(
        **_version_summary(version).model_dump(),
        rule_snapshot=list(version.rule_snapshot or []),
    )


@router.get("/{repo_id}/export.py")
async def export_head_python(repo_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    py = await svc.export_python(db, repo_id, version_number=None)
    if py is None:
        raise HTTPException(status_code=404, detail="Repository or version not found")
    return Response(
        content=py,
        media_type="text/x-python",
        headers={"Content-Disposition": f'attachment; filename="rules_repo_{repo_id}.py"'},
    )


@router.get("/{repo_id}/version/{n}/export.py")
async def export_version_python(
    repo_id: uuid.UUID, n: int, db: AsyncSession = Depends(get_db)
):
    py = await svc.export_python(db, repo_id, version_number=n)
    if py is None:
        raise HTTPException(status_code=404, detail="Repository or version not found")
    return Response(
        content=py,
        media_type="text/x-python",
        headers={"Content-Disposition": f'attachment; filename="rules_repo_{repo_id}_v{n}.py"'},
    )
