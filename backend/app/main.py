from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.brds import router as brds_router
from app.api.v1.datasets import router as datasets_router

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


@app.get("/health")
async def health():
    return {"status": "ok"}
