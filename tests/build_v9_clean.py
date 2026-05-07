"""
build_v9_clean.py — 기둥·보 좌표 완전 통일 빌드
=================================================
핵심 원칙:
  기둥: poc_v3_101.json abs 좌표 (모델공간, 검증 완료)
  보:   S-GIRDER LINE DXF 좌표 (동일 모델공간, 검증 완료)
  필터: 기둥을 보 Y 범위 내로 제한 → 부유 기둥 제거
  결과: 수직·수평 부재 완전 정렬

실행: freecadcmd tests/build_v9_clean.py
"""
import sys, os, math, json, csv, re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

os.chdir('D:/Git/FreeCAD_4TH')
sys.path.insert(0, 'D:/Git/FreeCAD_4TH')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import Part, FreeCAD, ezdxf
from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.entity_scanner import iter_all

# ── 좌표 통일 ─────────────────────────────────────────────────
TX_PKG = -448000.0; TY_PKG = 3621813.0  # TY 기준선 직독 정밀화 (3622000→3621813, 187mm)
DONG_B1F_DX = 116247.0 - 242247.0   # -126000 (S30-002 → master)
PKG_B1F_DX  = -630000.0              # -630000 (Y1 기준점으로 검증: B2F X1=1060938, B1F X1=1690938, 차=630000)

# ── 주차장 DXF 클립 (101동 인접 구역 — 검증된 방식) ─────────────
# B2F: 원래 클립 그대로 (101동 인접 B2F 구역)
# B1F: B2F 클립 + 630000 X offset (Y1 기준점으로 검증된 두 층 간격)
# 이렇게 하면 btrans_pkg_b1 적용 후 B2F와 동일 모델 좌표
_B2F_X1, _B2F_X2 = 552082.0, 712082.0
_PKG_Y1, _PKG_Y2 = -1376738.0, -1216738.0
PKG_B2F_CLIP = (_B2F_X1,          _PKG_Y1, _B2F_X2,          _PKG_Y2)
PKG_B1F_CLIP = (_B2F_X1+630000.0, _PKG_Y1, _B2F_X2+630000.0, _PKG_Y2)
# B2F 모델 X: 552082-448000=104082 ~ 712082-448000=264082
# B1F 모델 X: 1182082-1078000=104082 ~ 1342082-1078000=264082 ← 동일!

def tfm_dong_b2(x,y): return x, y
def tfm_dong_b1(x,y): return x + DONG_B1F_DX, y
def tfm_pkg_b2(x,y):  return x + TX_PKG, y + TY_PKG
def tfm_pkg_b1(x,y):  return x + PKG_B1F_DX + TX_PKG, y + TY_PKG

# ── 확정 치수 ─────────────────────────────────────────────────
SL_B2F = -9050.0; SL_B1F = -5600.0; SL_1F = 370.0
PKG_B1F_TOP  = SL_B1F + 4400.0   # -1200mm
TOWER_B1F_TOP = SL_1F              # +370mm
SLAB_T = 150.0

DONG_DXF  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
BEAM_CLIP = (55000, 2085000, 229013, 2460000)  # S30-001 영역 전체
BEAM_DIM_PAT = re.compile(r'^(\d{3,4})[Xx](\d{3,4})$')


# ──────────────────────────────────────────────────────────────
# 형상 유틸
# ──────────────────────────────────────────────────────────────

def box_solid(cx, cy, zb, zt, w, h):
    w, h, ht = abs(w), abs(h), zt - zb
    if ht <= 0 or w < 10 or h < 10: return None
    s = Part.makeBox(w, h, ht, FreeCAD.Vector(cx-w/2, cy-h/2, zb))
    return s if s.isValid() else None

def prism_solid(pts, zb, zt):
    ht = zt - zb
    if ht <= 0 or len(pts) < 3: return None
    vv = [FreeCAD.Vector(x, y, zb) for x, y in pts] + [FreeCAD.Vector(pts[0][0], pts[0][1], zb)]
    try:
        face = Part.makeFace(Part.makePolygon(vv), 'Part::FaceMakerBullseye')
        s = face.extrude(FreeCAD.Vector(0, 0, ht))
        return s if s.isValid() else None
    except: return None

