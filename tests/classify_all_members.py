"""
classify_all_members.py — 전체 구조 부재 완전 분류
====================================================
DONG + PKG 두 DXF에서 기둥/보/벽체/슬라브/기초를 전수 추출.
output/members_accumulated.json  — 전체 부재 목록
output/members_boq.json          — 타입별 BOQ 집계

[분류 기준]
  COLUMN : DONG = XR...$A-COL LWPOLYLINE (단면 100~2500mm)
           PKG  = 00_COLUMN LWPOLYLINE
  BEAM   : DONG = S-GIRDER / S-BEAM / S-PC-GIRDER LINE (>=300mm)
           PKG  = 00_BEAM / 00_(APT)BEAM LINE
  WALL   : DONG = XR...$A-WALL-RC LINE (>=200mm) + S-하부벽체 LINE
           PKG  = 00_SHEAR WALL LINE
  SLAB   : PKG  = S-PC-SLAB LWPOLYLINE (닫힌 폴리라인, 면적 계산)
           DONG = S-SLAB-SYMBOL 위치 기호 (면적 없음)
  FND    : DONG = S-FOUNDATION / S-BASE LINE+LWPOLYLINE
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ezdxf

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.entity_scanner import iter_all

# ── 경로 ────────────────────────────────────────────────────
DXF_DONG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
DXF_PKG  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'
OUT_DIR  = Path('output')

# ── 층별 클립 영역 (DONG) ──────────────────────────────────
DONG_FLOORS: Dict[str, Tuple[float, float, float, float]] = {
    'B2F': (69013,  2241258, 229013, 2401258),
    'B1F': (195013, 2241258, 355013, 2401258),
}

# ── 층고 (mm, stage0_levels.json 기반) ─────────────────────
FLOOR_Z: Dict[str, Dict[str, float]] = {
    'B2F': {'z_bot': -9050, 'z_top': -5600},
    'B1F': {'z_bot': -5600, 'z_top':   370},
    'PKG': {'z_bot': -9050, 'z_top': -5600},
}

# ── 레이어 패턴 ──────────────────────────────────────────────
_DONG_COL   = re.compile(r'A-COL(?:\(TR\))?$', re.IGNORECASE)
_DONG_BEAM  = re.compile(r'S-GIRDER|S-BEAM|S-PC-GIRDER', re.IGNORECASE)
_DONG_WALL  = re.compile(r'A-WALL-RC|S-하부벽체|S-WALL(?!-SYMBOL)', re.IGNORECASE)
_DONG_SLAB  = re.compile(r'S-SLAB-SYMBOL', re.IGNORECASE)
_DONG_FND   = re.compile(r'S-FOUNDATION|S-BASE|S-FND', re.IGNORECASE)

_PKG_COL    = re.compile(r'00_COLUMN$', re.IGNORECASE)
_PKG_BEAM   = re.compile(r'00_BEAM$|00_\(APT\)BEAM', re.IGNORECASE)
_PKG_WALL   = re.compile(r'00_SHEAR WALL$', re.IGNORECASE)
_PKG_SLAB   = re.compile(r'S-PC-SLAB$', re.IGNORECASE)
_PKG_FND    = re.compile(r'S-FOUNDATION|S-BASE|S-FND', re.IGNORECASE)

# 덧방용 수동 보조선 레이어
_ADD_COL    = re.compile(r'(ADD[-_]COL|덧방[-_]기둥)', re.IGNORECASE)
_ADD_BEAM   = re.compile(r'(ADD[-_]BEAM|덧방[-_]보)', re.IGNORECASE)
_ADD_WALL   = re.compile(r'(ADD[-_]WALL|덧방[-_]벽체)', re.IGNORECASE)
_ADD_SLAB   = re.compile(r'(ADD[-_]SLAB|덧방[-_]슬라브)', re.IGNORECASE)


# ── 면적 계산 ──────────────────────────────────────────────
def poly_area(pts: List[Tuple[float, float]]) -> float:
    """폴리라인 면적 계산. 점 순서가 self-crossing일 경우 중심 기준 각도 정렬 후 재계산.

    반환: mm² (양수).
    """
    import cmath

    def _shoelace(polygon: List[Tuple[float, float]]) -> float:
        n = len(polygon)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += polygon[i][0] * polygon[j][1]
            area -= polygon[j][0] * polygon[i][1]
        return abs(area) / 2.0

    if len(pts) < 3:
        return 0.0

    area = _shoelace(pts)
    if area > 1.0:
        return area

    # Shoelace가 0이면 self-crossing → 중심 기준 각도 정렬 후 재시도
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    sorted_pts = sorted(pts, key=lambda p: -cmath.phase(complex(p[0] - cx, p[1] - cy)))
    return _shoelace(sorted_pts)


def get_lwpoly_coords(e) -> List[Tuple[float, float]]:
    return [(p[0], p[1]) for p in e.get_points()]


# ── 중심 좌표 ──────────────────────────────────────────────
def centroid(coords: List[Tuple[float, float]]) -> Tuple[float, float]:
    cx = sum(p[0] for p in coords) / len(coords)
    cy = sum(p[1] for p in coords) / len(coords)
    return cx, cy


def in_clip(cx: float, cy: float,
            clip: Tuple[float, float, float, float]) -> bool:
    return clip[0] <= cx <= clip[2] and clip[1] <= cy <= clip[3]


# ── DONG 분류 ───────────────────────────────────────────────
def classify_dong(
    dxf_path: str,
    floors: Dict[str, Tuple[float, float, float, float]],
) -> List[dict]:
    """DONG DXF에서 B2F/B1F 부재 추출. iter_all로 INSERT 재귀."""

    print(f'\n[DONG] 파일 열기: {dxf_path}')
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    members: List[dict] = []
    counters: Dict[str, int] = {}

    def next_id(member_type: str, floor: str) -> str:
        key = f'{member_type}-{floor}'
        counters[key] = counters.get(key, 0) + 1
        return f'{member_type}-{floor}-{counters[key]:04d}'

    for floor, clip in floors.items():
        zb = FLOOR_Z.get(floor, {}).get('z_bot', 0)
        zt = FLOOR_Z.get(floor, {}).get('z_top', 0)
        h_floor = zt - zb  # 층고 mm

        col_cnt = beam_cnt = wall_cnt = slab_cnt = fnd_cnt = 0

        for e in iter_all(msp):
            try:
                layer = e.dxf.layer
                etype = e.dxftype()
                coords: List[Tuple[float, float]] = []

                if etype == 'LINE':
                    s, en = e.dxf.start, e.dxf.end
                    coords = [(s.x, s.y), (en.x, en.y)]
                elif etype == 'LWPOLYLINE':
                    coords = get_lwpoly_coords(e)
                elif etype in ('TEXT', 'MTEXT', 'ELLIPSE'):
                    p = getattr(e.dxf, 'insert', None) or getattr(e.dxf, 'center', None)
                    if p:
                        coords = [(p.x, p.y)]
                else:
                    continue

                if not coords:
                    continue

                cx, cy = centroid(coords)
                if not in_clip(cx, cy, clip):
                    continue

                # ── 수동 덧방 / 바이패스 처리 분기 ────────────────
                if _ADD_COL.search(layer):
                    if etype == 'LWPOLYLINE' and len(coords) >= 3:
                        xs = [p[0] for p in coords]
                        ys = [p[1] for p in coords]
                        w = max(xs) - min(xs)
                        h = max(ys) - min(ys)
                        members.append({
                            'id': next_id('COL', floor),
                            'type': 'COLUMN',
                            'floor': floor,
                            'source': 'DONG',
                            'x': round(cx, 1), 'y': round(cy, 1),
                            'z_bot': zb, 'z_top': zt,
                            'section': f'{round(w)}x{round(h)}',
                            'layer': layer,
                            'bypass_filter': True,
                        })
                        col_cnt += 1
                        continue

                elif _ADD_BEAM.search(layer):
                    if etype in ('LINE', 'LWPOLYLINE'):
                        for i in range(len(coords)-1):
                            L = math.hypot(coords[i+1][0] - coords[i][0], coords[i+1][1] - coords[i][1])
                            dx = coords[i+1][0] - coords[i][0]
                            dy = coords[i+1][1] - coords[i][1]
                            ang = math.degrees(math.atan2(dy, dx)) % 180
                            members.append({
                                'id': next_id('BM', floor),
                                'type': 'BEAM',
                                'floor': floor,
                                'source': 'DONG',
                                'x': round((coords[i][0]+coords[i+1][0])/2, 1), 'y': round((coords[i][1]+coords[i+1][1])/2, 1),
                                'z_bot': zb, 'z_top': zt,
                                'length_mm': round(L, 1),
                                'angle_deg': round(ang, 1),
                                'layer': layer,
                                'bypass_filter': True,
                            })
                            beam_cnt += 1
                        continue

                elif _ADD_WALL.search(layer):
                    if etype in ('LINE', 'LWPOLYLINE'):
                        for i in range(len(coords)-1):
                            L = math.hypot(coords[i+1][0] - coords[i][0], coords[i+1][1] - coords[i][1])
                            dx = coords[i+1][0] - coords[i][0]
                            dy = coords[i+1][1] - coords[i][1]
                            ang = math.degrees(math.atan2(dy, dx)) % 180
                            members.append({
                                'id': next_id('WL', floor),
                                'type': 'WALL',
                                'floor': floor,
                                'source': 'DONG',
                                'x': round((coords[i][0]+coords[i+1][0])/2, 1), 'y': round((coords[i][1]+coords[i+1][1])/2, 1),
                                'z_bot': zb, 'z_top': zt,
                                'length_mm': round(L, 1),
                                'height_mm': h_floor,
                                'angle_deg': round(ang, 1),
                                'layer': layer,
                                'bypass_filter': True,
                            })
                            wall_cnt += 1
                        continue

                elif _ADD_SLAB.search(layer):
                    if etype == 'LWPOLYLINE' and len(coords) >= 3:
                        area_mm2 = poly_area(coords)
                        members.append({
                            'id': next_id('SL', floor),
                            'type': 'SLAB',
                            'floor': floor,
                            'source': 'DONG',
                            'x': round(cx, 1), 'y': round(cy, 1),
                            'z_bot': zb, 'z_top': zt,
                            'area_m2': round(area_mm2 / 1e6, 3),
                            'layer': layer,
                            'bypass_filter': True,
                        })
                        slab_cnt += 1
                        continue

                # ── 기둥 ──────────────────────────────────
                if _DONG_COL.search(layer) and etype == 'LWPOLYLINE':
                    if len(coords) < 3:
                        continue
                    xs = [p[0] for p in coords]
                    ys = [p[1] for p in coords]
                    w = max(xs) - min(xs)
                    h = max(ys) - min(ys)
                    if not (100 <= w <= 2500 and 100 <= h <= 2500):
                        continue
                    mid = f'{round(w)}x{round(h)}'
                    members.append({
                        'id': next_id('COL', floor),
                        'type': 'COLUMN',
                        'floor': floor,
                        'source': 'DONG',
                        'x': round(cx, 1), 'y': round(cy, 1),
                        'z_bot': zb, 'z_top': zt,
                        'section': mid,
                        'layer': layer,
                    })
                    col_cnt += 1

                # ── 보 ────────────────────────────────────
                elif _DONG_BEAM.search(layer) and etype == 'LINE':
                    L = math.hypot(
                        coords[1][0] - coords[0][0],
                        coords[1][1] - coords[0][1]
                    )
                    if L < 300:
                        continue
                    dx = coords[1][0] - coords[0][0]
                    dy = coords[1][1] - coords[0][1]
                    ang = math.degrees(math.atan2(dy, dx)) % 180
                    members.append({
                        'id': next_id('BM', floor),
                        'type': 'BEAM',
                        'floor': floor,
                        'source': 'DONG',
                        'x': round(cx, 1), 'y': round(cy, 1),
                        'z_bot': zb, 'z_top': zt,
                        'length_mm': round(L, 1),
                        'angle_deg': round(ang, 1),
                        'layer': layer,
                    })
                    beam_cnt += 1

                # ── 벽체 ─────────────────────────────────
                elif _DONG_WALL.search(layer) and etype == 'LINE':
                    L = math.hypot(
                        coords[1][0] - coords[0][0],
                        coords[1][1] - coords[0][1]
                    )
                    if L < 200:
                        continue
                    dx = coords[1][0] - coords[0][0]
                    dy = coords[1][1] - coords[0][1]
                    ang = math.degrees(math.atan2(dy, dx)) % 180
                    members.append({
                        'id': next_id('WL', floor),
                        'type': 'WALL',
                        'floor': floor,
                        'source': 'DONG',
                        'x': round(cx, 1), 'y': round(cy, 1),
                        'z_bot': zb, 'z_top': zt,
                        'length_mm': round(L, 1),
                        'height_mm': h_floor,
                        'angle_deg': round(ang, 1),
                        'layer': layer,
                    })
                    wall_cnt += 1

                # ── 슬라브 기호 (위치만) ────────────────
                elif _DONG_SLAB.search(layer):
                    members.append({
                        'id': next_id('SL', floor),
                        'type': 'SLAB',
                        'floor': floor,
                        'source': 'DONG',
                        'x': round(cx, 1), 'y': round(cy, 1),
                        'z_bot': zb, 'z_top': zt,
                        'area_m2': None,   # 면적 없음 (기호)
                        'note': 'symbol_only',
                        'layer': layer,
                    })
                    slab_cnt += 1

                # ── 기초 ─────────────────────────────────
                elif _DONG_FND.search(layer):
                    fnd_data = {
                        'id': next_id('FND', floor),
                        'type': 'FND',
                        'floor': floor,
                        'source': 'DONG',
                        'x': round(cx, 1), 'y': round(cy, 1),
                        'z_bot': zb - 1000, 'z_top': zb,
                        'layer': layer,
                    }
                    if etype == 'LWPOLYLINE' and len(coords) >= 3:
                        fnd_data['points'] = [(round(p[0], 1), round(p[1], 1)) for p in coords]
                        area_m2 = poly_area(coords) / 1e6
                        fnd_data['area_m2'] = round(area_m2, 3)
                    members.append(fnd_data)
                    fnd_cnt += 1

            except Exception:
                continue

        print(f'  [{floor}] COL={col_cnt}, BM={beam_cnt}, WL={wall_cnt}, SL={slab_cnt}, FND={fnd_cnt}')

    return members


# ── PKG 분류 ────────────────────────────────────────────────
def classify_pkg(dxf_path: str) -> List[dict]:
    """PKG DXF에서 부재 추출 (클립 없이 전체)."""

    print(f'\n[PKG] 파일 열기: {dxf_path}')
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    members: List[dict] = []
    counters: Dict[str, int] = {}
    floor = 'PKG'
    zb = FLOOR_Z['PKG']['z_bot']
    zt = FLOOR_Z['PKG']['z_top']
    h_floor = zt - zb

    def next_id(member_type: str) -> str:
        counters[member_type] = counters.get(member_type, 0) + 1
        return f'{member_type}-PKG-{counters[member_type]:04d}'

    col_cnt = beam_cnt = wall_cnt = slab_cnt = fnd_cnt = 0

    for e in msp:
        try:
            layer = e.dxf.layer
            etype = e.dxftype()
            coords: List[Tuple[float, float]] = []

            if etype == 'LINE':
                s, en = e.dxf.start, e.dxf.end
                coords = [(s.x, s.y), (en.x, en.y)]
            elif etype == 'LWPOLYLINE':
                coords = get_lwpoly_coords(e)
            elif etype in ('TEXT', 'MTEXT'):
                p = getattr(e.dxf, 'insert', None)
                if p:
                    coords = [(p.x, p.y)]
            else:
                continue

            if not coords:
                continue

            cx, cy = centroid(coords)

            # ── 수동 덧방 / 바이패스 처리 분기 ────────────────
            if _ADD_COL.search(layer):
                if etype == 'LWPOLYLINE' and len(coords) >= 3:
                    xs = [p[0] for p in coords]
                    ys = [p[1] for p in coords]
                    w = max(xs) - min(xs)
                    h = max(ys) - min(ys)
                    members.append({
                        'id': next_id('COL'),
                        'type': 'COLUMN',
                        'floor': floor,
                        'source': 'PKG',
                        'x': round(cx, 1), 'y': round(cy, 1),
                        'z_bot': zb, 'z_top': zt,
                        'section': f'{round(w)}x{round(h)}',
                        'layer': layer,
                        'bypass_filter': True,
                    })
                    col_cnt += 1
                    continue

            elif _ADD_BEAM.search(layer):
                if etype in ('LINE', 'LWPOLYLINE'):
                    for i in range(len(coords)-1):
                        L = math.hypot(coords[i+1][0] - coords[i][0], coords[i+1][1] - coords[i][1])
                        dx = coords[i+1][0] - coords[i][0]
                        dy = coords[i+1][1] - coords[i][1]
                        ang = math.degrees(math.atan2(dy, dx)) % 180
                        members.append({
                            'id': next_id('BM'),
                            'type': 'BEAM',
                            'floor': floor,
                            'source': 'PKG',
                            'x': round((coords[i][0]+coords[i+1][0])/2, 1), 'y': round((coords[i][1]+coords[i+1][1])/2, 1),
                            'z_bot': zb, 'z_top': zt,
                            'length_mm': round(L, 1),
                            'angle_deg': round(ang, 1),
                            'layer': layer,
                            'bypass_filter': True,
                        })
                        beam_cnt += 1
                    continue

            elif _ADD_WALL.search(layer):
                if etype in ('LINE', 'LWPOLYLINE'):
                    for i in range(len(coords)-1):
                        L = math.hypot(coords[i+1][0] - coords[i][0], coords[i+1][1] - coords[i][1])
                        dx = coords[i+1][0] - coords[i][0]
                        dy = coords[i+1][1] - coords[i][1]
                        ang = math.degrees(math.atan2(dy, dx)) % 180
                        members.append({
                            'id': next_id('WL'),
                            'type': 'WALL',
                            'floor': floor,
                            'source': 'PKG',
                            'x': round((coords[i][0]+coords[i+1][0])/2, 1), 'y': round((coords[i][1]+coords[i+1][1])/2, 1),
                            'z_bot': zb, 'z_top': zt,
                            'length_mm': round(L, 1),
                            'height_mm': h_floor,
                            'angle_deg': round(ang, 1),
                            'layer': layer,
                            'bypass_filter': True,
                        })
                        wall_cnt += 1
                    continue

            elif _ADD_SLAB.search(layer):
                if etype == 'LWPOLYLINE' and len(coords) >= 3:
                    area_mm2 = poly_area(coords)
                    members.append({
                        'id': next_id('SL'),
                        'type': 'SLAB',
                        'floor': floor,
                        'source': 'PKG',
                        'x': round(cx, 1), 'y': round(cy, 1),
                        'z_bot': zb, 'z_top': zt,
                        'area_m2': round(area_mm2 / 1e6, 3),
                        'layer': layer,
                        'bypass_filter': True,
                    })
                    slab_cnt += 1
                    continue

            # ── 기둥 ──────────────────────────────────────
            if _PKG_COL.search(layer) and etype == 'LWPOLYLINE':
                if len(coords) < 3:
                    continue
                xs = [p[0] for p in coords]
                ys = [p[1] for p in coords]
                w = max(xs) - min(xs)
                h = max(ys) - min(ys)
                if not (100 <= w <= 3000 and 100 <= h <= 3000):
                    continue
                members.append({
                    'id': next_id('COL'),
                    'type': 'COLUMN',
                    'floor': floor,
                    'source': 'PKG',
                    'x': round(cx, 1), 'y': round(cy, 1),
                    'z_bot': zb, 'z_top': zt,
                    'section': f'{round(w)}x{round(h)}',
                    'layer': layer,
                })
                col_cnt += 1

            # ── 보 ────────────────────────────────────────
            elif _PKG_BEAM.search(layer) and etype == 'LINE':
                L = math.hypot(
                    coords[1][0] - coords[0][0],
                    coords[1][1] - coords[0][1]
                )
                if L < 300:
                    continue
                dx = coords[1][0] - coords[0][0]
                dy = coords[1][1] - coords[0][1]
                ang = math.degrees(math.atan2(dy, dx)) % 180
                members.append({
                    'id': next_id('BM'),
                    'type': 'BEAM',
                    'floor': floor,
                    'source': 'PKG',
                    'x': round(cx, 1), 'y': round(cy, 1),
                    'z_bot': zb, 'z_top': zt,
                    'length_mm': round(L, 1),
                    'angle_deg': round(ang, 1),
                    'layer': layer,
                })
                beam_cnt += 1

            # ── 벽체 (전단벽) ─────────────────────────────
            elif _PKG_WALL.search(layer) and etype == 'LINE':
                L = math.hypot(
                    coords[1][0] - coords[0][0],
                    coords[1][1] - coords[0][1]
                )
                if L < 200:
                    continue
                dx = coords[1][0] - coords[0][0]
                dy = coords[1][1] - coords[0][1]
                ang = math.degrees(math.atan2(dy, dx)) % 180
                members.append({
                    'id': next_id('WL'),
                    'type': 'WALL',
                    'floor': floor,
                    'source': 'PKG',
                    'x': round(cx, 1), 'y': round(cy, 1),
                    'z_bot': zb, 'z_top': zt,
                    'length_mm': round(L, 1),
                    'height_mm': h_floor,
                    'angle_deg': round(ang, 1),
                    'layer': layer,
                })
                wall_cnt += 1

            # ── 슬라브 ────────────────────────────────────
            elif _PKG_SLAB.search(layer) and etype == 'LWPOLYLINE':
                if len(coords) < 3:
                    continue
                area_mm2 = poly_area(coords)
                area_m2 = area_mm2 / 1e6
                members.append({
                    'id': next_id('SL'),
                    'type': 'SLAB',
                    'floor': floor,
                    'source': 'PKG',
                    'x': round(cx, 1), 'y': round(cy, 1),
                    'z_bot': zb, 'z_top': zt,
                    'area_m2': round(area_m2, 3),
                    'layer': layer,
                })
                slab_cnt += 1

            # ── 기초 ─────────────────────────────────────
            elif _PKG_FND.search(layer):
                fnd_data = {
                    'id': next_id('FND'),
                    'type': 'FND',
                    'floor': floor,
                    'source': 'PKG',
                    'x': round(cx, 1), 'y': round(cy, 1),
                    'z_bot': zb - 1000, 'z_top': zb,
                    'layer': layer,
                }
                if etype == 'LWPOLYLINE' and len(coords) >= 3:
                    fnd_data['points'] = [(round(p[0], 1), round(p[1], 1)) for p in coords]
                    area_m2 = poly_area(coords) / 1e6
                    fnd_data['area_m2'] = round(area_m2, 3)
                members.append(fnd_data)
                fnd_cnt += 1

        except Exception:
            continue

    print(f'  [PKG] COL={col_cnt}, BM={beam_cnt}, WL={wall_cnt}, SL={slab_cnt}, FND={fnd_cnt}')
    return members


# ── 누적 저장 ───────────────────────────────────────────────
def save_accumulated(members: List[dict], out_path: Path) -> None:
    by_type: Dict[str, int] = {}
    for m in members:
        t = m['type']
        by_type[t] = by_type.get(t, 0) + 1

    data = {
        'meta': {
            'total': len(members),
            'by_type': by_type,
            'last_updated': datetime.now().isoformat(timespec='seconds'),
        },
        'members': members,
    }
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f'\n-> {out_path}  ({len(members)}건)')


# ── BOQ 집계 ────────────────────────────────────────────────
def compute_boq(members: List[dict]) -> dict:
    boq: Dict[str, dict] = {
        'COLUMN': {'count': 0, 'total_volume_m3': 0.0},
        'BEAM':   {'count': 0, 'total_volume_m3': 0.0},
        'WALL':   {'count': 0, 'total_area_m2':   0.0},
        'SLAB':   {'count': 0, 'total_area_m2':   0.0},
        'FND':    {'count': 0},
    }

    for m in members:
        t = m['type']
        if t not in boq:
            continue
        boq[t]['count'] += 1

        if t == 'COLUMN':
            sec = m.get('section', '')
            try:
                parts = sec.replace('X', 'x').split('x')
                w_m = float(parts[0]) / 1000
                h_m = float(parts[1]) / 1000
                ht_m = (m.get('z_top', 0) - m.get('z_bot', 0)) / 1000
                boq[t]['total_volume_m3'] += w_m * h_m * ht_m
            except Exception:
                pass

        elif t == 'BEAM':
            L_m = (m.get('length_mm') or 0) / 1000
            # 단면 미확정이므로 대표값 0.5x0.8 m 적용
            boq[t]['total_volume_m3'] += L_m * 0.5 * 0.8

        elif t == 'WALL':
            L_m = (m.get('length_mm') or 0) / 1000
            H_m = (m.get('height_mm') or 3450) / 1000
            # 두께 기본 300mm
            boq[t]['total_area_m2'] += L_m * H_m

        elif t == 'SLAB':
            a = m.get('area_m2')
            if a:
                boq[t]['total_area_m2'] += a

    # 소수점 정리
    for v in boq.values():
        if 'total_volume_m3' in v:
            v['total_volume_m3'] = round(v['total_volume_m3'], 2)
        if 'total_area_m2' in v:
            v['total_area_m2'] = round(v['total_area_m2'], 2)

    return boq


# ── 검증 ────────────────────────────────────────────────────
def verify(boq: dict, dong_layer_dump: Dict[str, List[str]]) -> None:
    print('\n=== 검증 ===')
    fail = False
    for t, data in boq.items():
        cnt = data['count']
        status = 'OK' if cnt > 0 else 'FAIL'
        print(f'  {t:8s}: {cnt:5d}건  [{status}]')
        if cnt == 0:
            fail = True
            print(f'         !! {t} 0건 — 레이어 확인 필요')
            layers = dong_layer_dump.get(t, [])
            print(f'         후보 레이어: {layers[:5]}')

    if not fail:
        print('  → 전체 PASS')
    else:
        print('  → 일부 FAIL — 위 레이어 덤프 확인 요망')


# ── 메인 ────────────────────────────────────────────────────
def main():
    OUT_DIR.mkdir(exist_ok=True)

    # DONG 분류
    dong_members = classify_dong(DXF_DONG, DONG_FLOORS)

    # PKG 분류
    pkg_members = classify_pkg(DXF_PKG)

    # 합산
    all_members = dong_members + pkg_members

    # 저장
    acc_path = OUT_DIR / 'members_accumulated.json'
    save_accumulated(all_members, acc_path)

    # BOQ
    boq = compute_boq(all_members)
    boq_path = OUT_DIR / 'members_boq.json'
    boq_path.write_text(
        json.dumps(boq, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f'-> {boq_path}')

    # 검증
    # 레이어 덤프 (0건 타입 디버그용)
    layer_dump: Dict[str, List[str]] = {
        'COLUMN': ['XR...$A-COL LWPOLYLINE', '00_COLUMN LWPOLYLINE'],
        'BEAM':   ['S-GIRDER LINE', '00_BEAM LINE'],
        'WALL':   ['XR...$A-WALL-RC LINE', '00_SHEAR WALL LINE'],
        'SLAB':   ['S-PC-SLAB LWPOLYLINE', 'S-SLAB-SYMBOL TEXT'],
        'FND':    ['S-FOUNDATION LINE'],
    }
    verify(boq, layer_dump)

    # 요약 출력
    print('\n=== 최종 부재 타입별 카운트 ===')
    by_type: Dict[str, int] = {}
    by_source_type: Dict[str, Dict[str, int]] = {}
    for m in all_members:
        t = m['type']
        src = m['source']
        by_type[t] = by_type.get(t, 0) + 1
        if src not in by_source_type:
            by_source_type[src] = {}
        by_source_type[src][t] = by_source_type[src].get(t, 0) + 1

    for t, cnt in sorted(by_type.items()):
        print(f'  {t:8s}: {cnt:6d}건')
        for src in ['DONG', 'PKG']:
            scnt = by_source_type.get(src, {}).get(t, 0)
            if scnt:
                print(f'           {src}: {scnt}')

    print(f'\n합계: {len(all_members)}건')
    return boq


if __name__ == '__main__':
    main()
