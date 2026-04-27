"""
BOQ 자동화 시스템 FastAPI 앱

실행: uvicorn api.main:app --reload
뷰어: http://localhost:8000/
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes.boq import router as boq_router
from api.routes.specs import router as specs_router
from api.routes.projects import router as projects_router
from api.database import init_db

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


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
app.include_router(specs_router)
app.include_router(projects_router)

# Three.js 뷰어 정적 파일 서빙
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_viewer() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "BOQ Automation System"}
