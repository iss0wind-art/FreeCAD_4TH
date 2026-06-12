"""
Ray-Casting 차폐 판정 테스트 (1지국 특허 v11.4 Inverse Single-Ray 의미 복원)

기존 classify_faces(내적 부호만)는 차폐(은폐) 검사가 아니다.
특허 원의: 면 바깥 0.1mm 허공의 점이 *다른 부재 몸속*에 있으면 은폐면.
→ point_in_mesh (Möller-Trumbore + 6방향 과반수 투표) 기반 판정.

시나리오: 두 개의 1m 정육면체가 X방향으로 맞닿음 (A: 0~1000, B: 1000~2000).
A의 +X면(접촉면)은 은폐, A의 -X면(노출)은 거푸집.
"""

import numpy as np
import pytest

from core.ray_cast import (
    Face,
    FaceMaterial,
    TriangleMesh,
    point_in_mesh,
    classify_faces_occlusion,
)


def make_box_mesh(member_id: str, x0, y0, z0, x1, y1, z1) -> TriangleMesh:
    """AABB 박스를 12개 삼각형 메쉬로 생성"""
    v = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),  # 바닥 0-3
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),  # 천장 4-7
    ]
    quads = [
        (0, 3, 2, 1),  # 바닥 (법선 -Z)
        (4, 5, 6, 7),  # 천장 (+Z)
        (0, 1, 5, 4),  # 앞 (-Y)
        (2, 3, 7, 6),  # 뒤 (+Y)
        (0, 4, 7, 3),  # 좌 (-X)
        (1, 2, 6, 5),  # 우 (+X)
    ]
    tris = []
    for a, b, c, d in quads:
        tris.append((np.array(v[a], float), np.array(v[b], float), np.array(v[c], float)))
        tris.append((np.array(v[a], float), np.array(v[c], float), np.array(v[d], float)))
    return TriangleMesh(member_id=member_id, triangles=tris)


@pytest.fixture
def box_a():
    return make_box_mesh("A", 0, 0, 0, 1000, 1000, 1000)


@pytest.fixture
def box_b():
    """box_a의 +X면에 맞닿은 박스"""
    return make_box_mesh("B", 1000, 0, 0, 2000, 1000, 1000)


class TestPointInMesh:
    def test_center_is_inside(self, box_a):
        assert point_in_mesh(np.array([500.0, 500.0, 500.0]), box_a) is True

    def test_outside_is_outside(self, box_a):
        assert point_in_mesh(np.array([1500.0, 500.0, 500.0]), box_a) is False

    def test_far_outside(self, box_a):
        assert point_in_mesh(np.array([-9999.0, -9999.0, -9999.0]), box_a) is False


class TestOcclusionClassify:
    def test_contact_face_is_concealed(self, box_a, box_b):
        """A의 +X면(접촉면): 바깥 0.1mm 프로브가 B 몸속 → 은폐(조인트)"""
        contact = Face(
            face_id="A_+X",
            center=np.array([1000.0, 500.0, 500.0]),
            world_normal=np.array([1.0, 0.0, 0.0]),
            area_m2=1.0,
        )
        results = classify_faces_occlusion([contact], [box_b])
        assert results[0].is_concealed is True
        assert results[0].material == FaceMaterial.CONCRETE_JOINT

    def test_free_face_is_exposed(self, box_a, box_b):
        """A의 -X면(노출면): 프로브가 허공 → 거푸집"""
        free = Face(
            face_id="A_-X",
            center=np.array([0.0, 500.0, 500.0]),
            world_normal=np.array([-1.0, 0.0, 0.0]),
            area_m2=1.0,
        )
        results = classify_faces_occlusion([free], [box_b])
        assert results[0].is_concealed is False
        assert results[0].material == FaceMaterial.FORMWORK

    def test_no_other_meshes_all_exposed(self, box_a):
        """다른 부재가 없으면 모든 면 노출"""
        face = Face(
            face_id="A_top",
            center=np.array([500.0, 500.0, 1000.0]),
            world_normal=np.array([0.0, 0.0, 1.0]),
            area_m2=1.0,
        )
        results = classify_faces_occlusion([face], [])
        assert results[0].is_concealed is False
