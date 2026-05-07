"""
build_v12_north_ext.py — 북쪽 주차장 확장 영역 추가
======================================================
v11 문제 수정:
  - 기존: PKG_B2F 클립이 DONG과 78% X / 98% Y 겹침 → 중복 기둥 밀집
  - 수정: PKG 북쪽 전용 클립(world Y > 2401m) 사용 → 타워+주차장 분리

구조:
  DONG B2F (Y 2241m~2401m) : 101동 타워 지하2층
  PKG  B2F (Y 2401m~2613m) : 101동 북쪽 주차장 지하2층  ← 새로 추가
  DONG B1F (Y 2241m~2401m) : 101동 타워 지하1층
  PKG  B1F (Y 2401m~2613m) : 101동 북쪽 주차장 지하1층  ← 새로 추가

실행: "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/build_v12_north_ext.py
"""
import sys, os, json, math, re
os.chdir('D:/Git/FreeCAD_4TH')
sys.path.insert(0, 'D:/Git/FreeCAD_4TH')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import Part, FreeCAD, ezdxf
from core.dxf_parser.entity_scanner import iter_all
from core.pipeline.stage1_structural_filter import filter_structural
from core.pipeline.stage2_member_classifier import classify

# ── Stage 0: 층고 ──────────────────────────────────────────
with open('output/stage0_levels.json', encoding='utf-8') as f:
    lv = json.load(f)
SL     = {k: v['sl_abs'] for k, v in lv['floor_sl'].items()}

print('=' * 60)
print('v12 북쪽 주차장 확장 빌드')
print('=' * 60)

# ── DXF 경로 ──────────────────────────────────────────────
DXF_DONG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
DXF_PKG  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'

TX_PKG = -448000.0;  TY_PKG = 3621813.0
DONG_B1F_DX = -126000.0
PKG_B1F_DX  = -630000.0

# ── 클립 정의 ─────────────────────────────────────────────
CLIPS = {
    # 타워 (DONG DXF 기준)
    'DONG_B2F': (69013,  2241258, 229013, 2401258),
    'DONG_B1F': (195013, 2241258, 355013, 2401258),

    # 북쪽 주차장: world Y 2401m~2613m → PKG_Y -1221k~-1009k
    # X: PKG 전체 범위 490k~720k → world X 42k~272k
    'PKG_B2F_NORTH': (490000, -1221000, 720000, -1009000),
    'PKG_B1F_NORTH': (490000 + 630000, -1221000, 720000 + 630000, -1009000),
}

TRANSFORMS = {
    'DONG_B2F':      lambda x, y: (x, y),
    'DONG_B1F':      lambda x, y: (x + DONG_B1F_DX, y),
    'PKG_B2F_NORTH': lambda x, y: (x + TX_PKG, y + TY_PKG),
    'PKG_B1F_NORTH': lambda x, y: (x + PKG_B1F_DX + TX_PKG, y + TY_PKG),
}

BEAM_SPAN_MIN = 500
BEAM_SPAN_MAX = 14000
DEFAULT_BEAM_W = 500
DEFAULT_BEAM_H = 600

DIM_PAT = re.compile(r'^(\d{3,4})[Xx](\d{3,4})$')

# ── 유틸 ──────────────────────────────────────────────────

def make_col_box(cx, cy, w, h, z_bot, z_top):
    try:
        return Part.makeBox(w, h, z_top - z_bot,
                            FreeCAD.Vector(cx - w/2, cy - h/2, z_bot))
    except:
        return None


def make_beam(x0, y0, x1, y1, z_bot, bw, bh):
    try:
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 10: return None
        angle = math.degrees(math.atan2(y1 - y0, x1 - x0))
        s = Part.makeBox(L, bw, bh, FreeCAD.Vector(0, -bw/2, 0))
        m = FreeCAD.Matrix()
        m.rotateZ(math.radians(angle))
        m.move(FreeCAD.Vector(x0, y0, z_bot))
        return s.transformGeometry(m)
    except:
        return None


def get_dim_text(dxf_path, clip):
    doc = ezdxf.readfile(dxf_path, encoding='cp949')
    xmin, ymin, xmax, ymax = clip
    dims = []
    for e in iter_all(doc.modelspace()):
        if e.dxftype() not in ('TEXT', 'MTEXT'): continue
        try:
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip().replace(' ', '')
            pos = e.dxf.insert
            if not (xmin <= pos.x <= xmax and ymin <= pos.y <= ymax): continue
            m = DIM_PAT.match(txt)
            if m:
                dims.append((pos.x, pos.y, int(m.group(1)), int(m.group(2))))
        except:
            pass
    return dims


def nearest_dim(cx, cy, dims, radius=5000):
    best_d, best = 9e9, None
    for tx, ty, w, h in dims:
        d = math.hypot(tx - cx, ty - cy)
        if d < best_d:
            best_d, best = d, (w, h)
    return best if best_d <= radius else None


# ── 기둥 추출 ─────────────────────────────────────────────

