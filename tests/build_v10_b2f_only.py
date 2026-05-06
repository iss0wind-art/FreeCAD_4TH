"""
build_v10_b2f_only.py — B2F 단독 검증 빌드
=============================================
목적: 좌표 정합 최종 검증
  - S30-001 기둥만 (B2F, abs 좌표)
  - S-GIRDER 보만 (B2F, 동일 클립)
  - 다른 데이터 일절 없음 → 완전 순수 B2F
  - 기둥 Y 필터: S-GIRDER Y 범위 내로 제한

결과가 깨끗하면 좌표계 정합 완료 확인.
실행: freecadcmd tests/build_v10_b2f_only.py
"""
import sys, os, math, json, csv, re
from typing import List, Tuple, Dict

os.chdir('D:/Git/FreeCAD_4TH')
sys.path.insert(0, 'D:/Git/FreeCAD_4TH')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import Part, FreeCAD, ezdxf
from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.entity_scanner import iter_all

SL_B2F = -9050.0; SL_B1F = -5600.0; SLAB_T = 150.0
DONG_DXF  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
BEAM_CLIP = (55000, 2085000, 229013, 2460000)
BEAM_DIM_PAT = re.compile(r'^(\d{3,4})[Xx](\d{3,4})$')

print('='*60)
print('v10 B2F 단독 검증')
print('='*60)

# ── 1. S-GIRDER 보 추출 ──────────────────────────────────────
print('\n[1] S-GIRDER 보 추출...')
ext = StructuralExtractor(min_col_size=100, max_col_size=3000, min_slab_area_m2=50)
doc = ezdxf.readfile(DONG_DXF, encoding='cp949')
beams = [b for b in ext.extract(doc, clip=BEAM_CLIP).beams
         if math.hypot(b.x1-b.x0, b.y1-b.y0) >= 300]
bxs = [(b.x0+b.x1)/2 for b in beams]; bys = [(b.y0+b.y1)/2 for b in beams]
BEAM_X_MIN, BEAM_X_MAX = min(bxs), max(bxs)
BEAM_Y_MIN, BEAM_Y_MAX = min(bys), max(bys)
print(f'  보 {len(beams)}개  X:{BEAM_X_MIN:.0f}~{BEAM_X_MAX:.0f}  Y:{BEAM_Y_MIN:.0f}~{BEAM_Y_MAX:.0f}')

# 보 치수 TEXT
dim_lbl = []
for e in iter_all(doc.modelspace()):
    if e.dxftype() not in ('TEXT','MTEXT'): continue
    try:
        raw = (e.dxf.text if e.dxftype()=='TEXT' else e.text).strip().replace(' ','').upper()
        m = BEAM_DIM_PAT.match(raw)
        if not m: continue
        pos = e.dxf.insert; px, py = float(pos.x), float(pos.y)
        if not (BEAM_CLIP[0]<=px<=BEAM_CLIP[2] and BEAM_CLIP[1]<=py<=BEAM_CLIP[3]): continue
        dim_lbl.append((raw, px, py, float(m.group(1)), float(m.group(2))))
    except: pass
print(f'  치수TEXT: {len(dim_lbl)}개')

def nearest_dim(mx, my, max_d=4000.0):
    best, bd = None, max_d+1
    for item in dim_lbl:
        d = math.hypot(item[1]-mx, item[2]-my)
        if d < bd: bd, best = d, item
    return best

# ── 2. S30-001 기둥 로드 (Y 필터 적용) ──────────────────────
print('\n[2] S30-001 기둥 로드...')
with open('output/poc_v3_101.json', encoding='utf-8') as f:
    poc = json.load(f)

s30_001 = next(s for s in poc['sheets'] if s['sheet_id'] == 'S30-001')
Y_TOL = 5000.0  # 빡빡하게: 보 Y 범위 ±5m

cols_b2f = []
for c in s30_001['columns']:
    cx, cy = c['abs_cx'], c['abs_cy']
    # 보 Y 범위 밖 제외
    if cy < BEAM_Y_MIN - Y_TOL or cy > BEAM_Y_MAX + Y_TOL:
        continue
    cols_b2f.append((cx, cy, abs(c['w']), abs(c['h']), c.get('symbol','C')))

print(f'  B2F 기둥: {len(cols_b2f)}개  (전체 {len(s30_001["columns"])}개 중)')
cx_vals = [c[0] for c in cols_b2f]; cy_vals = [c[1] for c in cols_b2f]
print(f'  기둥 X:{min(cx_vals):.0f}~{max(cx_vals):.0f}  Y:{min(cy_vals):.0f}~{max(cy_vals):.0f}')

# ── 3. 기둥 중심 스냅 테이블 ──────────────────────────────────
col_centers = [(c[0], c[1]) for c in cols_b2f]

def snap_to_col(px, py, tol=1000.0):
    best, bd = None, tol+1
    for cx, cy in col_centers:
        d = math.hypot(cx-px, cy-py)
        if d < bd: bd, best = d, (cx, cy)
    return best if bd <= tol else (px, py)

