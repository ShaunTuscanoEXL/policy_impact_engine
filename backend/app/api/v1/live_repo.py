"""Live Rule Repository endpoints — list/create repos, list/get versions,
and download generated Python."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.live_repo import (
    BackfillResponse,
    CreateRepositoryRequest,
    ImportPythonRequest,
    ImportPythonResponse,
    ProposeFromBrdRequest,
    ProposeFromBrdResponse,
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


# ── Slice 1: BRD upload → proposal helper + admin backfill ───────────────


@router.post("/propose-from-brd", response_model=ProposeFromBrdResponse, status_code=201)
async def propose_from_brd_endpoint(
    payload: ProposeFromBrdRequest, db: AsyncSession = Depends(get_db)
):
    """One-shot helper: takes a BRD id, locates its latest rule_set,
    finds (or creates) the default live repo for (product, jurisdiction),
    and creates a merge proposal. If the live repo is empty, auto-applies
    the proposal immediately so the BRD baselines the repository as v1."""
    try:
        proposal, version = await svc.propose_from_brd(
            db,
            brd_id=uuid.UUID(payload.brd_id),
            repository_id=uuid.UUID(payload.repository_id) if payload.repository_id else None,
            product=payload.product,
            jurisdiction=payload.jurisdiction,
            auto_apply_when_empty=payload.auto_apply_when_empty,
            decided_by=payload.decided_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProposeFromBrdResponse(
        proposal_id=str(proposal.id),
        repository_id=str(proposal.repository_id),
        auto_applied=version is not None,
        new_version_number=version.version_number if version else None,
        summary=(version.summary if version else proposal.summary),
    )


@router.post("/admin/backfill", response_model=BackfillResponse)
async def backfill_classify_all_rules(db: AsyncSession = Depends(get_db)):
    """Admin: classify every Rule that's missing canonical_key/subsystem.

    Idempotent — safe to run multiple times. Should be invoked once
    after deploying slice 1 against an existing database.
    """
    n = await svc.backfill_all_rules(db)
    return BackfillResponse(rules_classified=n)


@router.post("/{repo_id}/import", response_model=ImportPythonResponse, status_code=201)
async def import_python(
    repo_id: uuid.UUID,
    payload: ImportPythonRequest,
    db: AsyncSession = Depends(get_db),
):
    """Slice 3: upload a Python rules module (codegen-format) and
    install it as a new repository version. Trusted-source flow per
    the architecture decision — rules are NOT routed through the
    merge engine and the upload directly becomes the new HEAD.
    """
    try:
        new_version, warnings, count = await svc.import_python_as_version(
            db,
            repository_id=repo_id,
            source=payload.source,
            decided_by=payload.decided_by,
            summary_override=payload.summary,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ImportPythonResponse(
        new_version_number=new_version.version_number,
        new_version_id=str(new_version.id),
        rules_imported=count,
        warnings=warnings,
        summary=new_version.summary or "",
    )
