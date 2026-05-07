"""
member_data.py — 부재 단일 데이터 모델
========================================
Track 1 / Track 2 양쪽이 공유하는 Member 정의.

[설계 원칙]
  - 5종 타입(COLUMN/BEAM/WALL/SLAB/FND) 단일 dataclass
  - 타입별 필드는 Optional, 검증은 type 기반
  - to_dict / from_dict 라운드트립 보장
  - 체적·면적 계산은 메서드로 (저장 X, 도출 O)

[현재 v7·v9·v11 빌드 스크립트에 흩어진 Member 정의를 통합]
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

# ─────────────────────────────────────────────────────────────
# 타입 상수
# ─────────────────────────────────────────────────────────────

VALID_TYPES = frozenset({"COLUMN", "BEAM", "WALL", "SLAB", "FND"})

_SECTION_PAT = re.compile(r"(\d+)\s*[xX×]\s*(\d+)")


# ─────────────────────────────────────────────────────────────
# Member dataclass
# ─────────────────────────────────────────────────────────────

@dataclass
class Member:
    """단일 부재.

    공통 필드는 모두 필수, 타입별 필드는 Optional.
    """
    id: str
    type: str                # COLUMN / BEAM / WALL / SLAB / FND
    floor: str               # B2F / B1F / 1F ...
    source: str              # DONG / PKG
    x: float                 # 중심/시작 X (mm)
    y: float                 # 중심/시작 Y (mm)
    z_bot: float             # 바닥 Z (mm)
    z_top: float             # 상단 Z (mm)
    layer: str               # DXF 레이어명

    # 타입별 옵션
    section:    Optional[str]   = None  # COLUMN/BEAM "400x800"
    length_mm:  Optional[float] = None  # BEAM/WALL
    height_mm:  Optional[float] = None  # WALL (z_top-z_bot 와 별도일 수 있음)
    angle_deg:  Optional[float] = None  # BEAM/WALL (수평 각도)
    area_m2:    Optional[float] = None  # SLAB

    def __post_init__(self) -> None:
        if self.type not in VALID_TYPES:
            raise ValueError(
                f"invalid type {self.type!r} (allowed: {sorted(VALID_TYPES)})"
            )
        # COLUMN·FND는 height_mm 미지정 시 z 차이로 자동 채움
        if self.height_mm is None and self.type in ("COLUMN", "FND"):
            self.height_mm = float(self.z_top) - float(self.z_bot)

    # ── 도출값 ────────────────────────────────────────────
    @property
    def height_z_mm(self) -> float:
        """z_top - z_bot."""
        return float(self.z_top) - float(self.z_bot)

    # height_mm 별칭 (호환성)
    @property
    def height_mm_effective(self) -> float:
        return self.height_mm if self.height_mm is not None else self.height_z_mm

    # 라운드트립 호환을 위한 height_mm property → 직접 필드라 그대로 사용
    # COLUMN의 경우 height_mm 미지정 → height_z_mm 으로 대체

    def height_mm_for_volume(self) -> float:
        """체적 계산용 높이."""
        if self.height_mm is not None:
            return float(self.height_mm)
        return self.height_z_mm

    @property
    def height_mm_default(self) -> float:
        """체적 계산용 기본 높이."""
        return self.height_mm_for_volume()

    def parse_section(self) -> Optional[tuple[float, float]]:
        """section 'WxH' → (W, H) mm."""
        if not self.section:
            return None
        m = _SECTION_PAT.search(self.section)
        if not m:
            return None
        return float(m.group(1)), float(m.group(2))

    def volume_m3(self, default_section: tuple[float, float] = (400, 400)) -> float:
        """체적 (m³)."""
        if self.type == "COLUMN":
            sec = self.parse_section() or default_section
            w, h = sec
            return (w / 1000.0) * (h / 1000.0) * (self.height_z_mm / 1000.0)

        if self.type == "BEAM":
            sec = self.parse_section() or default_section
            bw, bh = sec
            length = float(self.length_mm or 0.0)
            return (length / 1000.0) * (bw / 1000.0) * (bh / 1000.0)

        if self.type == "WALL":
            length = float(self.length_mm or 0.0)
            height = self.height_mm_for_volume()
            sec = self.parse_section()
            if sec:
                # WALL의 section은 'thickness x height' 규약
                thickness, _ = sec
                return (length / 1000.0) * (thickness / 1000.0) * (height / 1000.0)
            return 0.0

        if self.type == "FND":
            sec = self.parse_section() or default_section
            w, h = sec
            return (w / 1000.0) * (h / 1000.0) * (self.height_z_mm / 1000.0)

        # SLAB은 체적 의미 없음 (두께 정보 없음)
        return 0.0

    def area_value_m2(self) -> float:
        """면적 (m²). WALL=length*height, SLAB=area_m2."""
        if self.type == "WALL":
            length = float(self.length_mm or 0.0)
            height = self.height_mm_for_volume()
            return (length / 1000.0) * (height / 1000.0)

        if self.type == "SLAB":
            return float(self.area_m2 or 0.0)

        return 0.0

    # ── 직렬화 ────────────────────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # None 값 제거 (JSON 슬림화)
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Member":
        # 알려진 필드만 추출
        valid_keys = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in d.items() if k in valid_keys}
        return cls(**kwargs)


# ─────────────────────────────────────────────────────────────
# MemberCollection
# ─────────────────────────────────────────────────────────────

@dataclass
class MemberCollection:
    """부재 컬렉션 + 집계 메서드."""
    members: List[Member] = field(default_factory=list)
    meta:    Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.members)

    def __iter__(self):
        return iter(self.members)

    # ── 로드/저장 ─────────────────────────────────────────
    @classmethod
    def load_json(cls, path: Union[str, Path]) -> "MemberCollection":
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        members = [Member.from_dict(m) for m in data.get("members", [])]
        return cls(members=members, meta=data.get("meta", {}))

    def save_json(self, path: Union[str, Path]) -> None:
        path = Path(path)
        out = {
            "meta": {
                **self.meta,
                "total": len(self.members),
                "by_type": self.count_by_type(),
                "saved_at": datetime.now().isoformat(timespec="seconds"),
            },
            "members": [m.to_dict() for m in self.members],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    # ── 집계 ──────────────────────────────────────────────
    def count_by_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for m in self.members:
            counts[m.type] = counts.get(m.type, 0) + 1
        return counts

    def count_by_floor(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for m in self.members:
            counts[m.floor] = counts.get(m.floor, 0) + 1
        return counts

    def total_volume_m3(self, type_filter: Optional[str] = None) -> float:
        total = 0.0
        for m in self.members:
            if type_filter and m.type != type_filter:
                continue
            total += m.volume_m3()
        return total

    def total_area_m2(self, type_filter: Optional[str] = None) -> float:
        total = 0.0
        for m in self.members:
            if type_filter and m.type != type_filter:
                continue
            total += m.area_value_m2()
        return total

    def filter(
        self,
        type_: Optional[str] = None,
        floor: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Member]:
        out = self.members
        if type_:
            out = [m for m in out if m.type == type_]
        if floor:
            out = [m for m in out if m.floor == floor]
        if source:
            out = [m for m in out if m.source == source]
        return out