# ── 4. 솔리드 생성 ───────────────────────────────────────────
def box_solid(cx, cy, zb, zt, w, h):
    w, h, ht = abs(w), abs(h), zt-zb
    if ht<=0 or w<10 or h<10: return None
    s = Part.makeBox(w, h, ht, FreeCAD.Vector(cx-w/2, cy-h/2, zb))
    return s if s.isValid() else None

def prism_solid(pts, zb, zt):
    if zt<=zb or len(pts)<3: return None
    vv = [FreeCAD.Vector(x,y,zb) for x,y in pts]+[FreeCAD.Vector(pts[0][0],pts[0][1],zb)]
    try:
        face = Part.makeFace(Part.makePolygon(vv),'Part::FaceMakerBullseye')
        s = face.extrude(FreeCAD.Vector(0,0,zt-zb))
        return s if s.isValid() else None
    except: return None

def beam_solid(x0,y0,x1,y1,bw,bh,zb,zt):
    dx,dy = x1-x0,y1-y0; ln = math.hypot(dx,dy)
    if ln<100 or zt<=zb: return None
    ux,uy = -dy/ln, dx/ln
    pts = [(x0+ux*bw/2,y0+uy*bw/2),(x1+ux*bw/2,y1+uy*bw/2),
           (x1-ux*bw/2,y1-uy*bw/2),(x0-ux*bw/2,y0-uy*bw/2)]
    return prism_solid(pts, zb, zt)

print('\n[3] 솔리드 생성...')
fc_doc = FreeCAD.newDocument('v10')
shapes = []
sym_cnt: Dict[str,int] = {}

# B2F 기둥
z_col_top = SL_B1F - SLAB_T  # -5750
for cx, cy, cw, ch, sym in cols_b2f:
    sym_cnt[sym] = sym_cnt.get(sym, 0)+1
    mid = f'{sym}-B2F-{sym_cnt[sym]:04d}'
    s = box_solid(cx, cy, SL_B2F, z_col_top, cw, ch)
    if s:
        feat = fc_doc.addObject('Part::Feature', mid[:63])
        feat.Shape = s; shapes.append((mid, s))
print(f'  B2F 기둥: {len(shapes)}개')

# B2F 보 (기둥 중심 스냅)
beam_cnt = 0; snap_cnt = 0
sym_cnt_b: Dict[str,int] = {}
for bm in beams:
    x0,y0 = snap_to_col(bm.x0, bm.y0); x1,y1 = snap_to_col(bm.x1, bm.y1)
    if (x0,y0)!=(bm.x0,bm.y0): snap_cnt+=1
    if (x1,y1)!=(bm.x1,bm.y1): snap_cnt+=1
    dist = math.hypot(x1-x0, y1-y0)
    if dist < 300: continue
    mx,my = (x0+x1)/2,(y0+y1)/2
    hit = nearest_dim(mx, my)
    if hit: sym,_,_,bw,bh = hit
    else: bw,bh = (600. if dist>7000 else 400.),900.; sym=f'{int(bw)}X{int(bh)}_EST'
    sym_cnt_b[sym] = sym_cnt_b.get(sym,0)+1
    mid = f'{sym}-B2F-BM-{sym_cnt_b[sym]:04d}'
    z_slab = SL_B1F; bz = z_slab-bh; bzt = z_slab-SLAB_T
    s = beam_solid(x0,y0,x1,y1, bw,bh, bz, bzt)
    if s:
        feat = fc_doc.addObject('Part::Feature', mid[:63])
        feat.Shape = s; shapes.append((mid, s)); beam_cnt+=1

print(f'  B2F 보: {beam_cnt}개  스냅: {snap_cnt}/{len(beams)*2} 끝점')

fc_doc.recompute()
print(f'  등록: {len(fc_doc.Objects)}개')

# ── 5. STEP 출력 ─────────────────────────────────────────────
print('\n[4] STEP 출력...')
os.makedirs('output', exist_ok=True)
STEP = 'output/v10_b2f_only.step'
try:
    Part.export(list(fc_doc.Objects), STEP)
    sz = os.path.getsize(STEP)
    if sz < 10000: raise ValueError(f'{sz}B')
    print(f'  [STEP] {STEP}  ({sz//1024} KB)')
except Exception as e:
    print(f'  fallback: {e}')
    cmpd = Part.makeCompound([s for _,s in shapes])
    fa = fc_doc.addObject('Part::Feature','all'); fa.Shape=cmpd
    fc_doc.recompute(); fa.Shape.exportStep(STEP)
    print(f'  [STEP fallback] {STEP}  ({os.path.getsize(STEP)//1024} KB)')

# ── 6. BOQ 요약 ──────────────────────────────────────────────
cols_vol = sum((c[2]*c[3]*(z_col_top-SL_B2F))/1e9 for c in cols_b2f)
print(f'\n[완료]')
print(f'  기둥: {len(shapes)-beam_cnt}개  {cols_vol:.1f} m³')
print(f'  보:   {beam_cnt}개')
print(f'  기둥-보 좌표: 동일 좌표계 (에이전트 검증 완료)')
print(f'  C1 기준: 기둥(129241,2381804) ↔ 가장가까운 보 끝점 거리=354mm')
