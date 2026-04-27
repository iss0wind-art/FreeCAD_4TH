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


_NEW_TABLES_SQL = """
    CREATE TABLE IF NOT EXISTS member_specs (
        symbol          TEXT NOT NULL,
        project_scope   TEXT NOT NULL DEFAULT 'global',
        member_type     TEXT NOT NULL,
        subtype         TEXT,
        width           REAL NOT NULL DEFAULT 0,
        height          REAL NOT NULL DEFAULT 0,
        depth           REAL NOT NULL DEFAULT 0,
        thickness       REAL NOT NULL DEFAULT 0,
        length          REAL NOT NULL DEFAULT 0,
        wall_thickness  REAL NOT NULL DEFAULT 0,
        remark          TEXT,
        source          TEXT,
        created_at      TEXT NOT NULL,
        updated_at      TEXT,
        PRIMARY KEY (symbol, project_scope),
        CHECK (member_type IN ('BEAM','COLUMN','SLAB','WALL','FOUNDATION')),
        CHECK (width >= 0 AND height >= 0 AND depth >= 0
               AND thickness >= 0 AND length >= 0 AND wall_thickness >= 0)
    );
    CREATE INDEX IF NOT EXISTS idx_specs_type  ON member_specs(member_type);
    CREATE INDEX IF NOT EXISTS idx_specs_scope ON member_specs(project_scope);
    CREATE INDEX IF NOT EXISTS idx_specs_symbol ON member_specs(symbol);

    CREATE TABLE IF NOT EXISTS projects (
        project_id     TEXT PRIMARY KEY,
        name           TEXT NOT NULL,
        units          TEXT NOT NULL DEFAULT 'mm',
        manifest_yaml  TEXT,
        manifest_hash  TEXT,
        grid_json      TEXT,
        floors_json    TEXT,
        created_at     TEXT NOT NULL,
        updated_at     TEXT,
        CHECK (units IN ('mm','m'))
    );

    CREATE TABLE IF NOT EXISTS member_instances (
        instance_id    TEXT NOT NULL,
        project_id     TEXT NOT NULL,
        spec_symbol    TEXT NOT NULL,
        member_type    TEXT NOT NULL,
        subtype        TEXT,
        floor_id       TEXT NOT NULL,
        placement_json TEXT NOT NULL,
        rotation       REAL NOT NULL DEFAULT 0,
        z_offset       REAL NOT NULL DEFAULT 0,
        z_base         REAL NOT NULL,
        created_at     TEXT NOT NULL,
        PRIMARY KEY (project_id, instance_id),
        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
        CHECK (member_type IN ('BEAM','COLUMN','SLAB','WALL','FOUNDATION'))
    );
    CREATE INDEX IF NOT EXISTS idx_inst_project ON member_instances(project_id);
    CREATE INDEX IF NOT EXISTS idx_inst_floor   ON member_instances(project_id, floor_id);
    CREATE INDEX IF NOT EXISTS idx_inst_type    ON member_instances(member_type);
"""


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
        for stmt in _NEW_TABLES_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
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
        for stmt in _NEW_TABLES_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                client.execute(stmt)


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


# ─────────────────────────────────────────────────────────────
# member_specs CRUD
# ─────────────────────────────────────────────────────────────
def upsert_member_spec(spec: dict) -> None:
    """member_specs 삽입/갱신 (symbol + project_scope 복합 PK)."""
    now = datetime.now(timezone.utc).isoformat()
    sql = """
        INSERT INTO member_specs
            (symbol, project_scope, member_type, subtype,
             width, height, depth, thickness, length, wall_thickness,
             remark, source, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(symbol, project_scope) DO UPDATE SET
            member_type=excluded.member_type,
            subtype=excluded.subtype,
            width=excluded.width, height=excluded.height,
            depth=excluded.depth, thickness=excluded.thickness,
            length=excluded.length, wall_thickness=excluded.wall_thickness,
            remark=excluded.remark, source=excluded.source,
            updated_at=excluded.updated_at
    """
    symbol = spec.get("symbol") or ""
    member_type = spec.get("member_type") or ""
    if not symbol or not member_type:
        raise ValueError(f"upsert_member_spec: symbol 과 member_type 은 필수입니다 (got {spec!r})")

    params = (
        symbol, spec.get("project_scope", "global"),
        member_type, spec.get("subtype"),
        spec.get("width", 0), spec.get("height", 0),
        spec.get("depth", 0), spec.get("thickness", 0),
        spec.get("length", 0), spec.get("wall_thickness", 0),
        spec.get("remark"), spec.get("source", "USER"),
        now, now,
    )
    with _get_sqlite_conn() as conn:
        conn.execute(sql, params)
        conn.commit()


def get_member_spec(symbol: str, project_scope: str = "global") -> Optional[dict]:
    sql = """
        SELECT * FROM member_specs
        WHERE symbol = ? AND project_scope = ?
        LIMIT 1
    """
    with _get_sqlite_conn() as conn:
        row = conn.execute(sql, (symbol, project_scope)).fetchone()
        return dict(row) if row else None


def list_member_specs(member_type: Optional[str] = None) -> list[dict]:
    if member_type:
        sql = "SELECT * FROM member_specs WHERE member_type = ? ORDER BY symbol"
        params: tuple = (member_type,)
    else:
        sql = "SELECT * FROM member_specs ORDER BY member_type, symbol"
        params = ()
    with _get_sqlite_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_spec_map(symbols: list[str], project_scope: str = "global") -> dict[str, dict]:
    """symbol 목록 → {symbol: spec_dict} 일괄 조회."""
    if not symbols:
        return {}
    placeholders = ",".join("?" * len(symbols))
    sql = f"""
        SELECT * FROM member_specs
        WHERE symbol IN ({placeholders}) AND project_scope = ?
    """
    with _get_sqlite_conn() as conn:
        rows = conn.execute(sql, (*symbols, project_scope)).fetchall()
        return {dict(r)["symbol"]: dict(r) for r in rows}


# ─────────────────────────────────────────────────────────────
# projects CRUD
# ─────────────────────────────────────────────────────────────
def create_project(project: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    sql = """
        INSERT INTO projects
            (project_id, name, units, manifest_yaml, manifest_hash,
             grid_json, floors_json, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """
    params = (
        project["project_id"], project["name"],
        project.get("units", "mm"),
        project.get("manifest_yaml"), project.get("manifest_hash"),
        project.get("grid_json"), project.get("floors_json"),
        now, now,
    )
    with _get_sqlite_conn() as conn:
        conn.execute(sql, params)
        conn.commit()


def get_project(project_id: str) -> Optional[dict]:
    sql = "SELECT * FROM projects WHERE project_id = ? LIMIT 1"
    with _get_sqlite_conn() as conn:
        row = conn.execute(sql, (project_id,)).fetchone()
        return dict(row) if row else None


# ─────────────────────────────────────────────────────────────
# member_instances CRUD
# ─────────────────────────────────────────────────────────────
def insert_member_instances(instances: list[dict]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    sql = """
        INSERT OR REPLACE INTO member_instances
            (instance_id, project_id, spec_symbol, member_type, subtype,
             floor_id, placement_json, rotation, z_offset, z_base, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """
    rows = [
        (
            inst["instance_id"], inst["project_id"],
            inst["spec_symbol"], inst["member_type"],
            inst.get("subtype"),
            inst["floor_id"], inst["placement_json"],
            inst.get("rotation", 0), inst.get("z_offset", 0),
            inst["z_base"], now,
        )
        for inst in instances
    ]
    with _get_sqlite_conn() as conn:
        conn.executemany(sql, rows)
        conn.commit()