def beam_solid(x0, y0, x1, y1, bw, bh, zb, zt):
    dx, dy = x1-x0, y1-y0; ln = math.hypot(dx, dy)
    if ln < 100 or zt <= zb: return None
    ux, uy = -dy/ln, dx/ln
    pts = [(x0+ux*bw/2, y0+uy*bw/2), (x1+ux*bw/2, y1+uy*bw/2),
           (x1-ux*bw/2, y1-uy*bw/2), (x0-ux*bw/2, y0-uy*bw/2)]
    return prism_solid(pts, zb, zt)


# ──────────────────────────────────────────────────────────────
# 부재 데이터
# ──────────────────────────────────────────────────────────────

@dataclass
class Member:
    id: str; symbol: str; mtype: str; zone: str; floor: str
    volume_m3: float = 0.0
    shape: object = field(default=None, repr=False)
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        d = {'id':self.id,'symbol':self.symbol,'type':self.mtype,
             'zone':self.zone,'floor':self.floor,'volume_m3':self.volume_m3}
        d.update(self.extra); return d

TYPE_KR = {'column':'기둥','beam_x':'보(X)','beam_y':'보(Y)','slab':'슬라브','wall':'전단벽'}


# ──────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────

print('='*65)
print('v9 기둥·보 좌표 완전 통일 빌드')
print('='*65)

# 1. poc_v3 로드
with open('output/poc_v3_101.json', encoding='utf-8') as f:
    poc = json.load(f)

# 2. S-GIRDER 보 추출 (모델공간 좌표 — 검증 완료)
print('\n[1] S-GIRDER 보 추출...')
ext = StructuralExtractor(min_col_size=100, max_col_size=3000, min_slab_area_m2=50)
doc_d = ezdxf.readfile(DONG_DXF, encoding='cp949')
d_dong = ext.extract(doc_d, clip=BEAM_CLIP)
beams_dxf = [b for b in d_dong.beams if math.hypot(b.x1-b.x0,b.y1-b.y0) >= 300]
print(f'  S-GIRDER LINE: {len(beams_dxf)}개')

# 보 Y 범위 계산 (기둥 필터 기준)
BEAM_Y_MIN = min(min(b.y0,b.y1) for b in beams_dxf)
BEAM_Y_MAX = max(max(b.y0,b.y1) for b in beams_dxf)
BEAM_X_MIN = min(min(b.x0,b.x1) for b in beams_dxf)
BEAM_X_MAX = max(max(b.x0,b.x1) for b in beams_dxf)
print(f'  보 X: {BEAM_X_MIN:.0f}~{BEAM_X_MAX:.0f}  Y: {BEAM_Y_MIN:.0f}~{BEAM_Y_MAX:.0f}')

# 보 치수 TEXT 직독 (400X800 형식)
dim_lbl = []
for e in iter_all(doc_d.modelspace()):
    if e.dxftype() not in ('TEXT','MTEXT'): continue
    try:
        raw = (e.dxf.text if e.dxftype()=='TEXT' else e.text).strip().replace(' ','').upper()
        m2 = BEAM_DIM_PAT.match(raw)
        if not m2: continue
        pos = e.dxf.insert; px, py = float(pos.x), float(pos.y)
        if not (BEAM_CLIP[0]<=px<=BEAM_CLIP[2] and BEAM_CLIP[1]<=py<=BEAM_CLIP[3]): continue
        dim_lbl.append((raw, px, py, float(m2.group(1)), float(m2.group(2))))
    except: pass
print(f'  치수TEXT: {len(dim_lbl)}개  예:{[l[0] for l in dim_lbl[:4]]}')

