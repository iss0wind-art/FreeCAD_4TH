"""
데이터베이스 레이어 (Phase 5)

Turso (libsql) 우선, 환경 변수 없으면 SQLite 폴백.
TURSO_URL / TURSO_AUTH_TOKEN 환경 변수로 제어.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from api.models import BOQItemDTO, BOQJobResponse

DB_PATH = Path("output/boq.db")
_USE_TURSO = bool(os.getenv("TURSO_URL"))


def _get_sqlite_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """테이블 초기화 (앱 시작 시 1회 호출)"""
    if _USE_TURSO:
        _init_turso()
    else:
        _init_sqlite()


def _init_sqlite() -> None:
    with _get_sqlite_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS boq_jobs (
                job_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                status TEXT NOT NULL,
                boq_items TEXT NOT NULL,
                total_volume_m3 REAL NOT NULL,
                total_formwork_m2 REAL NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def _init_turso() -> None:
    import libsql_client
    url = os.environ["TURSO_URL"]
    token = os.getenv("TURSO_AUTH_TOKEN", "")
    with libsql_client.create_client_sync(url=url, auth_token=token) as client:
        client.execute("""
            CREATE TABLE IF NOT EXISTS boq_jobs (
                job_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                status TEXT NOT NULL,
                boq_items TEXT NOT NULL,
                total_volume_m3 REAL NOT NULL,
                total_formwork_m2 REAL NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL
            )
        """)


def save_boq_job(
    job_id: str,
    project_id: str,
    status: str,
    boq_items: list[BOQItemDTO],
    total_volume_m3: float,
    total_formwork_m2: float,
    error: Optional[str] = None,
) -> None:
    """BOQ 작업 결과 저장"""
    items_json = json.dumps([item.model_dump() for item in boq_items])
    created_at = datetime.now(timezone.utc).isoformat()

    sql = """
        INSERT OR REPLACE INTO boq_jobs
        (job_id, project_id, status, boq_items, total_volume_m3, total_formwork_m2, error, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (job_id, project_id, status, items_json,
              total_volume_m3, total_formwork_m2, error, created_at)

    if _USE_TURSO:
        import libsql_client
        url = os.environ["TURSO_URL"]
        token = os.getenv("TURSO_AUTH_TOKEN", "")
        with libsql_client.create_client_sync(url=url, auth_token=token) as client:
            client.execute(sql, params)
    else:
        with _get_sqlite_conn() as conn:
            conn.execute(sql, params)
            conn.commit()


def get_boq_job(job_id: str) -> Optional[BOQJobResponse]:
    """저장된 BOQ 작업 조회"""
    sql = "SELECT * FROM boq_jobs WHERE job_id = ?"

    if _USE_TURSO:
        import libsql_client
        url = os.environ["TURSO_URL"]
        token = os.getenv("TURSO_AUTH_TOKEN", "")
        with libsql_client.create_client_sync(url=url, auth_token=token) as client:
            result = client.execute(sql, (job_id,))
            rows = result.rows
            if not rows:
                return None
            row = dict(zip([c.name for c in result.columns], rows[0]))
    else:
        with _get_sqlite_conn() as conn:
            row = conn.execute(sql, (job_id,)).fetchone()
            if row is None:
                return None
            row = dict(row)

    items = [BOQItemDTO(**item) for item in json.loads(row["boq_items"])]
    return BOQJobResponse(
        job_id=row["job_id"],
        project_id=row["project_id"],
        status=row["status"],
        created_at=row["created_at"],
        boq_items=items,
        total_volume_m3=row["total_volume_m3"],
        total_formwork_m2=row["total_formwork_m2"],
    )


def generate_job_id() -> str:
    return str(uuid.uuid4())
