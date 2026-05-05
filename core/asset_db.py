"""
3지국 자산 데이터베이스 (Jiguk-3 Asset DB)

방부장 친명 (2026-05-05): *"지금부터 하는 파싱이나 모든것들을 데이터베이스화해서,
우리의 자산으로 삼는다."*

위치: D:/06.3지국 전용방/jiguk3_assets.db
스키마: SQLite (단독 사용·확장 가능)
"""

import os
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = r"D:\06.3지국 전용방\jiguk3_assets.db"

SCHEMA = """
-- 강역 (단지·프로젝트 단위)
CREATE TABLE IF NOT EXISTS territories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,         -- 예: "부산 에코델타 24BL"
    description TEXT,
    base_path TEXT,                     -- 도면 폴더 경로
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 도면
CREATE TABLE IF NOT EXISTS drawings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    territory_id INTEGER,
    filename TEXT NOT NULL,
    name TEXT,                          -- 확장자 제외 도면명
    page_code TEXT,                     -- S30-471 등
    source_dir TEXT,                    -- 원본 하위 폴더
    size_bytes INTEGER,
    file_kind TEXT,                     -- DWG / DXF / PDF
    dxf_path TEXT,                      -- 변환된 DXF 경로
    indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (territory_id) REFERENCES territories(id),
    UNIQUE(territory_id, filename, source_dir)
);

-- 도면 카테고리·동 매핑
CREATE TABLE IF NOT EXISTS drawing_categories (
    drawing_id INTEGER,
    category_code TEXT,                 -- WALL_LIST, COLUMN_LIST 등
    category_label TEXT,
    PRIMARY KEY (drawing_id, category_code),
    FOREIGN KEY (drawing_id) REFERENCES drawings(id)
);

CREATE TABLE IF NOT EXISTS drawing_dongs (
    drawing_id INTEGER,
    dong INTEGER,
    PRIMARY KEY (drawing_id, dong),
    FOREIGN KEY (drawing_id) REFERENCES drawings(id)
);

-- 부재 법전 (영역별 독립 PK 정책 — A-3 패턴 적용)
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    territory_id INTEGER,
    region TEXT NOT NULL,               -- BSMT / DONG101_112 / DONG113_116 등 영역
    code TEXT NOT NULL,                 -- TC1, C1, RB1A 등 base 코드
    member_type TEXT,                   -- COLUMN / BEAM / WALL / SLAB
    floor_from INTEGER,
    floor_to INTEGER,
    width INTEGER,                      -- mm
    height INTEGER,                     -- mm
    thickness INTEGER,                  -- 벽체용 mm
    main_bar TEXT,                      -- "20-D25"
    hoop TEXT,                          -- "D10@150"
    source_drawing_id INTEGER,
    extracted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (territory_id) REFERENCES territories(id),
    FOREIGN KEY (source_drawing_id) REFERENCES drawings(id),
    UNIQUE(territory_id, region, code, floor_from, floor_to)
);

-- 부재 인스턴스 (도면 안 실제 위치 — 추후 확장)
CREATE TABLE IF NOT EXISTS member_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER,
    drawing_id INTEGER,
    x REAL,
    y REAL,
    z REAL,
    rotation REAL DEFAULT 0,
    FOREIGN KEY (member_id) REFERENCES members(id),
    FOREIGN KEY (drawing_id) REFERENCES drawings(id)
);

-- 패턴 라이브러리 (재활용 사전)
CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,          -- A-1, B-3 등
    category TEXT,                      -- 부재표기 / DXF구조 / 일람표형식 / 부재단위 / 트림
    title TEXT NOT NULL,
    identification TEXT,                -- 식별 조건 (자유 텍스트)
    meaning TEXT,                       -- 의미
    response TEXT,                      -- 대응 방법
    first_found_drawing TEXT,
    first_found_date TEXT,
    notes TEXT
);

-- 의구심 박제
CREATE TABLE IF NOT EXISTS doubts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,          -- 1.1, 4.1 등
    title TEXT NOT NULL,
    description TEXT,
    status TEXT,                        -- OPEN / RESOLVED / DEFERRED / ESCALATED
    resolution TEXT,
    raised_at TEXT DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);

-- BOQ 산출 결과
CREATE TABLE IF NOT EXISTS bom_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    territory_id INTEGER,
    project_label TEXT,                 -- "102동 B1F v3" 등
    concrete_volume_m3 REAL,
    formwork_area_m2 REAL,
    deduction_volume_m3 REAL,           -- 트림 공제량
    deduction_area_m2 REAL,
    total_solids INTEGER,
    method TEXT,                        -- "Boolean Fuse v3" 등
    output_path TEXT,
    computed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (territory_id) REFERENCES territories(id)
);

-- 회귀 테스트 (도면 변경 추적)
CREATE TABLE IF NOT EXISTS regressions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drawing_id_old INTEGER,
    drawing_id_new INTEGER,
    metric TEXT,                        -- "member_count" / "concrete_volume"
    value_old REAL,
    value_new REAL,
    diff REAL,
    detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (drawing_id_old) REFERENCES drawings(id),
    FOREIGN KEY (drawing_id_new) REFERENCES drawings(id)
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_drawings_territory ON drawings(territory_id);
CREATE INDEX IF NOT EXISTS idx_members_territory_region ON members(territory_id, region);
CREATE INDEX IF NOT EXISTS idx_members_code ON members(code);
CREATE INDEX IF NOT EXISTS idx_doubts_status ON doubts(status);
"""


