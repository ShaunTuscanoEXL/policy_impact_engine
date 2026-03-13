from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.api.v1.brds import router as brds_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.simulations import router as simulations_router
from app.api.v1.scenarios import router as scenarios_router
from app.api.v1.rules import router as rules_router
from app.api.v1.pipeline import router as pipeline_router
from app.api.v1.export import router as export_router
from app.api.v1.dashboard import router as dashboard_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import all models so Base.metadata knows about them
    import app.models.brd  # noqa: F401
    import app.models.dataset  # noqa: F401
    import app.models.rule  # noqa: F401
    import app.models.simulation  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Policy Impact Engine", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(brds_router, prefix="/api/v1")
app.include_router(datasets_router, prefix="/api/v1")
app.include_router(simulations_router, prefix="/api/v1")
app.include_router(scenarios_router, prefix="/api/v1")
app.include_router(rules_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(export_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