def nearest_dim(mx, my, max_d=4000.0):
    best, bd = None, max_d+1
    for item in dim_lbl:
        d = math.hypot(item[1]-mx, item[2]-my)
        if d < bd: bd, best = d, item
    return best

# 3. 기둥 + 전단벽 로드
# ▶ 핵심 원칙: B2F 마스터 시트의 XY를 B1F에도 그대로 사용
#   이유: S30-002(B1F)는 X 범위가 S30-001(B2F)의 절반뿐 → B1F가 24m 좌측으로 치우침
#   해결: S30-001 XY 위치 그대로, Z만 바꿔서 B1F 기둥 생성
print('\n[2] 기둥 로드 (마스터 시트 기반 양 층 생성)...')
Y_TOL = 8000.0
all_members: List[Member] = []

# 마스터 시트 → 생성할 층 정의
BSMNT_DXF = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'

# 주차장 DXF에서 전체 클립으로 재추출
print('\n[PKG 전체 클립 재추출]')
import ezdxf as _ezdxf
_ext = StructuralExtractor(min_col_size=100, max_col_size=3000, min_slab_area_m2=50)
_doc_b = _ezdxf.readfile(BSMNT_DXF, encoding='cp949')
_pkg_b2 = _ext.extract(_doc_b, clip=PKG_B2F_CLIP)
_pkg_b1 = _ext.extract(_doc_b, clip=PKG_B1F_CLIP)
print(f'  PKG-B2 (전체 클립): {len(_pkg_b2.columns)}개 기둥')
print(f'  PKG-B1 (전체 클립): {len(_pkg_b1.columns)}개 기둥')

# 동적 poc 시트 대신 DXF 직접 추출 결과 사용
# PKG-B2: btrans_pkg_b2, PKG-B1: btrans_pkg_b1
_pkg_b2_abs = [(c.cx, c.cy, abs(c.w), abs(c.h)) for c in _pkg_b2.columns]
_pkg_b1_abs = [(c.cx, c.cy, abs(c.w), abs(c.h)) for c in _pkg_b1.columns]

CONFIGS = [
    ('S30-001', 'B2F', 'DONG', SL_B2F,  SL_B1F,        tfm_dong_b2),
    ('S30-001', 'B1F', 'DONG', SL_B1F,  TOWER_B1F_TOP,  tfm_dong_b2),  # 같은 XY
    ('PKG-B2',  'B2F', 'PKG',  SL_B2F,  SL_B1F,         tfm_pkg_b2),
    ('PKG-B1',  'B1F', 'PKG',  SL_B1F,  PKG_B1F_TOP,    tfm_pkg_b1),   # 별도 클립, 별도 변환
]

# PKG DXF 직접 데이터를 CONFIGS에서 사용하도록 재정의
PKG_RAW = {
    ('PKG-B2', 'B2F'): _pkg_b2_abs,
    ('PKG-B1', 'B1F'): _pkg_b1_abs,
}

