"""
FastAPI 엔드포인트 통합 테스트 (Phase 5)

TestClient로 실제 HTTP 요청 시뮬레이션 (서버 불필요).
"""

import pytest
import os
from fastapi.testclient import TestClient

# 테스트용 SQLite DB (임시 파일)
os.environ.setdefault("BOQ_DB_PATH", ":memory:")

from api.main import app
from api.database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """각 테스트 전 DB 초기화"""
    init_db()
    yield


# ─────────────────────────────────────
# Health Check
# ─────────────────────────────────────

class TestHealthCheck:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ─────────────────────────────────────
# POST /api/boq/calculate
# ─────────────────────────────────────

COLUMN_PAYLOAD = {
    "project_id": "TEST-001",
    "members": [
        {
            "member_id": "C1",
            "member_type": "COLUMN",
            "vertices_2d": [[-300, -300], [300, -300], [300, 300], [-300, 300]],
            "height": 3000.0,
            "z_base": 0.0,
        }
    ]
}

COLUMN_BEAM_PAYLOAD = {
    "project_id": "TEST-002",
    "members": [
        {
            "member_id": "C1",
            "member_type": "COLUMN",
            "vertices_2d": [[-300, -300], [300, -300], [300, 300], [-300, 300]],
            "height": 3000.0,
            "z_base": 0.0,
        },
        {
            "member_id": "B1",
            "member_type": "BEAM",
            "vertices_2d": [[-1000, -150], [1000, -150], [1000, 150], [-1000, 150]],
            "height": 500.0,
            "z_base": 0.0,
        }
    ]
}


class TestCalculateBOQ:
    def test_single_column_returns_200(self):
        resp = client.post("/api/boq/calculate", json=COLUMN_PAYLOAD)
        assert resp.status_code == 200

    def test_response_has_job_id(self):
        resp = client.post("/api/boq/calculate", json=COLUMN_PAYLOAD)
        data = resp.json()
        assert "job_id" in data
        assert len(data["job_id"]) == 36  # UUID

    def test_response_has_status_approved(self):
        resp = client.post("/api/boq/calculate", json=COLUMN_PAYLOAD)
        assert resp.json()["status"] == "APPROVED"

    def test_column_only_volume(self):
        """기둥 단독: 체적 1.08 m³"""
        resp = client.post("/api/boq/calculate", json=COLUMN_PAYLOAD)
        data = resp.json()
        assert abs(data["total_volume_m3"] - 1.08) < 0.001

    def test_column_beam_volume(self):
        """기둥+보: 순체적 0.63 m³"""
        resp = client.post("/api/boq/calculate", json=COLUMN_BEAM_PAYLOAD)
        data = resp.json()
        assert abs(data["total_volume_m3"] - 0.63) < 0.001

    def test_boq_items_in_response(self):
        resp = client.post("/api/boq/calculate", json=COLUMN_PAYLOAD)
        items = resp.json()["boq_items"]
        assert len(items) == 1
        assert items[0]["member_id"] == "C1"

    def test_project_id_preserved(self):
        resp = client.post("/api/boq/calculate", json=COLUMN_PAYLOAD)
        assert resp.json()["project_id"] == "TEST-001"

    def test_empty_members_returns_422(self):
        payload = {"project_id": "P1", "members": []}
        resp = client.post("/api/boq/calculate", json=payload)
        assert resp.status_code == 422

    def test_invalid_member_type_returns_422(self):
        payload = {
            "project_id": "P1",
            "members": [{
                "member_id": "X1", "member_type": "WALL",
                "vertices_2d": [[-300,-300],[300,-300],[300,300]],
                "height": 3000.0,
            }]
        }
        resp = client.post("/api/boq/calculate", json=payload)
        assert resp.status_code == 422

    def test_negative_height_returns_422(self):
        payload = {
            "project_id": "P1",
            "members": [{
                "member_id": "C1", "member_type": "COLUMN",
                "vertices_2d": [[-300,-300],[300,-300],[300,300]],
                "height": -500.0,
            }]
        }
        resp = client.post("/api/boq/calculate", json=payload)
        assert resp.status_code == 422

    def test_total_formwork_positive(self):
        resp = client.post("/api/boq/calculate", json=COLUMN_PAYLOAD)
        assert resp.json()["total_formwork_m2"] > 0


# ─────────────────────────────────────
# GET /api/boq/{job_id}
# ─────────────────────────────────────

class TestGetBOQResult:
    def test_get_existing_job(self):
        post_resp = client.post("/api/boq/calculate", json=COLUMN_PAYLOAD)
        job_id = post_resp.json()["job_id"]

        get_resp = client.get(f"/api/boq/{job_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["job_id"] == job_id

    def test_get_nonexistent_job_returns_404(self):
        resp = client.get("/api/boq/nonexistent-job-id")
        assert resp.status_code == 404

    def test_stored_job_has_correct_volume(self):
        post_resp = client.post("/api/boq/calculate", json=COLUMN_BEAM_PAYLOAD)
        job_id = post_resp.json()["job_id"]

        get_resp = client.get(f"/api/boq/{job_id}")
        assert abs(get_resp.json()["total_volume_m3"] - 0.63) < 0.001

    def test_stored_job_has_created_at(self):
        post_resp = client.post("/api/boq/calculate", json=COLUMN_PAYLOAD)
        job_id = post_resp.json()["job_id"]

        get_resp = client.get(f"/api/boq/{job_id}")
        assert "created_at" in get_resp.json()
        assert get_resp.json()["created_at"] != ""

    def test_stored_job_has_boq_items(self):
        post_resp = client.post("/api/boq/calculate", json=COLUMN_PAYLOAD)
        job_id = post_resp.json()["job_id"]

        get_resp = client.get(f"/api/boq/{job_id}")
        items = get_resp.json()["boq_items"]
        assert len(items) == 1
        assert items[0]["member_id"] == "C1"