@contextmanager
def conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA foreign_keys = ON")
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        print(f"[자산 DB] 초기화 완료: {DB_PATH}")


def ensure_territory(name, description=None, base_path=None):
    with conn() as c:
        cur = c.execute("SELECT id FROM territories WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            return row['id']
        cur = c.execute(
            "INSERT INTO territories (name, description, base_path) VALUES (?, ?, ?)",
            (name, description, base_path),
        )
        return cur.lastrowid


def insert_drawing(territory_id, filename, **kw):
    with conn() as c:
        # 기존 row 있으면 그 id 반환, 없으면 INSERT
        existing = c.execute(
            "SELECT id FROM drawings WHERE territory_id=? AND filename=? AND COALESCE(source_dir,'')=COALESCE(?,'')",
            (territory_id, filename, kw.get('source_dir')),
        ).fetchone()
        if existing:
            return existing['id']
        cur = c.execute(
            """INSERT INTO drawings
               (territory_id, filename, name, page_code, source_dir, size_bytes, file_kind, dxf_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (territory_id, filename,
             kw.get('name'), kw.get('page_code'), kw.get('source_dir'),
             kw.get('size_bytes'), kw.get('file_kind', 'DXF'), kw.get('dxf_path')),
        )
        return cur.lastrowid


def attach_categories(drawing_id, categories):
    """categories: [{'code': 'WALL_LIST', 'label': '벽체 일람표'}, ...]"""
    with conn() as c:
        for cat in categories:
            c.execute(
                "INSERT OR IGNORE INTO drawing_categories VALUES (?, ?, ?)",
                (drawing_id, cat['code'], cat.get('label')),
            )


def attach_dongs(drawing_id, dongs):
    with conn() as c:
        for d in dongs:
            c.execute("INSERT OR IGNORE INTO drawing_dongs VALUES (?, ?)", (drawing_id, d))


def insert_member(territory_id, region, code, member_type, **kw):
    with conn() as c:
        cur = c.execute(
            """INSERT OR REPLACE INTO members
               (territory_id, region, code, member_type,
                floor_from, floor_to, width, height, thickness,
                main_bar, hoop, source_drawing_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (territory_id, region, code, member_type,
             kw.get('floor_from'), kw.get('floor_to'),
             kw.get('width'), kw.get('height'), kw.get('thickness'),
             kw.get('main_bar'), kw.get('hoop'),
             kw.get('source_drawing_id')),
        )
        return cur.lastrowid


def insert_pattern(code, category, title, identification, meaning, response, **kw):
    with conn() as c:
        c.execute(
            """INSERT OR REPLACE INTO patterns
               (code, category, title, identification, meaning, response,
                first_found_drawing, first_found_date, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, category, title, identification, meaning, response,
             kw.get('first_found_drawing'), kw.get('first_found_date'), kw.get('notes')),
        )


def insert_doubt(code, title, description=None, status='OPEN', resolution=None):
    with conn() as c:
        c.execute(
            """INSERT OR REPLACE INTO doubts (code, title, description, status, resolution, resolved_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (code, title, description, status, resolution,
             datetime.now().isoformat() if status == 'RESOLVED' else None),
        )


def insert_bom(territory_id, project_label, **kw):
    with conn() as c:
        cur = c.execute(
            """INSERT INTO bom_results
               (territory_id, project_label,
                concrete_volume_m3, formwork_area_m2,
                deduction_volume_m3, deduction_area_m2,
                total_solids, method, output_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (territory_id, project_label,
             kw.get('concrete_volume_m3'), kw.get('formwork_area_m2'),
             kw.get('deduction_volume_m3'), kw.get('deduction_area_m2'),
             kw.get('total_solids'), kw.get('method'), kw.get('output_path')),
        )
        return cur.lastrowid


def query(sql, params=()):
    with conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def stats():
    with conn() as c:
        out = {}
        for table in ['territories', 'drawings', 'members', 'member_instances',
                      'patterns', 'doubts', 'bom_results']:
            out[table] = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return out


if __name__ == '__main__':
    init_db()
    print(stats())
