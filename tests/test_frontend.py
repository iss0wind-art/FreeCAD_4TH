"""
프론트엔드 파일 구조 + FastAPI 정적 서빙 테스트 (Phase 6)
"""

import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient

from api.main import app
from api.database import init_db

client = TestClient(app)
FRONTEND = Path("frontend")


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


# ─────────────────────────────────────
# 파일 구조 검증
# ─────────────────────────────────────

class TestFrontendFiles:
    def test_index_html_exists(self):
        assert (FRONTEND / "index.html").exists()

    def test_viewer_js_exists(self):
        assert (FRONTEND / "viewer.js").exists()

    def test_api_js_exists(self):
        assert (FRONTEND / "api.js").exists()

    def test_index_html_has_canvas(self):
        content = (FRONTEND / "index.html").read_text(encoding="utf-8")
        assert 'id="boq-canvas"' in content

    def test_index_html_has_calculate_button(self):
        content = (FRONTEND / "index.html").read_text(encoding="utf-8")
        assert 'id="btn-calculate"' in content

    def test_index_html_has_result_card(self):
        content = (FRONTEND / "index.html").read_text(encoding="utf-8")
        assert 'id="result-card"' in content

    def test_index_html_has_legend(self):
        """재질 범례 3종 포함"""
        content = (FRONTEND / "index.html").read_text(encoding="utf-8")
        assert "CONCRETE" in content
        assert "FORMWORK" in content
        assert "CONCRETE_JOINT" in content

    def test_index_html_imports_viewer(self):
        """viewer.js import 확인"""
        content = (FRONTEND / "index.html").read_text(encoding="utf-8")
        assert 'viewer.js' in content

    def test_index_html_imports_api(self):
        """api.js import 확인"""
        content = (FRONTEND / "index.html").read_text(encoding="utf-8")
        assert 'api.js' in content

    def test_viewer_js_has_init_viewer(self):
        content = (FRONTEND / "viewer.js").read_text(encoding="utf-8")
        assert "initViewer" in content

    def test_viewer_js_has_material_colors(self):
        content = (FRONTEND / "viewer.js").read_text(encoding="utf-8")
        assert "MATERIAL_COLORS" in content
        assert "CONCRETE_JOINT" in content

    def test_viewer_js_no_boolean_operations(self):
        """3D Boolean 연산 금지 — CSG/Boolean 키워드 없음"""
        content = (FRONTEND / "viewer.js").read_text(encoding="utf-8")
        assert "CSGMesh" not in content
        assert "ThreeBSP" not in content
        assert "Part.cut" not in content

    def test_viewer_js_uses_gltf_loader(self):
        content = (FRONTEND / "viewer.js").read_text(encoding="utf-8")
        assert "GLTFLoader" in content

    def test_viewer_js_exports_init_viewer(self):
        content = (FRONTEND / "viewer.js").read_text(encoding="utf-8")
        assert "export" in content
        assert "initViewer" in content

    def test_api_js_has_calculate_boq(self):
        content = (FRONTEND / "api.js").read_text(encoding="utf-8")
        assert "calculateBOQ" in content

    def test_api_js_has_get_boq_job(self):
        content = (FRONTEND / "api.js").read_text(encoding="utf-8")
        assert "getBOQJob" in content

    def test_api_js_uses_fetch(self):
        content = (FRONTEND / "api.js").read_text(encoding="utf-8")
        assert "fetch(" in content

    def test_api_js_uses_correct_endpoints(self):
        content = (FRONTEND / "api.js").read_text(encoding="utf-8")
        assert "/api/boq/calculate" in content
        assert "/api/boq/" in content


# ─────────────────────────────────────
# FastAPI 정적 서빙 테스트
# ─────────────────────────────────────

class TestStaticServing:
    def test_root_returns_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_root_contains_boq_canvas(self):
        resp = client.get("/")
        assert b"boq-canvas" in resp.content

    def test_static_viewer_js(self):
        resp = client.get("/static/viewer.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]

    def test_static_api_js(self):
        resp = client.get("/static/api.js")
        assert resp.status_code == 200

    def test_health_still_works(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_boq_api_still_works_with_viewer(self):
        """뷰어 추가 후 BOQ API 정상 동작"""
        payload = {
            "project_id": "VIEWER-TEST",
            "members": [{
                "member_id": "C1",
                "member_type": "COLUMN",
                "vertices_2d": [[-300,-300],[300,-300],[300,300],[-300,300]],
                "height": 3000.0,
            }]
        }
        resp = client.post("/api/boq/calculate", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"