for sid, fkey, zone, z_bot, z_top, tfm in CONFIGS:
    sheet = next(s for s in poc['sheets'] if s['sheet_id'] == sid)
    slab_t = sheet['slab_thickness']
    z_col_top = z_top - slab_t
    height = z_col_top - z_bot
    sym_cnt: Dict[str,int] = {}
    col_ok = 0; col_skip = 0

    # 기둥 소스 결정: PKG는 DXF 직접 추출, DONG은 poc_v3
    if (sid, fkey) in PKG_RAW:
        raw_cols = PKG_RAW[(sid, fkey)]
        col_source = [(tfm(cx_r, cy_r), cw_r, ch_r, 'C') for cx_r, cy_r, cw_r, ch_r in raw_cols]
    else:
        sheet = next(s for s in poc['sheets'] if s['sheet_id'] == sid)
        col_source = [(tfm(c['abs_cx'], c['abs_cy']), abs(c['w']), abs(c['h']), c.get('symbol','C'))
                      for c in sheet['columns']]

    for (cx, cy), cw, ch, sym in col_source:
        if cy < BEAM_Y_MIN - Y_TOL or cy > BEAM_Y_MAX + Y_TOL:
            col_skip += 1; continue
        sym_cnt[sym] = sym_cnt.get(sym, 0) + 1
        mid = f'{sym}-{fkey}-{zone}-{sym_cnt[sym]:04d}'
        s = box_solid(cx, cy, z_bot, z_col_top, cw, ch)
        vol = (cw * ch * height) / 1e9 if height > 0 else 0.0
        all_members.append(Member(
            id=mid, symbol=sym, mtype='column', zone=zone, floor=fkey,
            volume_m3=round(vol, 4), shape=s,
            extra={'section': f'{int(cw)}x{int(ch)}', 'height_mm': round(height),
                   'cx': round(cx), 'cy': round(cy)},
        ))
        col_ok += 1

    # 전단벽 (B2F만 — 중복 방지, DONG만)
    wall_ok = 0
    if fkey == 'B2F' and zone == 'DONG':
        sheet = next(s for s in poc['sheets'] if s['sheet_id'] == sid)
        for seq, w in enumerate(sheet.get('wall_segments', [])):
            cx, cy = tfm(w['abs_cx'], w['abs_cy'])
            if cy < BEAM_Y_MIN - Y_TOL or cy > BEAM_Y_MAX + Y_TOL:
                continue
            ww, wh = abs(w['w']), abs(w['h'])
            s = box_solid(cx, cy, z_bot, z_col_top, ww, wh)
            vol = (ww * wh * height) / 1e9 if height > 0 else 0.0
            all_members.append(Member(
                id=f'SW-{fkey}-{zone}-{seq+1:04d}', symbol='SW', mtype='wall',
                zone=zone, floor=fkey, volume_m3=round(vol, 4), shape=s,
                extra={'section': f'{int(ww)}x{int(wh)}', 'cx': round(cx), 'cy': round(cy)},
            ))
            wall_ok += 1

    print(f'  [{sid}→{fkey}-{zone}] 기둥:{col_ok} 전단벽:{wall_ok} (Y필터:{col_skip}개 제거)')

# 4. S-GIRDER 보 생성 — 기둥 중심 스냅 (face→center)
print('\n[3] S-GIRDER 보 생성 (기둥 중심 스냅)...')

# 기둥 중심 목록 수집 (필터 적용 후)
col_centers = [(m.extra['cx'], m.extra['cy'])
               for m in all_members if m.mtype == 'column']
print(f'  스냅 기준 기둥: {len(col_centers)}개')

def snap_to_col(px, py, snap_tol=1200.0):
    """보 끝점 → 가장 가까운 기둥 중심 스냅 (기둥 반폭 + 여유)."""
    best, bd = None, snap_tol + 1
    for cx, cy in col_centers:
        d = math.hypot(cx-px, cy-py)
        if d < bd: bd, best = d, (cx, cy)
    return best if bd <= snap_tol else (px, py)

sym_cnt_b: Dict[str,int] = {}
sym_cnt_b1: Dict[str,int] = {}
snapped, total_pts = 0, 0

def make_beams(beams_list, fkey, z_slab_top, sym_cnt_d):
    global snapped, total_pts
    for bm in beams_list:
        # 기둥 중심으로 스냅
        x0, y0 = snap_to_col(bm.x0, bm.y0)
        x1, y1 = snap_to_col(bm.x1, bm.y1)
        total_pts += 2
        if (x0, y0) != (bm.x0, bm.y0): snapped += 1
        if (x1, y1) != (bm.x1, bm.y1): snapped += 1
        dist = math.hypot(x1-x0, y1-y0)
        if dist < 300: continue
        mx, my = (x0+x1)/2, (y0+y1)/2
        hit = nearest_dim(mx, my)
        if hit: sym,_,_,bw,bh = hit
        else: bw,bh=(600.0 if dist>7000 else 400.0),900.0; sym=f'{int(bw)}X{int(bh)}_EST'
        sym_cnt_d[sym] = sym_cnt_d.get(sym,0)+1
        mid = f'{sym}-{fkey}-DONG-{sym_cnt_d[sym]:04d}'
        s = beam_solid(x0,y0,x1,y1, bw,bh, z_slab_top-bh, z_slab_top-SLAB_T)
        vol = (bw*bh*dist)/1e9
        ang = abs(math.degrees(math.atan2(y1-y0,x1-x0))) % 180
        mtype = 'beam_y' if (75<ang<105) else 'beam_x'
        all_members.append(Member(
            id=mid, symbol=sym, mtype=mtype, zone='DONG', floor=fkey,
            volume_m3=round(vol,4), shape=s,
            extra={'section':f'{int(bw)}x{int(bh)}','span_mm':round(dist)},
        ))

