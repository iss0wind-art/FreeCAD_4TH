"""
Ray-Casting 은폐면 식별 엔진 테스트 (특허 제1, 2호 로직 검증)

검증 항목:
- 내적 < 0 → 은폐면(CONCRETE_JOINT)
- 내적 >= 0 → 노출면(FORMWORK)
- Water Stamp 비파괴 속성 치환
- 면적 합산 정확도
"""

import pytest
import numpy as np
from core.ray_cast import (
    Face,
    FaceMaterial,
    RayCastResult,
    is_concealed_face,
    classify_faces,
    apply_water_stamp,
    compute_formwork_area,
    compute_concealed_area,
)


# ─────────────────────────────────────
# 공통 픽스처
# ─────────────────────────────────────

@pytest.fixture
def upward_face():
    """위를 향하는 면 (법선: +Z)"""
    return Face(
        face_id="F_UP",
        center=np.array([0.0, 0.0, 1.5]),
        world_normal=np.array([0.0, 0.0, 1.0]),
        area_m2=0.36,
    )


@pytest.fixture
def downward_face():
    """아래를 향하는 면 (법선: -Z)"""
    return Face(
        face_id="F_DOWN",
        center=np.array([0.0, 0.0, 0.0]),
        world_normal=np.array([0.0, 0.0, -1.0]),
        area_m2=0.36,
    )


@pytest.fixture
def side_face_north():
    """북쪽 노출면 (법선: +Y)"""
    return Face(
        face_id="F_NORTH",
        center=np.array([0.0, 0.3, 1.5]),
        world_normal=np.array([0.0, 1.0, 0.0]),
        area_m2=1.8,
    )


@pytest.fixture
def concealed_joint_face():
    """콘크리트 조인트 은폐면 (법선이 광선과 반대)"""
    # 법선: -Y (안쪽), 광선이 +Y 방향에서 옴 → 내적 < 0
    return Face(
        face_id="F_JOINT",
        center=np.array([0.0, -0.15, 1.0]),
        world_normal=np.array([0.0, -1.0, 0.0]),
        area_m2=0.18,
    )


# ─────────────────────────────────────
# 내적 기반 은폐면 판별 테스트
# ─────────────────────────────────────

class TestIsConcealed:
    def test_opposing_vectors_is_concealed(self):
        """법선과 광선이 완전 반대 → 내적 = -1 → 은폐면"""
        normal = np.array([0.0, 1.0, 0.0])
        ray = np.array([0.0, -1.0, 0.0])
        concealed, dot = is_concealed_face(normal, ray)
        assert concealed is True
        assert abs(dot - (-1.0)) < 1e-6

    def test_same_direction_is_exposed(self):
        """법선과 광선이 같은 방향 → 내적 = 1 → 노출면"""
        normal = np.array([0.0, 0.0, 1.0])
        ray = np.array([0.0, 0.0, 1.0])
        concealed, dot = is_concealed_face(normal, ray)
        assert concealed is False
        assert abs(dot - 1.0) < 1e-6

    def test_perpendicular_is_exposed(self):
        """법선과 광선이 수직(내적 = 0) → 노출면으로 처리"""
        normal = np.array([1.0, 0.0, 0.0])
        ray = np.array([0.0, 1.0, 0.0])
        concealed, dot = is_concealed_face(normal, ray)
        assert concealed is False
        assert abs(dot) < 1e-6

    def test_oblique_concealed(self):
        """비스듬히 반대 방향 → 내적 음수 → 은폐"""
        normal = np.array([0.0, -1.0, 0.0])
        ray = np.array([0.3, 0.7, 0.5])   # Y성분 양수, 법선 -Y → 내적 음수
        concealed, dot = is_concealed_face(normal, ray)
        assert concealed is True
        assert dot < 0

    def test_zero_normal_does_not_crash(self):
        """영벡터 법선에서 충돌 없이 처리"""
        normal = np.array([0.0, 0.0, 0.0])
        ray = np.array([0.0, 0.0, 1.0])
        concealed, dot = is_concealed_face(normal, ray)
        assert isinstance(concealed, bool)


# ─────────────────────────────────────
# 면 일괄 분류 테스트
# ─────────────────────────────────────

