"""
codex.py — 프로젝트 구조 지식 베이스 (Structural Codex)
======================================================
일람표(S40)에서 추출된 부재 규격 정보를 저장하고 제공.
"G1" -> {"W": 500, "H": 600} 등의 매핑 관리.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class MemberSpec:
    name: str
    width: float = 0.0
    height: float = 0.0
    depth: float = 0.0  # 기둥용
    thickness: float = 0.0 # 슬래브/벽체용
    note: str = ""

class ProjectCodex:
    """프로젝트 전체의 구조 부재 규격 저장소."""
    def __init__(self):
        self.beams: Dict[str, MemberSpec] = {}
        self.columns: Dict[str, MemberSpec] = {}
        self.slabs: Dict[str, MemberSpec] = {}
        self.walls: Dict[str, MemberSpec] = {}

    def add_beam(self, name: str, w: float, h: float):
        self.beams[name.upper()] = MemberSpec(name=name, width=w, height=h)

    def get_beam_spec(self, name: str) -> Optional[MemberSpec]:
        return self.beams.get(name.upper())

    def add_column(self, name: str, w: float, d: float):
        self.columns[name.upper()] = MemberSpec(name=name, width=w, depth=d)

    def get_column_spec(self, name: str) -> Optional[MemberSpec]:
        return self.columns.get(name.upper())

    def report(self) -> str:
        return f"[Codex] Beams: {len(self.beams)}, Columns: {len(self.columns)}"

# 글로벌 코덱스 인스턴스 (싱글톤 패턴 또는 파이프라인 전달 방식 사용)
_global_codex = ProjectCodex()

def get_codex() -> ProjectCodex:
    return _global_codex
