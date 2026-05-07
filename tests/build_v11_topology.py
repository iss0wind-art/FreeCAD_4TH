"""
build_v11_topology.py — 기둥 중심 기반 토폴로지 빌드
=====================================================
DXF 잡선 대신 확정된 기둥 위치를 씨앗으로:
  1. 기둥 중심점 추출 (LWPOLYLINE bbox 중심)
  2. 인접 기둥 쌍 탐색 (거리 + 방향 필터)
  3. 기둥 중심 → 기둥 중심 보 연결
  4. 보 단면: DXF TEXT 치수 매핑

실행: "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/build_v11_topology.py
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
SLAB_T = 150.0

print('=' * 60)
print('v11 토폴로지 빌드')
print('=' * 60)

# ── 설정 ───────────────────────────────────────────────────
DXF_DONG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
DXF_PKG  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'

TX_PKG = -448000.0;  TY_PKG = 3621813.0
DONG_B1F_DX = -126000.0
PKG_B1F_DX  = -630000.0

CLIPS = {
    'DONG_B2F': (69013,  2241258, 229013, 2401258),
    'DONG_B1F': (195013, 2241258, 355013, 2401258),
    'PKG_B2F':  (552082,  -1376738, 712082,  -1216738),
    'PKG_B1F':  (1182082, -1376738, 1342082, -1216738),
}

TRANSFORMS = {
    'DONG_B2F': lambda x,y: (x, y),
    'DONG_B1F': lambda x,y: (x + DONG_B1F_DX, y),
    'PKG_B2F':  lambda x,y: (x + TX_PKG, y + TY_PKG),
    'PKG_B1F':  lambda x,y: (x + PKG_B1F_DX + TX_PKG, y + TY_PKG),
}

# 보 스팬 한계: 최소 500mm, 최대 14000mm
BEAM_SPAN_MIN = 500
BEAM_SPAN_MAX = 14000

# 건물 주축 방향 (°): 0, 90, ~14, ~104
MAIN_AXES = [0, 14, 90, 104, 180]
AXIS_TOL  = 15   # ±15° 허용

# 기본 보 단면
DEFAULT_BEAM_W = 500
DEFAULT_BEAM_H = 600


# ── 유틸 함수 ──────────────────────────────────────────────

def angle_ok(dx, dy):
    """두 점 사이 방향이 주축 ±AXIS_TOL 이내인지."""
    a = math.degrees(math.atan2(dy, dx)) % 180
    for ax in MAIN_AXES:
        if abs(a - ax) <= AXIS_TOL or abs(a - ax - 180) <= AXIS_TOL:
            return True
    return False


def get_dim_text(dxf_path, clip):
    """DXF에서 치수 TEXT(NNNxNNN) 수집."""
    DIM_PAT = re.compile(r'^(\d{3,4})[Xx](\d{3,4})$')
    doc = ezdxf.readfile(dxf_path, encoding='cp949')
    xmin,ymin,xmax,ymax = clip
    dims = []
    for e in iter_all(doc.modelspace()):
        if e.dxftype() not in ('TEXT','MTEXT'): continue
        try:
            txt = (e.dxf.text if e.dxftype()=='TEXT' else e.text).strip().replace(' ','')
            pos = e.dxf.insert
            if not (xmin<=pos.x<=xmax and ymin<=pos.y<=ymax): continue
            m = DIM_PAT.match(txt)
            if m:
                dims.append((pos.x, pos.y, int(m.group(1)), int(m.group(2))))
        except: pass
    return dims


def nearest_dim(cx, cy, dims, radius=5000):
    """가장 가까운 치수 TEXT 반환."""
    best_d, best = 9e9, None
    for tx, ty, w, h in dims:
        d = math.hypot(tx-cx, ty-cy)
        if d < best_d:
            best_d, best = d, (w, h)
    return best if best_d <= radius else None


def make_col_box(cx, cy, w, h, z_bot, z_top):
    try:
        return Part.makeBox(w, h, z_top-z_bot,
                            FreeCAD.Vector(cx-w/2, cy-h/2, z_bot))
    except: return None


def make_beam(x0, y0, x1, y1, z_bot, bw, bh):
    try:
        L = math.hypot(x1-x0, y1-y0)
        if L < 10: return None
        angle = math.degrees(math.atan2(y1-y0, x1-x0))
        s = Part.makeBox(L, bw, bh, FreeCAD.Vector(0, -bw/2, 0))
        m = FreeCAD.Matrix()
        m.rotateZ(math.radians(angle))
        m.move(FreeCAD.Vector(x0, y0, z_bot))
        return s.transformGeometry(m)
    except: return None


# ── 기둥 추출 ──────────────────────────────────────────────

def extract_columns(key):
    """기둥 중심점 + 단면 크기 반환."""
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


# ── 핵심: DXF 보 선 → 기둥 중심 스냅 ────────────────────

def snap_beams_to_cols(dxf_path, clip, cols_world, dims, z_slab_top,
                        tfm=None, snap_r=2000):
    """
    DXF 보 레이어 LINE을 읽어 양 끝점을 가장 가까운 기둥 중심에 스냅.
    DXF가 'where' 알려주고, 기둥이 'exact coord' 알려줌.
    """
    BEAM_LAYERS = re.compile(
        r'S-GIRDER|S-BEAM|S-PC-GIRDER|00_BEAM|00_\(APT\)BEAM', re.IGNORECASE)

    doc  = ezdxf.readfile(dxf_path, encoding='cp949')
    xmin,ymin,xmax,ymax = clip

    def nearest_col(wx, wy):
        best_d, best = 9e9, None
        for c in cols_world:
            d = math.hypot(c['x']-wx, c['y']-wy)
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
            cx, cy = (sx+ex)/2, (sy+ey)/2
            if not (xmin<=cx<=xmax and ymin<=cy<=ymax): continue
            L = math.hypot(ex-sx, ey-sy)
            if L < BEAM_SPAN_MIN: continue

            # 월드 좌표로 변환
            if tfm:
                wsx, wsy = tfm(sx, sy)
                wex, wey = tfm(ex, ey)
            else:
                wsx, wsy, wex, wey = sx, sy, ex, ey

            # 양 끝점을 가장 가까운 기둥 중심에 스냅
            col_s, ds = nearest_col(wsx, wsy)
            col_e, de = nearest_col(wex, wey)

            # 스냅 성공 + 서로 다른 기둥이어야 보
            if ds > snap_r or de > snap_r: continue
            if col_s is col_e: continue

            # 치수
            wcx, wcy = (col_s['x']+col_e['x'])/2, (col_s['y']+col_e['y'])/2
            dim = nearest_dim(wcx, wcy, dims)
            bw = dim[0] if dim else DEFAULT_BEAM_W
            bh = dim[1] if dim else DEFAULT_BEAM_H
            z_bot = z_slab_top - bh

            beams.append((col_s['x'], col_s['y'],
                          col_e['x'], col_e['y'],
                          z_bot, bw, bh))
        except: pass

    # 중복 제거
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


# ── 메인 빌드 ──────────────────────────────────────────────

shapes = []
stats  = {'col': 0, 'beam': 0}

# 층별 기둥 수집
print('\n[1] 기둥 추출...')
cols_b2f_dong = extract_columns('DONG_B2F')
cols_b1f_dong = extract_columns('DONG_B1F')
cols_b2f_pkg  = extract_columns('PKG_B2F')
print(f'  DONG B2F: {len(cols_b2f_dong)}개')
print(f'  DONG B1F: {len(cols_b1f_dong)}개')
print(f'  PKG  B2F: {len(cols_b2f_pkg)}개')

# 층별 치수 TEXT
print('\n[2] 치수 TEXT 수집...')
dims_dong_b2f = get_dim_text(DXF_DONG, CLIPS['DONG_B2F'])
dims_pkg_b1f  = get_dim_text(DXF_PKG,  CLIPS['PKG_B1F'])
print(f'  DONG B2F 치수: {len(dims_dong_b2f)}개')
print(f'  PKG  B1F 치수: {len(dims_pkg_b1f)}개')

# ── B2F 빌드 ───────────────────────────────────────────────
print('\n[3] B2F 기둥 솔리드...')
z_b2f_bot = SL['B2F']
z_b2f_top = SL['B1F']

for c in cols_b2f_dong + cols_b2f_pkg:
    s = make_col_box(c['x'], c['y'], c['w'], c['h'], z_b2f_bot, z_b2f_top)
    if s:
        shapes.append(s)
        stats['col'] += 1

print(f'  기둥 {stats["col"]}개')

print('\n[4] B2F 보 (DXF스냅)...')
all_b2f_cols = cols_b2f_dong + cols_b2f_pkg
dims_b2f = dims_dong_b2f[:]

# DONG B2F 보
beams_dong = snap_beams_to_cols(
    DXF_DONG, CLIPS['DONG_B2F'], all_b2f_cols, dims_b2f, z_b2f_top,
    tfm=TRANSFORMS['DONG_B2F'])
# PKG B1F 시트 보 (B2F 보가 B1F 시트에 표현)
beams_pkg = snap_beams_to_cols(
    DXF_PKG, CLIPS['PKG_B1F'], all_b2f_cols, dims_b2f, z_b2f_top,
    tfm=TRANSFORMS['PKG_B1F'])

for x0,y0,x1,y1,z_bot,bw,bh in beams_dong + beams_pkg:
    s = make_beam(x0, y0, x1, y1, z_bot, bw, bh)
    if s:
        shapes.append(s)
        stats['beam'] += 1
print(f'  DONG보={len(beams_dong)} PKG보={len(beams_pkg)} 생성={stats["beam"]}')

# ── B1F 빌드 ───────────────────────────────────────────────
print('\n[5] B1F 기둥 솔리드...')
z_b1f_bot = SL['B1F']
z_b1f_top = SL['1F']
col_before = stats['col']

for c in cols_b1f_dong:
    s = make_col_box(c['x'], c['y'], c['w'], c['h'], z_b1f_bot, z_b1f_top)
    if s:
        shapes.append(s)
        stats['col'] += 1
print(f'  기둥 {stats["col"]-col_before}개')

print('\n[6] B1F 보 (DXF스냅)...')
dims_dong_b1f = get_dim_text(DXF_DONG, CLIPS['DONG_B1F'])
beams_b1f = snap_beams_to_cols(
    DXF_DONG, CLIPS['DONG_B1F'], cols_b1f_dong, dims_dong_b1f, z_b1f_top,
    tfm=TRANSFORMS['DONG_B1F'])
beam_before = stats['beam']
for x0,y0,x1,y1,z_bot,bw,bh in beams_b1f:
    s = make_beam(x0, y0, x1, y1, z_bot, bw, bh)
    if s:
        shapes.append(s)
        stats['beam'] += 1
print(f'  보 {len(beams_b1f)}개 → 생성 {stats["beam"]-beam_before}개')

# ── STEP 출력 ───────────────────────────────────────────────
print('\n[7] STEP 출력...')
doc_fc = FreeCAD.newDocument('v11')
compound = Part.makeCompound(shapes)
obj = doc_fc.addObject('Part::Feature', 'v11_topology')
obj.Shape = compound
doc_fc.recompute()
STEP = 'output/v11_topology.step'
Part.export([obj], STEP)
sz = os.path.getsize(STEP)//1024

print('\n' + '='*60)
print('v11 완료')
print('='*60)
print(f'  기둥: {stats["col"]:5d}개')
print(f'  보:   {stats["beam"]:5d}개')
print(f'  합계: {len(shapes):5d}개')
print(f'  STEP: {STEP} ({sz} KB)')