class TestClassifyFaces:
    def test_classify_upward_face_is_formwork(self, upward_face):
        """위를 향하는 면: light_source가 위에서 오면 노출면"""
        light = np.array([0.0, 0.0, 10.0])
        results = classify_faces([upward_face], light_source=light)
        assert len(results) == 1
        assert results[0].is_concealed is False
        assert results[0].material == FaceMaterial.FORMWORK

    def test_classify_joint_face_is_concrete_joint(self, concealed_joint_face):
        """콘크리트 조인트 면: 은폐면으로 분류"""
        light = np.array([0.0, 10.0, 5.0])
        results = classify_faces([concealed_joint_face], light_source=light)
        assert results[0].is_concealed is True
        assert results[0].material == FaceMaterial.CONCRETE_JOINT

    def test_classify_mixed_faces(self, upward_face, concealed_joint_face, side_face_north):
        """혼합 면 목록 분류 → 각자 올바른 재질 부여"""
        light = np.array([0.0, 5.0, 10.0])
        faces = [upward_face, concealed_joint_face, side_face_north]
        results = classify_faces(faces, light_source=light)
        assert len(results) == 3
        materials = {r.face_id: r.material for r in results}
        # 위쪽 면 → FORMWORK
        assert materials["F_UP"] == FaceMaterial.FORMWORK
        # 조인트 면 → CONCRETE_JOINT
        assert materials["F_JOINT"] == FaceMaterial.CONCRETE_JOINT

    def test_empty_faces_returns_empty(self):
        """빈 목록 → 빈 결과"""
        results = classify_faces([])
        assert results == []


# ─────────────────────────────────────
# Water Stamp 비파괴 속성 치환 테스트
# ─────────────────────────────────────

class TestWaterStamp:
    def test_stamp_applies_material(self, upward_face):
        """Water Stamp → 올바른 재질이 면에 적용됨"""
        results = [RayCastResult(
            face_id="F_UP",
            is_concealed=False,
            dot_product=0.9,
            material=FaceMaterial.FORMWORK,
        )]
        stamped = apply_water_stamp([upward_face], results)
        assert stamped[0].material == FaceMaterial.FORMWORK

    def test_original_face_not_mutated(self, upward_face):
        """비파괴: 원본 Face 객체는 수정되지 않음"""
        original_material = upward_face.material
        results = [RayCastResult(
            face_id="F_UP",
            is_concealed=True,
            dot_product=-0.5,
            material=FaceMaterial.CONCRETE_JOINT,
        )]
        stamped = apply_water_stamp([upward_face], results)
        # 원본 불변
        assert upward_face.material == original_material
        # 새 객체에만 적용
        assert stamped[0].material == FaceMaterial.CONCRETE_JOINT

    def test_unmatched_face_kept_as_is(self, upward_face):
        """매칭되는 결과 없는 면 → UNCLASSIFIED 유지"""
        stamped = apply_water_stamp([upward_face], [])
        assert stamped[0].material == FaceMaterial.UNCLASSIFIED


# ─────────────────────────────────────
# 면적 합산 테스트
# ─────────────────────────────────────

class TestAreaSummation:
    def test_formwork_area_sum(self):
        """FORMWORK 면적만 합산"""
        faces = [
            Face("F1", np.zeros(3), np.array([0,0,1.0]), area_m2=1.0, material=FaceMaterial.FORMWORK),
            Face("F2", np.zeros(3), np.array([0,0,1.0]), area_m2=2.0, material=FaceMaterial.FORMWORK),
            Face("F3", np.zeros(3), np.array([0,0,1.0]), area_m2=0.5, material=FaceMaterial.CONCRETE_JOINT),
        ]
        assert abs(compute_formwork_area(faces) - 3.0) < 1e-6

    def test_concealed_area_sum(self):
        """CONCRETE_JOINT 면적만 합산"""
        faces = [
            Face("F1", np.zeros(3), np.array([0,0,1.0]), area_m2=1.0, material=FaceMaterial.FORMWORK),
            Face("F2", np.zeros(3), np.array([0,0,1.0]), area_m2=0.3, material=FaceMaterial.CONCRETE_JOINT),
            Face("F3", np.zeros(3), np.array([0,0,1.0]), area_m2=0.2, material=FaceMaterial.CONCRETE_JOINT),
        ]
        assert abs(compute_concealed_area(faces) - 0.5) < 1e-6

    def test_no_formwork_faces_returns_zero(self):
        """FORMWORK 없으면 0"""
        faces = [
            Face("F1", np.zeros(3), np.array([0,0,1.0]), area_m2=1.0, material=FaceMaterial.CONCRETE_JOINT),
        ]
        assert compute_formwork_area(faces) == 0.0

    def test_total_area_equals_formwork_plus_concealed(self):
        """전체 면적 = FORMWORK + CONCRETE_JOINT"""
        faces = [
            Face("F1", np.zeros(3), np.array([0,0,1.0]), area_m2=2.0, material=FaceMaterial.FORMWORK),
            Face("F2", np.zeros(3), np.array([0,0,1.0]), area_m2=0.5, material=FaceMaterial.CONCRETE_JOINT),
        ]
        total = sum(f.area_m2 for f in faces)
        assert abs(compute_formwork_area(faces) + compute_concealed_area(faces) - total) < 1e-6
