"""
데이터베이스 레이어 테스트 (Phase 5)
SQLite 폴백 모드로 테스트 (Turso 연결 불필요).
"""

import pytest
import os
import tempfile
from pathlib import Path

# 테스트 전 Turso 비활성화
os.environ.pop("TURSO_URL", None)

from api.models import BOQItemDTO


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """임시 SQLite DB 경로 주입"""
    import api.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db_module, "_USE_TURSO", False)
    db_module.init_db()
    return db_module


class TestSQLiteDatabase:
    def test_init_creates_table(self, tmp_db):
        """DB 초기화 후 테이블 존재"""
        import sqlite3
        with sqlite3.connect(str(tmp_db.DB_PATH)) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]
        assert "boq_jobs" in table_names

    def test_save_and_retrieve_job(self, tmp_db):
        """저장 후 조회 일치"""
        items = [
            BOQItemDTO(member_id="C1", volume_m3=1.08,
                       formwork_area_m2=7.2, formwork_deduction_m2=0.6)
        ]
        tmp_db.save_boq_job(
            job_id="JOB-001",
            project_id="PROJ-001",
            status="APPROVED",
            boq_items=items,
            total_volume_m3=1.08,
            total_formwork_m2=7.2,
        )
        result = tmp_db.get_boq_job("JOB-001")
        assert result is not None
        assert result.job_id == "JOB-001"
        assert result.project_id == "PROJ-001"
        assert result.status == "APPROVED"
        assert abs(result.total_volume_m3 - 1.08) < 1e-6

    def test_get_nonexistent_returns_none(self, tmp_db):
        result = tmp_db.get_boq_job("NONEXISTENT")
        assert result is None

    def test_boq_items_serialized_correctly(self, tmp_db):
        items = [
            BOQItemDTO(member_id="C1", volume_m3=0.63,
                       formwork_area_m2=6.6, formwork_deduction_m2=0.6,
                       gltf_url="/output/C1.gltf"),
        ]
        tmp_db.save_boq_job(
            job_id="JOB-002",
            project_id="PROJ-002",
            status="APPROVED",
            boq_items=items,
            total_volume_m3=0.63,
            total_formwork_m2=6.6,
        )
        result = tmp_db.get_boq_job("JOB-002")
        assert len(result.boq_items) == 1
        assert result.boq_items[0].member_id == "C1"
        assert result.boq_items[0].gltf_url == "/output/C1.gltf"

    def test_upsert_replaces_existing(self, tmp_db):
        """동일 job_id 재저장 시 업데이트"""
        items = [BOQItemDTO(member_id="C1", volume_m3=1.0,
                            formwork_area_m2=7.0, formwork_deduction_m2=0.5)]
        tmp_db.save_boq_job("JOB-003", "P1", "APPROVED", items, 1.0, 7.0)

        items2 = [BOQItemDTO(member_id="C1", volume_m3=0.63,
                             formwork_area_m2=6.6, formwork_deduction_m2=0.6)]
        tmp_db.save_boq_job("JOB-003", "P1", "APPROVED", items2, 0.63, 6.6)

        result = tmp_db.get_boq_job("JOB-003")
        assert abs(result.total_volume_m3 - 0.63) < 1e-6

    def test_generate_job_id_is_uuid(self, tmp_db):
        import uuid
        jid = tmp_db.generate_job_id()
        parsed = uuid.UUID(jid)
        assert str(parsed) == jid