make_beams(beams_dxf, 'B2F', SL_B1F, sym_cnt_b)
make_beams(beams_dxf, 'B1F', TOWER_B1F_TOP, sym_cnt_b1)
b_total = sum(1 for m in all_members if 'beam' in m.mtype)
print(f'  스냅: {snapped}/{total_pts} 끝점  보: {b_total}개')

# 5. FreeCAD 등록
print('\n[4] FreeCAD 등록...')
fc_doc = FreeCAD.newDocument('v9')
valid = []
for mbr in all_members:
    if mbr.shape is None: continue
    feat = fc_doc.addObject('Part::Feature', mbr.id[:63])
    feat.Shape = mbr.shape; valid.append(mbr.shape)
fc_doc.recompute()
print(f'  {len(fc_doc.Objects)}개 등록')

# 6. STEP 출력
print('\n[5] STEP 출력...')
os.makedirs('output', exist_ok=True)
STEP = 'output/v9_clean.step'
try:
    Part.export(list(fc_doc.Objects), STEP)
    sz = os.path.getsize(STEP)
    if sz < 10000: raise ValueError(f'{sz}B')
    print(f'  [STEP] {STEP}  ({sz//1024} KB)')
except Exception as e:
    print(f'  fallback: {e}')
    cmpd = Part.makeCompound(valid)
    fa = fc_doc.addObject('Part::Feature','all'); fa.Shape = cmpd
    fc_doc.recompute(); fa.Shape.exportStep(STEP)
    print(f'  [STEP fallback] {STEP}  ({os.path.getsize(STEP)//1024} KB)')

# 7. BOQ
print('\n[6] BOQ 출력...')
by_type: Dict[str,dict] = {}
for m in all_members:
    t = m.mtype
    by_type.setdefault(t,{'count':0,'vol':0.0})
    by_type[t]['count'] += 1; by_type[t]['vol'] = round(by_type[t]['vol']+m.volume_m3,3)

total = round(sum(m.volume_m3 for m in all_members),3)
with open('output/v9_boq.json','w',encoding='utf-8') as f:
    json.dump({'total':len(all_members),'total_m3':total,'by_type':by_type,
               'members':[m.to_dict() for m in all_members]}, f, ensure_ascii=False, indent=2)
with open('output/v9_boq.csv','w',newline='',encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['부재ID','도면명','유형','구역','층','치수','체적(m³)'])
    for m in all_members:
        w.writerow([m.id,m.symbol,TYPE_KR.get(m.mtype,m.mtype),m.zone,m.floor,
                    m.extra.get('section',''),m.volume_m3])
print(f'  [JSON/CSV] v9_boq.{"{json,csv}"}')

# 최종
print('\n'+'='*65)
print('부재 집계:')
for t in ['column','beam_x','beam_y','wall']:
    info = by_type.get(t,{'count':0,'vol':0.0})
    if info['count']==0: continue
    print(f'  {TYPE_KR.get(t,t):7s}: {info["count"]:4d}개  {info["vol"]:8.1f} m³')
print(f'\n  합계: {len(all_members)}부재 / {len(valid)}솔리드 / {total:.1f} m³')
print('='*65)
print('[완료] v9 기둥·보 좌표 통일 빌드')
