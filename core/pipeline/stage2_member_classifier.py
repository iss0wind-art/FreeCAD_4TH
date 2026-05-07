"""
stage2_member_classifier.py — Stage 2: 부재별 분류
====================================================
Stage 1 FilterResult → 기둥/보/벽체/슬라브/기초 분리.
층별 JSON 산출물.

[분류 기준]
  기둥  (COLUMN) : S-기둥* 레이어 LWPOLYLINE(닫힌 단면) + HATCH
                   단면 크기 100~2500mm
  보    (BEAM)   : S-GIRDER / S-BEAM / S-PC-GIRDER 레이어 LINE
                   길이 300mm 이상
  벽체  (WALL)   : A-WALL-RC 레이어 LINE 쌍 (두께 100~600mm)
  슬라브(SLAB)   : S-SLAB 레이어 LWPOLYLINE (면적 기반)
  기초  (FND)    : S-FOUNDATION / S-BASE 레이어

[출력]
  ClassifyResult — 부재별 목록 (층별)
  stage2_members.json — 부재 목록 JSON
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.pipeline.stage1_structural_filter import (
    FilterResult, StructuralEntity, filter_structural,
)

# ── 레이어 → 부재 타입 매핑 ──────────────────────────────────

_BEAM_LAYER   = re.compile(r'S-GIRDER|S-BEAM|S-PC-GIRDER|00_BEAM|00_\(APT\)BEAM', re.IGNORECASE)
_WALL_LAYER   = re.compile(r'A-WALL-RC|S-WALL', re.IGNORECASE)
_SLAB_LAYER   = re.compile(r'S-SLAB', re.IGNORECASE)
_FND_LAYER    = re.compile(r'S-FOUNDATION|S-BASE|S-FND', re.IGNORECASE)
# 기둥: S- 접두사이고 위에 해당 안 되면 기둥 계열
_COL_LAYER    = re.compile(r'^S-|00_COLUMN', re.IGNORECASE)
_WALL2_LAYER  = re.compile(r'00_SHEAR.WALL', re.IGNORECASE)


# ── 자료구조 ─────────────────────────────────────────────────

@dataclass
class MemberRecord:
    member_type: str          # COLUMN / BEAM / WALL / SLAB / FND
    layer:       str
    etype:       str          # LINE / LWPOLYLINE / HATCH ...
    x:           float        # 중심 X
    y:           float        # 중심 Y
    # 치수 (Stage 3에서 채워짐, 여기선 기하 추정값)
    width:       Optional[float] = None   # mm
    height:      Optional[float] = None   # mm (보: 단면높이 / 기둥: 깊이)
    length:      Optional[float] = None   # 보 길이 / 기둥 둘레
    angle_deg:   Optional[float] = None   # 보 방향각
    # 좌표 원본
    coords:      List[Tuple[float,float]] = field(default_factory=list)


@dataclass
class ClassifyResult:
    floor:   str
    columns: List[MemberRecord] = field(default_factory=list)
    beams:   List[MemberRecord] = field(default_factory=list)
    walls:   List[MemberRecord] = field(default_factory=list)
    slabs:   List[MemberRecord] = field(default_factory=list)
    fnds:    List[MemberRecord] = field(default_factory=list)
    unknown: List[MemberRecord] = field(default_factory=list)

    def summary(self) -> Dict:
        return {
            'floor':   self.floor,
            'columns': len(self.columns),
            'beams':   len(self.beams),
            'walls':   len(self.walls),
            'slabs':   len(self.slabs),
            'fnds':    len(self.fnds),
            'unknown': len(self.unknown),
        }


# ── 분류기 ──────────────────────────────────────────────────

def classify(filter_result: FilterResult, floor: str = 'B2F') -> ClassifyResult:
    result = ClassifyResult(floor=floor)

    for se in filter_result.entities:
        layer = se.layer
        etype = se.etype
        coords = se.coords

        # 중심 좌표
        if coords:
            cx = sum(p[0] for p in coords) / len(coords)
            cy = sum(p[1] for p in coords) / len(coords)
        else:
            continue

        # ── 보 분류 ──────────────────────────────────────
        if _BEAM_LAYER.search(layer):
            if etype == 'LINE' and len(coords) == 2 and se.length and se.length >= 300:
                dx = coords[1][0] - coords[0][0]
                dy = coords[1][1] - coords[0][1]
                angle = math.degrees(math.atan2(dy, dx)) % 180
                # 유효 각도 필터 (건물 회전 ~14° 고려: 0°±20°, 90°±20°)
                a = angle % 180
                if not (a <= 20 or a >= 160 or 70 <= a <= 110 or 5 <= a <= 25 or 85 <= a <= 115):
                    continue
                rec = MemberRecord(
                    member_type='BEAM', layer=layer, etype=etype,
                    x=cx, y=cy, length=se.length, angle_deg=round(angle, 1),
                    coords=coords,
                )
                result.beams.append(rec)
            continue

        # ── 벽체 분류 ────────────────────────────────────
        if _WALL_LAYER.search(layer) or _WALL2_LAYER.search(layer):
            if etype == 'LINE' and se.length and se.length >= 200:
                dx = coords[1][0] - coords[0][0]
                dy = coords[1][1] - coords[0][1]
                angle = math.degrees(math.atan2(dy, dx)) % 180
                rec = MemberRecord(
                    member_type='WALL', layer=layer, etype=etype,
                    x=cx, y=cy, length=se.length, angle_deg=round(angle, 1),
                    coords=coords,
                )
                result.walls.append(rec)
            continue

        # ── 슬라브 분류 ──────────────────────────────────
        if _SLAB_LAYER.search(layer):
            rec = MemberRecord(
                member_type='SLAB', layer=layer, etype=etype,
                x=cx, y=cy, coords=coords,
            )
            result.slabs.append(rec)
            continue

        # ── 기초 분류 ────────────────────────────────────
        if _FND_LAYER.search(layer):
            rec = MemberRecord(
                member_type='FND', layer=layer, etype=etype,
                x=cx, y=cy, coords=coords,
            )
            result.fnds.append(rec)
            continue

        # ── 기둥 분류 (S- 계열 나머지) ──────────────────
        if _COL_LAYER.search(layer):
            # LWPOLYLINE만 실제 기둥 단면으로 인정 (LINE은 단면선이므로 무시)
            if etype != 'LWPOLYLINE':
                continue
            if len(coords) < 4:
                continue
            xs = [p[0] for p in coords]
            ys = [p[1] for p in coords]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if not (100 <= w <= 2500 and 100 <= h <= 2500):
                result.unknown.append(MemberRecord(
                    member_type='UNKNOWN', layer=layer, etype=etype,
                    x=cx, y=cy, coords=coords))
                continue
            rec = MemberRecord(
                member_type='COLUMN', layer=layer, etype=etype,
                x=cx, y=cy, width=round(w,1), height=round(h,1),
                coords=coords[:4],
            )
            result.columns.append(rec)
            continue

        result.unknown.append(MemberRecord(
            member_type='UNKNOWN', layer=layer, etype=etype,
            x=cx, y=cy, coords=coords,
        ))

    return result


# ── 저장 ────────────────────────────────────────────────────

def save_classify(result: ClassifyResult, out_path: str):
    def rec_to_dict(r: MemberRecord) -> dict:
        return {
            'type':  r.member_type,
            'layer': r.layer,
            'etype': r.etype,
            'x': round(r.x, 1), 'y': round(r.y, 1),
            'width':  round(r.width, 1)  if r.width  else None,
            'height': round(r.height, 1) if r.height else None,
            'length': round(r.length, 1) if r.length else None,
            'angle':  r.angle_deg,
        }

    data = {
        'summary': result.summary(),
        'columns': [rec_to_dict(r) for r in result.columns],
        'beams':   [rec_to_dict(r) for r in result.beams],
        'walls':   [rec_to_dict(r) for r in result.walls],
        'slabs':   [rec_to_dict(r) for r in result.slabs],
        'fnds':    [rec_to_dict(r) for r in result.fnds],
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=True, indent=2)


# ── 실행 ────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    sys.path.insert(0, 'D:/Git/FreeCAD_4TH')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    floors = {
        'B2F': (69013,  2241258, 229013, 2401258),
        'B1F': (195013, 2241258, 355013, 2401258),
    }

    DXF = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
    all_results = {}

    for floor, clip in floors.items():
        fr = filter_structural(DXF, clip=clip)
        cr = classify(fr, floor=floor)
        all_results[floor] = cr
        s = cr.summary()
        print(f'\n[{floor}]')
        print(f'  기둥: {s["columns"]:4d}개')
        print(f'  보:   {s["beams"]:4d}개')
        print(f'  벽체: {s["walls"]:4d}개')
        print(f'  슬라브:{s["slabs"]:4d}개')
        print(f'  기초: {s["fnds"]:4d}개')
        print(f'  미분류:{s["unknown"]:4d}개')

        save_classify(cr, f'output/stage2_{floor.lower()}.json')
        print(f'  → output/stage2_{floor.lower()}.json')

    # 보 각도 분포
    print('\n=== B2F 보 각도 분포 ===')
    from collections import Counter
    angles = Counter(round(b.angle_deg / 5) * 5
                     for b in all_results['B2F'].beams if b.angle_deg is not None)
    for ang in sorted(angles):
        print(f'  {ang:3d}°: {angles[ang]:4d}개')
