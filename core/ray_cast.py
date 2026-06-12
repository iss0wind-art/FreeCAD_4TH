"""
Ray-Casting 은폐면 식별 엔진 (특허 제1, 2호 핵심 로직)

비파괴 메쉬 제어 방식:
1. 선 투영(Outline Projection): 투영 행렬로 가상 면 분할
2. 은폐면 식별: 내적(Dot Product) < 0 이면 콘크리트 조인트(은폐면)
3. Water Stamp: 은폐면→공제, 노출면→거푸집+UV 재질 매핑
"""

from dataclasses import dataclass
from enum import Enum
import numpy as np


class FaceMaterial(Enum):
    CONCRETE_JOINT = "CONCRETE_JOINT"   # 은폐면 → 공제
    FORMWORK = "FORMWORK"               # 노출면 → 거푸집 산출
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass
class Face:
    """3D 메쉬 면 (비파괴 속성 제어)"""
    face_id: str
    center: np.ndarray          # 면 중심점 (3D 월드 좌표)
    world_normal: np.ndarray    # 월드 법선 벡터 (단위 벡터)
    area_m2: float
    material: FaceMaterial = FaceMaterial.UNCLASSIFIED


@dataclass
class RayCastResult:
    """Ray-Casting 분류 결과"""
    face_id: str
    is_concealed: bool
    dot_product: float
    material: FaceMaterial


def is_concealed_face(
    face_normal: np.ndarray,
    probe_ray_direction: np.ndarray,
) -> tuple[bool, float]:
    """
    내적(Dot Product) < 0 이면 은폐면(콘크리트 조인트)으로 확정.

    원리:
    - 내적 < 0: 법선과 광선이 반대 방향 → 면이 광선 쪽을 향하지 않음 → 은폐
    - 내적 >= 0: 법선과 광선이 같은 방향 → 노출면 → 거푸집 산출
    """
    # 단위 벡터 정규화
    n = face_normal / (np.linalg.norm(face_normal) + 1e-10)
    r = probe_ray_direction / (np.linalg.norm(probe_ray_direction) + 1e-10)

    dot = float(np.dot(n, r))
    return dot < 0, dot


def classify_faces(
    faces: list[Face],
    light_source: np.ndarray = np.array([0.0, 0.0, 1.0]),
) -> list[RayCastResult]:
    """
    메쉬 면 목록을 일괄 분류.
    각 면 중심에서 light_source 방향으로 프로브 Ray를 쏨.
    """
    results = []
    for face in faces:
        probe_ray = light_source - face.center
        concealed, dot = is_concealed_face(face.world_normal, probe_ray)
        material = FaceMaterial.CONCRETE_JOINT if concealed else FaceMaterial.FORMWORK
        results.append(RayCastResult(
            face_id=face.face_id,
            is_concealed=concealed,
            dot_product=round(dot, 6),
            material=material,
        ))
    return results


def apply_water_stamp(faces: list[Face], results: list[RayCastResult]) -> list[Face]:
    """
    Water Stamp: 분류 결과를 메쉬 면에 비파괴적으로 속성 치환.
    원본 면을 수정하지 않고 새 객체로 반환 (불변성 원칙).
    """
    result_map = {r.face_id: r for r in results}
    stamped = []
    for face in faces:
        rc = result_map.get(face.face_id)
        if rc is None:
            stamped.append(face)
            continue
        stamped.append(Face(
            face_id=face.face_id,
            center=face.center,
            world_normal=face.world_normal,
            area_m2=face.area_m2,
            material=rc.material,
        ))
    return stamped


def compute_formwork_area(faces: list[Face]) -> float:
    """노출면(FORMWORK) 면적 합산 (m²)"""
    return sum(f.area_m2 for f in faces if f.material == FaceMaterial.FORMWORK)


def compute_concealed_area(faces: list[Face]) -> float:
    """은폐면(CONCRETE_JOINT) 면적 합산 (m²) - 공제량"""
    return sum(f.area_m2 for f in faces if f.material == FaceMaterial.CONCRETE_JOINT)


