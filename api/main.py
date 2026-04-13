"""
BOQ 자동화 시스템 FastAPI 앱 (Phase 5)

실행: uvicorn api.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.routes.boq import router as boq_router
from api.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="BOQ 자동화 시스템",
    description="Agentic AI + 2D/3D 하이브리드 건설 물량 자동 산출",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(boq_router)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "BOQ Automation System"}
