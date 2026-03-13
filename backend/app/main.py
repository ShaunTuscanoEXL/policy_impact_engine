from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.brds import router as brds_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.simulations import router as simulations_router
from app.api.v1.scenarios import router as scenarios_router
from app.api.v1.rules import router as rules_router
from app.api.v1.pipeline import router as pipeline_router

app = FastAPI(title="Policy Impact Engine", version="0.1.0")

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


@app.get("/health")
async def health():
    return {"status": "ok"}
