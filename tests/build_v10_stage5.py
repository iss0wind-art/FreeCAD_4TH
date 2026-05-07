"""
build_v10_stage5.py — Stage 5: 클린 파이프라인 3D 빌드
========================================================
Stage 0~4 산출물 기반으로 FreeCAD 솔리드 생성.
기존 build_v9의 문제(다층 보 혼합, 잡선 포함) 해결.

실행: "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/build_v10_stage5.py
"""
import sys, os, json, math, re
os.chdir('D:/Git/FreeCAD_4TH')
sys.path.insert(0, 'D:/Git/FreeCAD_4TH')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import Part, FreeCAD

from core.pipeline.stage1_structural_filter import filter_structural
from core.pipeline.stage2_member_classifier import classify

# ── Stage 0: 층고 ──────────────────────────────────────────
with open('output/stage0_levels.json', encoding='utf-8') as f:
    levels_data = json.load(f)

SL = {k: v['sl_abs'] for k, v in levels_data['floor_sl'].items()}
FLOOR_H = {
    'B2F': abs(SL['B1F'] - SL['B2F']),   # 3450mm
    'B1F': abs(SL['1F']  - SL['B1F']),   # 5970mm
}
SLAB_T = 150.0

print('=' * 60)
print('Stage 5: 클린 파이프라인 3D 빌드 (v10)')
print('=' * 60)
print(f'B2F SL={SL["B2F"]}mm  층고={FLOOR_H["B2F"]}mm')
print(f'B1F SL={SL["B1F"]}mm  층고={FLOOR_H["B1F"]}mm')

# ── 설정 ───────────────────────────────────────────────────
DXF_DONG  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
DXF_PKG   = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'

CLIPS = {
    'DONG_B2F': (69013,  2241258, 229013, 2401258),
    'DONG_B1F': (195013, 2241258, 355013, 2401258),
    'PKG_B2F':  (552082,  -1376738, 712082,  -1216738),  # 기둥
    'PKG_B1F':  (1182082, -1376738, 1342082, -1216738),  # 보 (B1F 시트에 표현)
}
# PKG 보: 00_SHEAR WALL 레이어 긴 LINE → 보 대용
PKG_BEAM_LAYERS = re.compile(r'00_SHEAR.WALL|00_GIRDER|00_BEAM', re.IGNORECASE)
PKG_BEAM_MIN_L  = 500  # mm 이상만 보로 인정
TX_PKG = -448000.0;  TY_PKG = 3621813.0
PKG_B1F_DX = -630000.0

# ── 유틸 ───────────────────────────────────────────────────

def box(cx, cy, z_bot, w, h, height, label=''):
    """기둥/보 솔리드 (중심 XY 기준)."""
    try:
        s = Part.makeBox(w, h, height,
                         FreeCAD.Vector(cx - w/2, cy - h/2, z_bot))
        return s
    except Exception as e:
        return None

def beam_box(x0, y0, x1, y1, z_bot, bw, bh):
    """보 솔리드 (시작/끝점 기준)."""
    try:
        L = math.hypot(x1-x0, y1-y0)
        if L < 10: return None
        angle = math.degrees(math.atan2(y1-y0, x1-x0))
        s = Part.makeBox(L, bw, bh,
                         FreeCAD.Vector(0, -bw/2, 0))
        m = FreeCAD.Matrix()
        m.rotateZ(math.radians(angle))
        m.move(FreeCAD.Vector(x0, y0, z_bot))
        return s.transformGeometry(m)
    except:
        return None

def cluster_columns(members, tol=500):
    """같은 위치 기둥 중복 제거 (tol mm 이내 = 동일 기둥).
    크기가 가장 큰 것을 대표로 선택."""
    groups = []
    for m in members:
        matched = False
        for g in groups:
            rep = g[0]
            if abs(m.x - rep.x) < tol and abs(m.y - rep.y) < tol:
                g.append(m); matched = True; break
        if not matched:
            groups.append([m])
    result = []
    for g in groups:
        # 면적 가장 큰 것 대표
        best = max(g, key=lambda c: (c.width or 0) * (c.height or 0))
        result.append(best)
    return result

# ── Stage 1+2+3: 각 층 추출 ───────────────────────────────

import re
import ezdxf
from core.dxf_parser.entity_scanner import iter_all

DIM_PAT = re.compile(r'^(\d{3,4})[Xx×](\d{3,4})$')

def attach_dims(cr, dxf_path, clip):
    """Stage 3: 보에 치수 TEXT 매핑."""
    doc = ezdxf.readfile(dxf_path, encoding='cp949')
    xmin,ymin,xmax,ymax = clip
    dim_texts = []
    for e in iter_all(doc.modelspace()):
        if e.dxftype() not in ('TEXT','MTEXT'): continue
        try:
            txt = (e.dxf.text if e.dxftype()=='TEXT' else e.text).strip().replace(' ','')
            pos = e.dxf.insert
            if not (xmin<=pos.x<=xmax and ymin<=pos.y<=ymax): continue
            m = DIM_PAT.match(txt)
            if m:
                dim_texts.append((pos.x, pos.y, int(m.group(1)), int(m.group(2))))
        except: pass
    for beam in cr.beams:
        best_d = 9e9
        for tx, ty, w, h in dim_texts:
            d = math.hypot(tx-beam.x, ty-beam.y)
            if d < best_d:
                best_d, beam.width, beam.height = d, w, h
    return cr

