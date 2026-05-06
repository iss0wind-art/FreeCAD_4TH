"""
poc_v4_build_3d.py — v4 3D 빌드 (FreeCAD STEP 생성)
=====================================================
v3 결함 수정:
  1. 좌표 통일: PKG 기둥을 S30 좌표계로 변환 (-448000, +3622000)
  2. 슬라브 형태: 기둥 convex hull (BBox 탈피)
  3. 도면 직독값: B2F=-9050, B1F=-5600, 1F=+370 (추정 없음)

입력: output/poc_v3_101.json (파싱 결과)
출력: output/poc_v4_101.step

실행: freecadcmd -c tests/poc_v4_build_3d.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ─────────────────────────────────────────────────────────────
# 확정 치수 (도면 직독, 추정 없음)
# ─────────────────────────────────────────────────────────────

SL = {'B2F': -9050.0, 'B1F': -5600.0, '1F': 370.0}
SLAB_T = 150.0   # S40-051~057 150mm
GIRDER_H = 900.0  # codex_beams_basement.json 전체 900mm

# probe_coord_align.py 결과: PKG→S30 오프셋
PKG_TX = -448000.0
PKG_TY = 3622000.0

META_V3 = "output/poc_v3_101.json"
OUT_STEP = "output/poc_v4_101.step"
OUT = "output"


def load_v3_meta() -> list[dict]:
    if not os.path.exists(META_V3):
        raise FileNotFoundError(f'{META_V3} 없음. poc_v3_101_integrated.py 먼저 실행')
    with open(META_V3, encoding='utf-8') as f:
        d = json.load(f)
    return d['sheets']


def unify_col(cx: float, cy: float, is_pkg: bool) -> tuple[float, float]:
    """PKG 좌표 → S30 좌표계 변환."""
    if is_pkg:
        return cx + PKG_TX, cy + PKG_TY
    return cx, cy


def convex_hull_box(pts: list) -> list:
    """기둥 중심점 convex hull. scipy 없으면 BBox 사용."""
    if not pts:
        return []
    try:
        import numpy as np
        from scipy.spatial import ConvexHull
        arr = np.array(pts)
        if len(arr) < 4:
            raise ValueError
        hull = ConvexHull(arr)
        return [pts[i] for i in hull.vertices]
    except Exception:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        m = 2000  # margin
        return [
            (min(xs)-m, min(ys)-m),
            (max(xs)+m, min(ys)-m),
            (max(xs)+m, max(ys)+m),
            (min(xs)-m, max(ys)+m),
        ]


def make_box_solid(Part, cx, cy, z_bot, z_top, w, h):
    height = z_top - z_bot
    if height <= 0 or w <= 0 or h <= 0:
        return None
    b = Part.makeBox(w, h, height, Part.Vector(cx-w/2, cy-h/2, z_bot))
    return b if b.isValid() else None


def make_slab(Part, hull_pts, z_bot, z_top):
    """LWPOLYLINE → 슬라브 프리즘. 실패 시 BBox 박스로 폴백."""
    import FreeCAD
    height = z_top - z_bot
    if height <= 0:
        return None
    try:
        verts = [FreeCAD.Vector(x, y, z_bot) for x, y in hull_pts]
        verts.append(verts[0])
        wire = Part.makePolygon(verts)
        face = Part.makeFace(wire, 'Part::FaceMakerBullseye')
        solid = face.extrude(FreeCAD.Vector(0, 0, height))
        if solid.isValid():
            return solid
    except Exception:
        pass
    # 폴백: BBox
    xs = [p[0] for p in hull_pts]
    ys = [p[1] for p in hull_pts]
    return make_box_solid(Part,
        (min(xs)+max(xs))/2, (min(ys)+max(ys))/2,
        z_bot, z_top,
        max(xs)-min(xs), max(ys)-min(ys))


def build_sheet(Part, sheet: dict) -> list[tuple[str, object]]:
    """시트 데이터 → 솔리드 목록."""
    floor_key = sheet['floor_key']  # 'B2F' or 'B1F'
    is_pkg = sheet['sheet_id'].startswith('PKG')

    z_floor_bot = SL[floor_key]
    z_floor_top = SL['B1F'] if floor_key == 'B2F' else SL['1F']
    z_slab_bot = z_floor_top - SLAB_T
    z_slab_top = z_floor_top
    z_col_bot = z_floor_bot
    z_col_top = z_slab_bot
    z_girder_bot = z_floor_top - GIRDER_H
    z_girder_top = z_slab_bot

    solids = []
    col_pts = []

    # 기둥 통일 좌표 수집
    unified_cols = []
    for c in sheet.get('columns', []):
        raw_cx = c.get('abs_cx', c.get('cx', 0))
        raw_cy = c.get('abs_cy', c.get('cy', 0))
        ux, uy = unify_col(raw_cx, raw_cy, is_pkg)
        w = c.get('w', 500)
        h = c.get('h', 500)
        unified_cols.append((ux, uy, w, h))
        col_pts.append((ux, uy))

    # 1. 슬라브 (convex hull)
    if len(col_pts) >= 3:
        hull = convex_hull_box(col_pts)
        if hull:
            slab = make_slab(Part, hull, z_slab_bot, z_slab_top)
            if slab:
                solids.append(('slab', slab))

    # 2. 기둥
    col_ok = 0
    for ux, uy, w, h in unified_cols:
        box = make_box_solid(Part, ux, uy, z_col_bot, z_col_top, w, h)
        if box:
            solids.append(('column', box))
            col_ok += 1

    # 3. 보
    for g in sheet.get('girders', []):
        try:
            x0, y0 = unify_col(g['abs_x0'], g['abs_y0'], is_pkg)
            x1, y1 = unify_col(g['abs_x1'], g['abs_y1'], is_pkg)
            gw = g.get('width', 300)
            import math, FreeCAD
            dx, dy = x1-x0, y1-y0
            ln = math.hypot(dx, dy)
            if ln < 100:
                continue
            ux, uy = -dy/ln, dx/ln  # 수직 벡터
            verts = [
                FreeCAD.Vector(x0+ux*gw/2, y0+uy*gw/2, z_girder_bot),
                FreeCAD.Vector(x1+ux*gw/2, y1+uy*gw/2, z_girder_bot),
                FreeCAD.Vector(x1-ux*gw/2, y1-uy*gw/2, z_girder_bot),
                FreeCAD.Vector(x0-ux*gw/2, y0-uy*gw/2, z_girder_bot),
                FreeCAD.Vector(x0+ux*gw/2, y0+uy*gw/2, z_girder_bot),
            ]
            wire = Part.makePolygon(verts)
            face = Part.makeFace(wire, 'Part::FaceMakerBullseye')
            solid = face.extrude(FreeCAD.Vector(0, 0, GIRDER_H))
            if solid.isValid():
                solids.append(('girder', solid))
        except Exception:
            pass

    print(f'  {sheet["sheet_id"]} {floor_key} pkg={is_pkg}: '
          f'slab={sum(1 for k,_ in solids if k=="slab")} '
          f'col={col_ok}/{len(unified_cols)} '
          f'girder={sum(1 for k,_ in solids if k=="girder")}')
    return solids


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)

    try:
        import Part
        import FreeCAD
    except ImportError:
        print('[ERR] FreeCAD 없음 — freecadcmd 사용')
        return

    print('[로드] v3 메타 JSON...')
    sheets = load_v3_meta()
    print(f'  {len(sheets)}개 시트: {[s["sheet_id"] for s in sheets]}')

    all_solids = []
    for sheet in sheets:
        solids = build_sheet(Part, sheet)
        all_solids.extend(solids)

    print(f'\n[STEP] 총 {len(all_solids)}개 솔리드 → {OUT_STEP}')
    shapes = [s for _, s in all_solids]
    compound = Part.makeCompound(shapes)
    Part.export([compound], OUT_STEP)

    vol = compound.Volume / 1e9
    elapsed = time.time() - t0
    print(f'[완료] {len(all_solids)} 솔리드, {vol:.0f} m³, {elapsed:.1f}s')

    # 유형별 집계
    by_type: dict[str, int] = {}
    for kind, _ in all_solids:
        by_type[kind] = by_type.get(kind, 0) + 1
    for kind, cnt in sorted(by_type.items()):
        print(f'  {kind}: {cnt}개')

    # 검증 게이트
    print('\n[검증]')
    g1 = compound.isValid()
    g2 = vol > 0
    g3 = by_type.get('column', 0) >= 100
    g4 = by_type.get('slab', 0) >= 2  # B2F + B1F
    gates = [('G1 compound isValid', g1), ('G2 부피 > 0', g2),
             ('G3 기둥 100개+', g3), ('G4 슬라브 2개+', g4)]
    for name, ok in gates:
        print(f'  {"PASS" if ok else "FAIL"} {name}')
    pass_n = sum(1 for _, ok in gates if ok)
    print(f'  결과: {pass_n}/{len(gates)}')


if __name__ == '__main__':
    main()