def extract_columns(key):
    clip = CLIPS[key]
    dxf  = DXF_DONG if key.startswith('DONG') else DXF_PKG
    tfm  = TRANSFORMS[key]

    fr = filter_structural(dxf, clip=clip)
    cr = classify(fr, floor=key)

    cols = []
    for c in cr.columns:
        if c.etype != 'LWPOLYLINE': continue
        w = c.width  or DEFAULT_BEAM_W
        h = c.height or DEFAULT_BEAM_H
        if w < 100 or h < 100: continue
        rx, ry = tfm(c.x, c.y)
        cols.append({'x': rx, 'y': ry, 'w': w, 'h': h, 'src': key})
    return cols


# ── 보 스냅 ──────────────────────────────────────────────

def snap_beams_to_cols(dxf_path, clip, cols_world, dims, z_slab_top,
                        tfm=None, snap_r=2000, use_shear_wall=False):
    pat = r'S-GIRDER|S-BEAM|S-PC-GIRDER|00_BEAM|00_\(APT\)BEAM'
    if use_shear_wall:
        pat += r'|00_SHEAR.WALL'
    BEAM_LAYERS = re.compile(pat, re.IGNORECASE)

    doc  = ezdxf.readfile(dxf_path, encoding='cp949')
    xmin, ymin, xmax, ymax = clip

    def nearest_col(wx, wy):
        best_d, best = 9e9, None
        for c in cols_world:
            d = math.hypot(c['x'] - wx, c['y'] - wy)
            if d < best_d:
                best_d, best = d, c
        return best, best_d

    beams = []
    for e in iter_all(doc.modelspace()):
        if e.dxftype() != 'LINE': continue
        if not BEAM_LAYERS.search(getattr(e.dxf, 'layer', '')): continue
        try:
            sx, sy = e.dxf.start.x, e.dxf.start.y
            ex, ey = e.dxf.end.x,   e.dxf.end.y
            cx, cy = (sx + ex) / 2, (sy + ey) / 2
            if not (xmin <= cx <= xmax and ymin <= cy <= ymax): continue
            L = math.hypot(ex - sx, ey - sy)
            if L < BEAM_SPAN_MIN: continue

            if tfm:
                wsx, wsy = tfm(sx, sy)
                wex, wey = tfm(ex, ey)
            else:
                wsx, wsy, wex, wey = sx, sy, ex, ey

            col_s, ds = nearest_col(wsx, wsy)
            col_e, de = nearest_col(wex, wey)

            if ds > snap_r or de > snap_r: continue
            if col_s is col_e: continue

            wcx = (col_s['x'] + col_e['x']) / 2
            wcy = (col_s['y'] + col_e['y']) / 2
            dim = nearest_dim(wcx, wcy, dims)
            bw = dim[0] if dim else DEFAULT_BEAM_W
            bh = dim[1] if dim else DEFAULT_BEAM_H
            z_bot = z_slab_top - bh

            beams.append((col_s['x'], col_s['y'],
                          col_e['x'], col_e['y'],
                          z_bot, bw, bh))
        except:
            pass

    seen = set()
    unique = []
    for b in beams:
        key = (round(b[0]/100), round(b[1]/100),
               round(b[2]/100), round(b[3]/100))
        key = tuple(sorted([key[:2], key[2:]]))
        if key not in seen:
            seen.add(key)
            unique.append(b)
    return unique


# ── 메인 빌드 ─────────────────────────────────────────────

shapes = []
stats  = {'col': 0, 'beam': 0}

print('\n[1] 기둥 추출...')
cols_dong_b2f = extract_columns('DONG_B2F')
cols_dong_b1f = extract_columns('DONG_B1F')
cols_pkg_b2f  = extract_columns('PKG_B2F_NORTH')
cols_pkg_b1f  = extract_columns('PKG_B1F_NORTH')

print(f'  DONG B2F 타워:    {len(cols_dong_b2f):3d}개  world X {min(c["x"] for c in cols_dong_b2f):.0f}~{max(c["x"] for c in cols_dong_b2f):.0f}  Y {min(c["y"] for c in cols_dong_b2f):.0f}~{max(c["y"] for c in cols_dong_b2f):.0f}' if cols_dong_b2f else '  DONG B2F 타워:    0개')
print(f'  PKG  B2F 북쪽주차장:{len(cols_pkg_b2f):3d}개  world X {min(c["x"] for c in cols_pkg_b2f):.0f}~{max(c["x"] for c in cols_pkg_b2f):.0f}  Y {min(c["y"] for c in cols_pkg_b2f):.0f}~{max(c["y"] for c in cols_pkg_b2f):.0f}' if cols_pkg_b2f else '  PKG  B2F 북쪽:    0개')
print(f'  DONG B1F 타워:    {len(cols_dong_b1f):3d}개')
print(f'  PKG  B1F 북쪽주차장:{len(cols_pkg_b1f):3d}개' if cols_pkg_b1f else '  PKG  B1F 북쪽:    0개')

