"""
core/pipeline/member_data.py — Unified Member Data Model
========================================================
v7, v9, v11 규격을 통합한 단일 Member 데이터 모델 정의.
Track 1(Direct)과 Track 2(Skeleton)에서 공통으로 사용.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import uuid

@dataclass
class Member:
    member_type: str              # COLUMN, BEAM, WALL, SLAB, FND
    spec:        str              # 부재 일람표 명칭 (예: C1, G1, W1)
    floor:       str              # 층 (예: B2F, 1F)
    id:          str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 기하 정보
    x:           float = 0.0      # 중심 또는 시작점 X
    y:           float = 0.0      # 중심 또는 시작점 Y
    z:           float = 0.0      # 중심 또는 시작점 Z (층고 기반 자동 계산)
    
    # 차원 (Dimensions)
    width:       Optional[float] = None   # 폭 (mm)
    height:      Optional[float] = None   # 높이/두께 (mm)
    length:      Optional[float] = None   # 길이 (mm)
    depth:       Optional[float] = None   # 깊이 (기둥 등에서 사용)
    
    # 상세 기하
    rotation:    float = 0.0      # 회전각 (deg)
    z_offset:    float = 0.0      # 수직 오프셋 (mm)
    coords:      List[Tuple[float, float]] = field(default_factory=list) # 다각형 꼭짓점 또는 시작/끝
    
    # BOQ 산출물
    volume:      float = 0.0      # 체적 (m3)
    area:        float = 0.0      # 면적 (m2)
    
    # 메타데이터
    layer:       Optional[str] = None
    etype:       Optional[str] = None
    metadata:    Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id':          self.id,
            'type':        self.member_type,
            'spec':        self.spec,
            'floor':       self.floor,
            'x':           round(self.x, 2),
            'y':           round(self.y, 2),
            'z':           round(self.z, 2),
            'width':       round(self.width, 2) if self.width else None,
            'height':      round(self.height, 2) if self.height else None,
            'length':      round(self.length, 2) if self.length else None,
            'rotation':    round(self.rotation, 2),
            'z_offset':    round(self.z_offset, 2),
            'volume':      round(self.volume, 4),
            'area':        round(self.area, 2),
            'layer':       self.layer,
            'metadata':    self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Member:
        # dict 데이터를 Member 객체로 복원 (필요 시 구현)
        m_id = data.get('id', str(uuid.uuid4()))
        return cls(
            id=m_id,
            member_type=data.get('type', 'UNKNOWN'),
            spec=data.get('spec', 'N/A'),
            floor=data.get('floor', 'UNKNOWN'),
            x=data.get('x', 0.0),
            y=data.get('y', 0.0),
            z=data.get('z', 0.0),
            width=data.get('width'),
            height=data.get('height'),
            length=data.get('length'),
            rotation=data.get('rotation', 0.0),
            z_offset=data.get('z_offset', 0.0),
            layer=data.get('layer'),
            metadata=data.get('metadata', {})
        )
