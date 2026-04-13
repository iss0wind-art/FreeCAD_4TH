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
