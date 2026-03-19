from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.api.v1.brds import router as brds_router
from app.api.v1.rules import router as rules_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.test_cases import router as test_cases_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models.brd
    import app.models.rule
    import app.models.test_case
    import app.models.loan_record
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Policy Impact Engine", version="0.2.0", lifespan=lifespan)

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


@app.get("/health")
async def health():
    return {"status": "ok"}
