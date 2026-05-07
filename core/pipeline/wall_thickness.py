"""
wall_thickness.py — WALL 두께 추정
====================================
DXF 레이어 패턴 → 두께(mm) 매핑.

[규칙]
  00_SHEAR WALL      → 300mm (전단벽, RC 무거운)
  A-WALL-RC          → 200mm (RC 일반 벽체)
  S-하부벽체         → 200mm
  기타               → 200mm (기본 폴백)
"""
from __future__ import annotations

import re

# ─────────────────────────────────────────────────────────────
# 패턴 → 두께 매핑 (우선순위 순서)
# ─────────────────────────────────────────────────────────────

_THICKNESS_RULES = [
    (re.compile(r"SHEAR\s*WALL", re.IGNORECASE), 300),
    (re.compile(r"A[-_]WALL[-_]RC", re.IGNORECASE), 200),
    (re.compile(r"S[-_]?하부벽체", re.IGNORECASE), 200),
    (re.compile(r"S[-_]WALL", re.IGNORECASE), 200),
]

DEFAULT_THICKNESS_MM = 200


def estimate_wall_thickness(layer: str) -> int:
    """레이어명 → 추정 두께(mm)."""
    if not layer:
        return DEFAULT_THICKNESS_MM
    for pat, thick in _THICKNESS_RULES:
        if pat.search(layer):
            return thick
    return DEFAULT_THICKNESS_MM