print('\n[2] 치수 TEXT 수집...')
dims_dong_b2f = get_dim_text(DXF_DONG, CLIPS['DONG_B2F'])
dims_dong_b1f = get_dim_text(DXF_DONG, CLIPS['DONG_B1F'])
dims_pkg_b2f  = get_dim_text(DXF_PKG,  CLIPS['PKG_B2F_NORTH'])
print(f'  DONG B2F: {len(dims_dong_b2f)}개  DONG B1F: {len(dims_dong_b1f)}개  PKG 북쪽: {len(dims_pkg_b2f)}개')

# ── B2F 기둥 솔리드 ───────────────────────────────────────
print('\n[3] B2F 기둥 솔리드...')
z_b2f = SL['B2F']
z_b1f = SL['B1F']

all_b2f_cols = cols_dong_b2f + cols_pkg_b2f
for c in all_b2f_cols:
    s = make_col_box(c['x'], c['y'], c['w'], c['h'], z_b2f, z_b1f)
    if s:
        shapes.append(s); stats['col'] += 1
print(f'  B2F 기둥 {stats["col"]}개 (타워{len(cols_dong_b2f)}+주차장{len(cols_pkg_b2f)})')

# ── B2F 보 ────────────────────────────────────────────────
print('\n[4] B2F 보...')
dims_b2f_all = dims_dong_b2f + dims_pkg_b2f

beams_dong_b2f = snap_beams_to_cols(
    DXF_DONG, CLIPS['DONG_B2F'], all_b2f_cols, dims_b2f_all, z_b1f,
    tfm=TRANSFORMS['DONG_B2F'])
beams_pkg_north_b2f = snap_beams_to_cols(
    DXF_PKG, CLIPS['PKG_B2F_NORTH'], all_b2f_cols, dims_b2f_all, z_b1f,
    tfm=TRANSFORMS['PKG_B2F_NORTH'], use_shear_wall=True)

beam_b2f_start = stats['beam']
for x0, y0, x1, y1, z_bot, bw, bh in beams_dong_b2f + beams_pkg_north_b2f:
    s = make_beam(x0, y0, x1, y1, z_bot, bw, bh)
    if s:
        shapes.append(s); stats['beam'] += 1
print(f'  DONG보={len(beams_dong_b2f)} PKG북쪽보={len(beams_pkg_north_b2f)} 생성={stats["beam"]-beam_b2f_start}')

# ── B1F 기둥 솔리드 ───────────────────────────────────────
print('\n[5] B1F 기둥 솔리드...')
z_1f = SL['1F']
all_b1f_cols = cols_dong_b1f + cols_pkg_b1f
col_b1f_start = stats['col']
for c in all_b1f_cols:
    s = make_col_box(c['x'], c['y'], c['w'], c['h'], z_b1f, z_1f)
    if s:
        shapes.append(s); stats['col'] += 1
print(f'  B1F 기둥 {stats["col"]-col_b1f_start}개 (타워{len(cols_dong_b1f)}+주차장{len(cols_pkg_b1f)})')

# ── B1F 보 ────────────────────────────────────────────────
print('\n[6] B1F 보...')
dims_b1f_all = dims_dong_b1f + dims_pkg_b2f  # PKG B1F 치수 텍스트도 B2F 클립 재활용

beams_dong_b1f = snap_beams_to_cols(
    DXF_DONG, CLIPS['DONG_B1F'], all_b1f_cols, dims_b1f_all, z_1f,
    tfm=TRANSFORMS['DONG_B1F'])
beams_pkg_north_b1f = snap_beams_to_cols(
    DXF_PKG, CLIPS['PKG_B1F_NORTH'], all_b1f_cols, dims_b1f_all, z_1f,
    tfm=TRANSFORMS['PKG_B1F_NORTH'], use_shear_wall=True)

beam_b1f_start = stats['beam']
for x0, y0, x1, y1, z_bot, bw, bh in beams_dong_b1f + beams_pkg_north_b1f:
    s = make_beam(x0, y0, x1, y1, z_bot, bw, bh)
    if s:
        shapes.append(s); stats['beam'] += 1
print(f'  DONG보={len(beams_dong_b1f)} PKG북쪽보={len(beams_pkg_north_b1f)} 생성={stats["beam"]-beam_b1f_start}')

# ── STEP 출력 ──────────────────────────────────────────────
print('\n[7] STEP 출력...')
doc_fc = FreeCAD.newDocument('v12')
compound = Part.makeCompound(shapes)
obj = doc_fc.addObject('Part::Feature', 'v12_north_ext')
obj.Shape = compound
doc_fc.recompute()
STEP = 'output/v12_north_ext.step'
Part.export([obj], STEP)
sz = os.path.getsize(STEP) // 1024

print('\n' + '=' * 60)
print('v12 완료')
print('=' * 60)
print(f'  B2F 기둥:  타워 {len(cols_dong_b2f)}개  + 주차장 {len(cols_pkg_b2f)}개')
print(f'  B1F 기둥:  타워 {len(cols_dong_b1f)}개  + 주차장 {len(cols_pkg_b1f)}개')
print(f'  기둥합계: {stats["col"]:5d}개')
print(f'  보  합계: {stats["beam"]:5d}개')
print(f'  총  합계: {len(shapes):5d}개')
print(f'  STEP: {STEP} ({sz} KB)')
