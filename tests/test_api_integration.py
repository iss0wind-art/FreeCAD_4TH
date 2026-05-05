"""
Phase 2 E2E 통합 테스트

시나리오:
1. DB init 검증 — member_specs / projects / member_instances 테이블 존재 확인
2. spec CRUD — upsert_member_spec → get_member_spec → list_member_specs 왕복 검증
3. project CRUD — create_project → get_project 왕복 검증
4. manifest 파싱 → DB 저장 — sample_project.boq.yaml 파싱 후 DB 저장
5. FastAPI TestClient GET /api/specs — upsert 후 목록 조회 응답 확인
6. FastAPI TestClient GET /api/specs/{symbol} — 존재/미존재 404 확인
7. FastAPI TestClient POST /api/projects — sample yaml 업로드 → 201 응답 + project_id 반환 확인
8. GET /api/specs?member_type=BEAM 필터 동작 확인

테스트용 DB: tmp_path monkeypatch — 기존 output/boq.db 오염 없음.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

# Turso 비활성화 (SQLite 폴백 강제)
os.environ.pop("TURSO_URL", None)

# ─────────────────────────────────────────────────────────────
# 공용 픽스처
# ─────────────────────────────────────────────────────────────
SAMPLE_YAML_PATH = Path(__file__).resolve().parent.parent / "spec" / "sample_project.boq.yaml"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """각 테스트마다 격리된 임시 SQLite DB를 주입한다."""
    import api.database as db_module

    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test_integration.db")
    monkeypatch.setattr(db_module, "_USE_TURSO", False)
    db_module.init_db()
    return db_module


@pytest.fixture()
def test_client(tmp_path, monkeypatch):
    """TestClient + 격리된 DB를 함께 반환한다."""
    import api.database as db_module

    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test_client.db")
    monkeypatch.setattr(db_module, "_USE_TURSO", False)
    db_module.init_db()

    from fastapi.testclient import TestClient
    from api.main import app

    return TestClient(app), db_module


# ─────────────────────────────────────────────────────────────
# 시나리오 1: DB init 검증
# ─────────────────────────────────────────────────────────────
class TestDBInit:
    def test_member_specs_table_exists(self, tmp_db):
        """init_db() 후 member_specs 테이블이 생성돼야 한다."""
        with sqlite3.connect(str(tmp_db.DB_PATH)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "member_specs" in tables

    def test_projects_table_exists(self, tmp_db):
        """init_db() 후 projects 테이블이 생성돼야 한다."""
        with sqlite3.connect(str(tmp_db.DB_PATH)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "projects" in tables

    def test_member_instances_table_exists(self, tmp_db):
        """init_db() 후 member_instances 테이블이 생성돼야 한다."""
        with sqlite3.connect(str(tmp_db.DB_PATH)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "member_instances" in tables

    def test_all_three_new_tables_exist(self, tmp_db):
        """Phase 1 신규 3개 테이블이 모두 생성돼야 한다."""
        with sqlite3.connect(str(tmp_db.DB_PATH)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert {"member_specs", "projects", "member_instances"}.issubset(tables)


# ─────────────────────────────────────────────────────────────
# 시나리오 2: spec CRUD
# ─────────────────────────────────────────────────────────────
_COLUMN_SPEC = {
    "symbol": "TC1",
    "project_scope": "global",
    "member_type": "COLUMN",
    "width": 500.0,
    "height": 500.0,
    "depth": 4000.0,
    "source": "TEST",
}

_BEAM_SPEC = {
    "symbol": "RG1",
    "project_scope": "global",
    "member_type": "BEAM",
    "width": 300.0,
    "height": 600.0,
    "source": "TEST",
}


class TestSpecCRUD:
    def test_upsert_then_get_returns_spec(self, tmp_db):
        """upsert → get 왕복: 저장한 스펙이 조회돼야 한다."""
        tmp_db.upsert_member_spec(_COLUMN_SPEC)
        result = tmp_db.get_member_spec("TC1", "global")
        assert result is not None
        assert result["symbol"] == "TC1"
        assert result["member_type"] == "COLUMN"

    def test_upsert_then_get_numeric_fields(self, tmp_db):
        """upsert → get: width/height/depth 수치 필드 정확성."""
        tmp_db.upsert_member_spec(_COLUMN_SPEC)
        result = tmp_db.get_member_spec("TC1", "global")
        assert result is not None
        assert abs(result["width"] - 500.0) < 1e-6
        assert abs(result["height"] - 500.0) < 1e-6
        assert abs(result["depth"] - 4000.0) < 1e-6

    def test_list_member_specs_returns_all(self, tmp_db):
        """upsert 2건 → list 조회: 2건 반환."""
        tmp_db.upsert_member_spec(_COLUMN_SPEC)
        tmp_db.upsert_member_spec(_BEAM_SPEC)
        specs = tmp_db.list_member_specs()
        assert len(specs) == 2

    def test_list_member_specs_filter_by_type(self, tmp_db):
        """member_type 필터: BEAM 만 반환."""
        tmp_db.upsert_member_spec(_COLUMN_SPEC)
        tmp_db.upsert_member_spec(_BEAM_SPEC)
        beams = tmp_db.list_member_specs(member_type="BEAM")
        assert len(beams) == 1
        assert beams[0]["symbol"] == "RG1"

    def test_get_nonexistent_spec_returns_none(self, tmp_db):
        """존재하지 않는 symbol 조회 시 None 반환."""
        result = tmp_db.get_member_spec("NONEXISTENT", "global")
        assert result is None

    def test_upsert_updates_existing(self, tmp_db):
        """동일 PK 재 upsert 시 필드가 갱신돼야 한다."""
        tmp_db.upsert_member_spec(_COLUMN_SPEC)
        updated = {**_COLUMN_SPEC, "width": 600.0}
        tmp_db.upsert_member_spec(updated)
        result = tmp_db.get_member_spec("TC1", "global")
        assert result is not None
        assert abs(result["width"] - 600.0) < 1e-6

    def test_upsert_preserves_source_field(self, tmp_db):
        """source 필드가 저장돼야 한다."""
        tmp_db.upsert_member_spec(_COLUMN_SPEC)
        result = tmp_db.get_member_spec("TC1", "global")
        assert result is not None
        assert result["source"] == "TEST"


# ─────────────────────────────────────────────────────────────
# 시나리오 3: project CRUD
# ─────────────────────────────────────────────────────────────
_PROJECT_RECORD = {
    "project_id": "INTEG-001",
    "name": "통합테스트 프로젝트",
    "units": "mm",
    "manifest_yaml": "# test yaml",
    "manifest_hash": "abc123",
}


class TestProjectCRUD:
    def test_create_then_get_returns_project(self, tmp_db):
        """create_project → get_project 왕복: 저장된 프로젝트가 조회돼야 한다."""
        tmp_db.create_project(_PROJECT_RECORD)
        result = tmp_db.get_project("INTEG-001")
        assert result is not None
        assert result["project_id"] == "INTEG-001"

    def test_create_then_get_name_field(self, tmp_db):
        """name 필드가 일치해야 한다."""
        tmp_db.create_project(_PROJECT_RECORD)
        result = tmp_db.get_project("INTEG-001")
        assert result is not None
        assert result["name"] == "통합테스트 프로젝트"

    def test_create_then_get_units_field(self, tmp_db):
        """units 필드가 일치해야 한다."""
        tmp_db.create_project(_PROJECT_RECORD)
        result = tmp_db.get_project("INTEG-001")
        assert result is not None
        assert result["units"] == "mm"

    def test_get_nonexistent_project_returns_none(self, tmp_db):
        """존재하지 않는 project_id 조회 시 None 반환."""
        result = tmp_db.get_project("NONEXISTENT-9999")
        assert result is None

    def test_create_preserves_manifest_yaml(self, tmp_db):
        """manifest_yaml 필드가 보존돼야 한다."""
        tmp_db.create_project(_PROJECT_RECORD)
        result = tmp_db.get_project("INTEG-001")
        assert result is not None
        assert result["manifest_yaml"] == "# test yaml"


# ─────────────────────────────────────────────────────────────
# 시나리오 4: manifest 파싱 → DB 저장
# ─────────────────────────────────────────────────────────────
class TestManifestParseAndStore:
    def test_sample_yaml_file_exists(self):
        """샘플 YAML 파일이 존재해야 한다."""
        assert SAMPLE_YAML_PATH.exists(), f"샘플 파일 없음: {SAMPLE_YAML_PATH}"

    def test_parse_manifest_returns_model(self):
        """parse_manifest()가 ManifestModel을 반환해야 한다."""
        from core.manifest_parser import parse_manifest

        yaml_text = SAMPLE_YAML_PATH.read_text(encoding="utf-8")
        manifest = parse_manifest(yaml_text)
        assert manifest.project.id == "SAMPLE-001"

    def test_parse_manifest_member_count(self):
        """샘플 YAML: 부재 8개 (기둥 4 + 보 4)."""
        from core.manifest_parser import parse_manifest

        yaml_text = SAMPLE_YAML_PATH.read_text(encoding="utf-8")
        manifest = parse_manifest(yaml_text)
        assert len(manifest.members) == 8

    def test_parse_manifest_and_store_project(self, tmp_db):
        """parse_manifest → create_project → get_project 전체 흐름."""
        import hashlib
        import json
        from core.manifest_parser import parse_manifest

        yaml_text = SAMPLE_YAML_PATH.read_text(encoding="utf-8")
        manifest = parse_manifest(yaml_text)

        tmp_db.create_project({
            "project_id": manifest.project.id,
            "name": manifest.project.name,
            "units": manifest.project.units,
            "manifest_yaml": yaml_text,
            "manifest_hash": hashlib.sha256(yaml_text.encode()).hexdigest(),
            "floors_json": json.dumps([f.model_dump() for f in manifest.floors]),
        })

        stored = tmp_db.get_project(manifest.project.id)
        assert stored is not None
        assert stored["project_id"] == "SAMPLE-001"
        assert stored["name"] == "Phase 1 검증 샘플"

    def test_parse_manifest_grid_keys(self):
        """그리드 x_lines/y_lines 키가 올바르게 파싱돼야 한다."""
        from core.manifest_parser import parse_manifest

        yaml_text = SAMPLE_YAML_PATH.read_text(encoding="utf-8")
        manifest = parse_manifest(yaml_text)
        assert manifest.grid is not None
        assert "A" in manifest.grid.x_lines
        assert "B" in manifest.grid.x_lines


# ─────────────────────────────────────────────────────────────
# 시나리오 5 & 8: FastAPI TestClient GET /api/specs (+ 필터)
# ─────────────────────────────────────────────────────────────
class TestGetSpecsEndpoint:
    def test_empty_specs_returns_empty_list(self, test_client):
        """DB가 비어 있으면 빈 리스트를 반환해야 한다."""
        client, _ = test_client
        resp = client.get("/api/specs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_upsert_then_list_returns_one(self, test_client):
        """upsert 1건 후 GET /api/specs → 1건 반환."""
        client, db = test_client
        db.upsert_member_spec(_COLUMN_SPEC)
        resp = client.get("/api/specs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "TC1"

    def test_list_specs_has_required_fields(self, test_client):
        """응답 항목에 필수 필드가 모두 포함돼야 한다."""
        client, db = test_client
        db.upsert_member_spec(_COLUMN_SPEC)
        resp = client.get("/api/specs")
        item = resp.json()[0]
        for field in ("symbol", "member_type", "width", "height", "created_at"):
            assert field in item, f"필드 누락: {field}"

    def test_filter_by_beam_returns_only_beams(self, test_client):
        """?member_type=BEAM 필터: BEAM 만 반환."""
        client, db = test_client
        db.upsert_member_spec(_COLUMN_SPEC)
        db.upsert_member_spec(_BEAM_SPEC)
        resp = client.get("/api/specs?member_type=BEAM")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "RG1"
        assert data[0]["member_type"] == "BEAM"

    def test_filter_by_column_returns_only_columns(self, test_client):
        """?member_type=COLUMN 필터: COLUMN 만 반환."""
        client, db = test_client
        db.upsert_member_spec(_COLUMN_SPEC)
        db.upsert_member_spec(_BEAM_SPEC)
        resp = client.get("/api/specs?member_type=COLUMN")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "TC1"

    def test_invalid_member_type_returns_422(self, test_client):
        """허용되지 않은 member_type 필터 → 422."""
        client, _ = test_client
        resp = client.get("/api/specs?member_type=INVALID")
        assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────
# 시나리오 6: FastAPI TestClient GET /api/specs/{symbol}
# ─────────────────────────────────────────────────────────────
class TestGetSpecBySymbolEndpoint:
    def test_existing_symbol_returns_200(self, test_client):
        """존재하는 symbol 조회 → 200."""
        client, db = test_client
        db.upsert_member_spec(_COLUMN_SPEC)
        resp = client.get("/api/specs/TC1")
        assert resp.status_code == 200

    def test_existing_symbol_returns_correct_data(self, test_client):
        """존재하는 symbol 조회 → 정확한 데이터 반환."""
        client, db = test_client
        db.upsert_member_spec(_COLUMN_SPEC)
        resp = client.get("/api/specs/TC1")
        data = resp.json()
        assert data["symbol"] == "TC1"
        assert data["member_type"] == "COLUMN"

    def test_nonexistent_symbol_returns_404(self, test_client):
        """존재하지 않는 symbol 조회 → 404."""
        client, _ = test_client
        resp = client.get("/api/specs/NONEXISTENT")
        assert resp.status_code == 404

    def test_404_response_has_detail(self, test_client):
        """404 응답에 detail 필드가 있어야 한다."""
        client, _ = test_client
        resp = client.get("/api/specs/MISSING_SYMBOL")
        assert "detail" in resp.json()

    def test_symbol_with_project_scope_query(self, test_client):
        """project_scope 쿼리 파라미터로 조회 가능해야 한다."""
        client, db = test_client
        db.upsert_member_spec(_COLUMN_SPEC)
        resp = client.get("/api/specs/TC1?project_scope=global")
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────
# 시나리오 7: FastAPI TestClient POST /api/projects
# ─────────────────────────────────────────────────────────────
class TestPostProjectsEndpoint:
    def test_upload_sample_yaml_returns_201(self, test_client):
        """샘플 YAML 업로드 → 201 Created."""
        client, _ = test_client
        yaml_bytes = SAMPLE_YAML_PATH.read_bytes()
        resp = client.post(
            "/api/projects",
            files={"file": ("sample_project.boq.yaml", yaml_bytes, "text/yaml")},
        )
        assert resp.status_code == 201

    def test_upload_sample_yaml_returns_project_id(self, test_client):
        """응답에 project_id가 포함돼야 한다."""
        client, _ = test_client
        yaml_bytes = SAMPLE_YAML_PATH.read_bytes()
        resp = client.post(
            "/api/projects",
            files={"file": ("sample_project.boq.yaml", yaml_bytes, "text/yaml")},
        )
        data = resp.json()
        assert "project_id" in data
        assert data["project_id"] == "SAMPLE-001"

    def test_upload_sample_yaml_returns_name(self, test_client):
        """응답에 name 이 포함돼야 한다."""
        client, _ = test_client
        yaml_bytes = SAMPLE_YAML_PATH.read_bytes()
        resp = client.post(
            "/api/projects",
            files={"file": ("sample_project.boq.yaml", yaml_bytes, "text/yaml")},
        )
        data = resp.json()
        assert data["name"] == "Phase 1 검증 샘플"

    def test_upload_sample_yaml_returns_member_count(self, test_client):
        """member_count 가 8 (기둥 4 + 보 4)이어야 한다."""
        client, _ = test_client
        yaml_bytes = SAMPLE_YAML_PATH.read_bytes()
        resp = client.post(
            "/api/projects",
            files={"file": ("sample_project.boq.yaml", yaml_bytes, "text/yaml")},
        )
        data = resp.json()
        assert data["member_count"] == 8

    def test_upload_same_yaml_twice_returns_409(self, test_client):
        """동일 project_id 재업로드 → 409 Conflict."""
        client, _ = test_client
        yaml_bytes = SAMPLE_YAML_PATH.read_bytes()
        client.post(
            "/api/projects",
            files={"file": ("sample_project.boq.yaml", yaml_bytes, "text/yaml")},
        )
        resp2 = client.post(
            "/api/projects",
            files={"file": ("sample_project.boq.yaml", yaml_bytes, "text/yaml")},
        )
        assert resp2.status_code == 409

    def test_upload_invalid_yaml_returns_422(self, test_client):
        """손상된 YAML 업로드 → 422."""
        client, _ = test_client
        bad_yaml = b"this is: not: valid: yaml: {{ broken"
        resp = client.post(
            "/api/projects",
            files={"file": ("bad.boq.yaml", bad_yaml, "text/yaml")},
        )
        assert resp.status_code == 422

    def test_upload_stores_project_in_db(self, test_client):
        """업로드 후 DB에 프로젝트가 저장돼야 한다."""
        client, db = test_client
        yaml_bytes = SAMPLE_YAML_PATH.read_bytes()
        client.post(
            "/api/projects",
            files={"file": ("sample_project.boq.yaml", yaml_bytes, "text/yaml")},
        )
        stored = db.get_project("SAMPLE-001")
        assert stored is not None
        assert stored["project_id"] == "SAMPLE-001"

    def test_upload_stores_member_instances_in_db(self, test_client):
        """업로드 후 member_instances 에 부재가 저장돼야 한다."""
        client, db = test_client
        yaml_bytes = SAMPLE_YAML_PATH.read_bytes()
        client.post(
            "/api/projects",
            files={"file": ("sample_project.boq.yaml", yaml_bytes, "text/yaml")},
        )
        with sqlite3.connect(str(db.DB_PATH)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM member_instances WHERE project_id = ?",
                ("SAMPLE-001",),
            ).fetchone()[0]
        assert count == 8