data = {}
for key, clip in CLIPS.items():
    dxf = DXF_DONG if key.startswith('DONG') else DXF_PKG
    fr = filter_structural(dxf, clip=clip)
    cr = classify(fr, floor=key)
    cr = attach_dims(cr, dxf, clip)
    data[key] = cr
    cols_clean = cluster_columns(cr.columns)
    print(f'  {key}: 기둥={len(cols_clean)}(중복제거전:{len(cr.columns)}) 보={len(cr.beams)}')
    cr._columns_clean = cols_clean

# ── 좌표 변환 함수 ─────────────────────────────────────────

def tx_dong_b1(x, y):
    return x - 126000.0, y  # S30-002 → S30-001 좌표계

def tx_pkg_b2(x, y):
    return x + TX_PKG, y + TY_PKG

def tx_pkg_b1(x, y):
    return x + PKG_B1F_DX + TX_PKG, y + TY_PKG

# ── FreeCAD 문서 ───────────────────────────────────────────

doc_fc = FreeCAD.newDocument('v10_stage5')
shapes = []
stats = {'col': 0, 'beam': 0}

DEFAULT_COL_W = 600.0
DEFAULT_COL_H = 600.0
DEFAULT_BEAM_W = 500.0
DEFAULT_BEAM_H = 600.0

def add_columns(cr_cols, z_bot, floor_h, tfm=None):
    for c in cr_cols:
        cx, cy = (tfm(c.x, c.y) if tfm else (c.x, c.y))
        w = c.width  or DEFAULT_COL_W
        h = c.height or DEFAULT_COL_H
        s = box(cx, cy, z_bot, w, h, floor_h)
        if s:
            shapes.append(s)
            stats['col'] += 1

def add_beams(cr_beams, z_slab_top, beam_h_default, tfm=None):
    """보는 슬라브 상면(z_slab_top) 아래에 매달림.
    z_bot = z_slab_top - beam_height"""
    for b in cr_beams:
        if not b.coords or len(b.coords) < 2: continue
        x0, y0 = b.coords[0]
        x1, y1 = b.coords[1]
        if tfm:
            x0, y0 = tfm(x0, y0)
            x1, y1 = tfm(x1, y1)
        bw = b.width  or DEFAULT_BEAM_W
        bh = b.height or beam_h_default
        z_bot = z_slab_top - bh   # 보 하단 = 슬라브 상면 - 보 높이
        s = beam_box(x0, y0, x1, y1, z_bot, bw, bh)
        if s:
            shapes.append(s)
            stats['beam'] += 1

# ── DONG B2F ───────────────────────────────────────────────
print('\n[1] DONG B2F ...')
z_b2f = SL['B2F']   # 기둥 하단
z_b1f = SL['B1F']   # B2F 보의 슬라브 상면 = B1F 바닥
add_columns(data['DONG_B2F']._columns_clean, z_b2f, FLOOR_H['B2F'])
add_beams(data['DONG_B2F'].beams, z_b1f, DEFAULT_BEAM_H)   # 보 상단=B1F SL

# ── DONG B1F ───────────────────────────────────────────────
print('[2] DONG B1F ...')
z_1f = SL['1F']   # B1F 보의 슬라브 상면 = 1F 바닥
add_columns(data['DONG_B1F']._columns_clean, z_b1f, FLOOR_H['B1F'], tfm=tx_dong_b1)
add_beams(data['DONG_B1F'].beams, z_1f, DEFAULT_BEAM_H, tfm=tx_dong_b1)

# ── PKG B2F 기둥 + B1F 시트에서 보 추출 ────────────────────
print('[3] PKG B2F 기둥 + B1F 보 ...')
add_columns(data['PKG_B2F']._columns_clean, z_b2f, FLOOR_H['B2F'], tfm=tx_pkg_b2)
# PKG 보: B1F 시트에 표현됨 → B1F 오프셋(-630000) 역변환 후 B2F 좌표계로
def tx_pkg_b1_to_b2(x, y):
    return x + PKG_B1F_DX + TX_PKG, y + TY_PKG   # B1F→B2F(-630000) + PKG→DONG
add_beams(data['PKG_B1F'].beams, z_b1f, DEFAULT_BEAM_H, tfm=tx_pkg_b1_to_b2)

# ── FreeCAD 등록 + STEP 출력 ───────────────────────────────
print(f'\n[4] FreeCAD 등록 ...')
print(f'  기둥: {stats["col"]}개  보: {stats["beam"]}개  합: {len(shapes)}개')

compound = Part.makeCompound(shapes)
obj = doc_fc.addObject('Part::Feature', 'v10_stage5')
obj.Shape = compound
doc_fc.recompute()

STEP = 'output/v10_stage5.step'
Part.export([obj], STEP)
sz = os.path.getsize(STEP) // 1024
print(f'  [STEP] {STEP}  ({sz} KB)')

# ── 요약 ───────────────────────────────────────────────────
print('\n' + '=' * 60)
print('v10 Stage5 빌드 완료')
print('=' * 60)
print(f'  기둥: {stats["col"]:5d}개')
print(f'  보:   {stats["beam"]:5d}개')
print(f'  합계: {len(shapes):5d}개')
