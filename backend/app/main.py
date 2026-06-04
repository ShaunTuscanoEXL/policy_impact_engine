from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.api.v1.brds import router as brds_router
from app.api.v1.rules import router as rules_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.test_cases import router as test_cases_router
from app.api.v1.loan_records import router as loan_records_router
from app.api.v1.live_repo import router as live_repo_router
from app.api.v1.merge import router as merge_router
from app.api.v1.impact import router as impact_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models.brd
    import app.models.rule
    import app.models.test_case
    import app.models.loan_record
    import app.models.live_repo  # registers LiveRuleRepository / Version / Entry
    import app.models.merge      # registers MergeProposal / MergeProposalItem
    import app.models.impact     # registers ImpactRun
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Additive auto-migrations — new columns added in later slices that
        # create_all() won't apply to a pre-existing table. Idempotent on
        # both Postgres (IF NOT EXISTS) and other dialects (catch + ignore).
        await _apply_additive_migrations(conn)

    # Backfill: for repos that existed before slice A landed,
    # set production_version_id := highest version's id so the UI
    # has something to render. Idempotent.
    from app.database import async_session
    from app.services.live_repo_service import backfill_production_versions
    async with async_session() as db:
        try:
            await backfill_production_versions(db)
        except Exception:
            # Backfill should never block startup
            pass
    yield


async def _apply_additive_migrations(conn) -> None:
    """Run idempotent ALTER TABLE statements for columns introduced after
    the table was first created. Each statement is wrapped so a failure
    on one doesn't block the rest. Postgres-aware via IF NOT EXISTS;
    falls back gracefully on other dialects."""
    from sqlalchemy import text
    statements = [
        # Slice A: production version pointer
        "ALTER TABLE live_rule_repositories "
        "ADD COLUMN IF NOT EXISTS production_version_id UUID NULL",
        "ALTER TABLE live_rule_repositories "
        "ADD COLUMN IF NOT EXISTS production_promoted_at TIMESTAMP NULL",
        "ALTER TABLE live_rule_repositories "
        "ADD COLUMN IF NOT EXISTS production_promoted_by VARCHAR(128) NULL",
    ]
    for stmt in statements:
        try:
            await conn.execute(text(stmt))
        except Exception as e:
            # Log + continue; create_all() above already handles fresh DBs.
            import logging
            logging.getLogger(__name__).warning(
                "Additive migration skipped (%s): %s", stmt[:60], e
            )

app = FastAPI(title="Policy Impact Engine", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(brds_router, prefix="/api/v1")
app.include_router(rules_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(test_cases_router, prefix="/api/v1")
app.include_router(loan_records_router, prefix="/api/v1")
app.include_router(live_repo_router, prefix="/api/v1")
app.include_router(merge_router, prefix="/api/v1")
app.include_router(impact_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