# ════════════════════════════════════════════════════════════════════
# 차폐 기반 은폐면 판정 — 1지국 특허 v11.4 Inverse Single-Ray 의미 복원
# (2026-06-12 전수조사 처방)
#
# 기존 classify_faces는 고정 광원과의 내적 부호만 보므로 차폐 검사가 아니다.
# 특허 원의: "면 바깥 0.1mm 허공의 점이 다른 부재 몸속에 있으면 그 면은
# 접촉 조인트(은폐면)" — 1지국 MathHelper.point_in_mesh
# (Möller-Trumbore 레이-삼각형 + Jordan Curve 6방향 과반수 투표)와 동일 사상.
# ════════════════════════════════════════════════════════════════════

from dataclasses import field


@dataclass
class TriangleMesh:
    """부재 1개의 삼각형 메쉬 (차폐 판정용)"""
    member_id: str
    triangles: list = field(default_factory=list)  # [(v0, v1, v2) np.ndarray 3개씩]


def _ray_triangle_t(origin: np.ndarray, direction: np.ndarray,
                    v0: np.ndarray, v1: np.ndarray, v2: np.ndarray,
                    eps: float = 1e-9):
    """Möller-Trumbore: 반직선-삼각형 교차 거리 t 반환 (미교차 시 None)"""
    edge1 = v1 - v0
    edge2 = v2 - v0
    h = np.cross(direction, edge2)
    a = np.dot(edge1, h)
    if abs(a) < eps:
        return None  # 평행
    f = 1.0 / a
    s = origin - v0
    u = f * np.dot(s, h)
    if u < -eps or u > 1.0 + eps:
        return None
    q = np.cross(s, edge1)
    v = f * np.dot(direction, q)
    if v < -eps or u + v > 1.0 + eps:
        return None
    t = f * np.dot(edge2, q)
    return t if t > eps else None  # 반직선 전방 교차만


_SIX_DIRECTIONS = (
    np.array([1.0, 0.0, 0.0]), np.array([-1.0, 0.0, 0.0]),
    np.array([0.0, 1.0, 0.0]), np.array([0.0, -1.0, 0.0]),
    np.array([0.0, 0.0, 1.0]), np.array([0.0, 0.0, -1.0]),
)


def point_in_mesh(point: np.ndarray, mesh: TriangleMesh) -> bool:
    """
    점이 닫힌 메쉬 몸속에 있는가 — Jordan Curve 정리.
    6방향으로 레이를 쏘아 교차 횟수가 홀수인 방향이 과반이면 내부.
    (모서리 스침 등 수치 오차를 과반수 투표로 흡수)
    """
    if not mesh.triangles:
        return False
    odd_votes = 0
    for direction in _SIX_DIRECTIONS:
        # 인접 삼각형의 공유변/꼭짓점을 같은 t로 두 번 세는 것 방지: t 중복 제거
        ts = []
        for (v0, v1, v2) in mesh.triangles:
            t = _ray_triangle_t(point, direction, v0, v1, v2)
            if t is None:
                continue
            if all(abs(t - prev) > 1e-6 for prev in ts):
                ts.append(t)
        if len(ts) % 2 == 1:
            odd_votes += 1
    return odd_votes > len(_SIX_DIRECTIONS) // 2


def classify_faces_occlusion(
    faces: list[Face],
    other_meshes: list[TriangleMesh],
    probe_offset: float = 0.1,
) -> list[RayCastResult]:
    """
    차폐 기반 일괄 분류 (특허 의미 정본).
    각 면 중심에서 바깥 법선으로 probe_offset(기본 0.1mm)만큼 떨어진
    허공 점이 *다른 부재* 몸속이면 은폐면(조인트), 아니면 노출면(거푸집).
    """
    results = []
    for face in faces:
        n = face.world_normal / (np.linalg.norm(face.world_normal) + 1e-10)
        probe = face.center + n * probe_offset
        concealed = any(point_in_mesh(probe, m) for m in other_meshes)
        material = FaceMaterial.CONCRETE_JOINT if concealed else FaceMaterial.FORMWORK
        results.append(RayCastResult(
            face_id=face.face_id,
            is_concealed=concealed,
            dot_product=0.0,  # 차폐 판정에선 내적 미사용
            material=material,
        ))
    return results
