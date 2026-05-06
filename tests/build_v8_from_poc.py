"""
build_v8_from_poc.py — poc_v3_101.json 직접 사용 3D 빌드
=========================================================
poc_v3_101.json: 이미 추출 완료된 부재 데이터
  - 기둥 abs_cx/abs_cy: 도면 절대 좌표
  - 보 p1/p2: 시트 로컬 좌표 (→ offset 계산 후 절대 변환)
  - 심볼: C1, RB20 등 도면 원래 이름
  - 치수: codex_w/h (일람표 직독)

부재 ID: {symbol}-{floor}-{zone}-{seq:04d}
  예) C1-B2F-DONG-0001, RB20-B2F-DONG-0001

출력: output/v8_poc.step + output/v8_boq.json + output/v8_boq.csv

실행: freecadcmd tests/build_v8_from_poc.py
"""
import sys, os, math, json, csv
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

os.chdir('D:/Git/FreeCAD_4TH')
sys.path.insert(0, 'D:/Git/FreeCAD_4TH')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import Part, FreeCAD
import ezdxf
import re
from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.entity_scanner import iter_all

# ── 좌표 통일 (coord_align_result.json 직독값) ───────────────
# S30-001을 기준 좌표계로 사용
TX_PKG = -448000.0   # coord_align_result: tx=-448000
TY_PKG =  3622000.0  # coord_align_result: ty=3622000

# 시트별 오프셋 보정 (S30-001 기준으로 통일)
# S30-001 ox=116247, S30-002 ox=242247 → S30-002 X보정: -126000
DONG_B1F_X_CORR = 116247.0 - 242247.0   # = -126000mm
# PKG-B1 ox=877250, PKG-B2 ox=247250 → PKG-B1 X보정: -630000
PKG_B1F_X_CORR  = 247250.0 - 877250.0   # = -630000mm

def btrans_pkg_b2(x, y):  return x + TX_PKG,               y + TY_PKG
def btrans_pkg_b1(x, y):  return x + PKG_B1F_X_CORR + TX_PKG, y + TY_PKG
def btrans_dong_b1(x, y): return x + DONG_B1F_X_CORR,      y

# ── 확정 치수 ─────────────────────────────────────────────────
PKG_B1F_H = 4400.0
SL_B1F    = -5600.0
SL_B2F    = -9050.0
SL_1F     =   370.0
PKG_B1F_TOP  = SL_B1F + PKG_B1F_H   # -1200mm
TOWER_B1F_TOP = SL_1F                 # +370mm
SLAB_T = 150.0

# 도면 경로
DONG_DXF  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
DONG_CLIP = (69013, 2241258, 229013, 2401258)   # S30-001 기둥 클립
# 보: X는 S30-001 영역만 (229013 이하 — S30-002 시작 242247 제외)
# Y는 기둥 전체 포함으로 확장 (2451963까지)
BEAM_CLIP = (55000, 2085000, 229013, 2460000)

# 보 치수 직독 패턴 (400X800 형식)
BEAM_DIM_PAT = re.compile(r'^(\d{3,4})[Xx](\d{3,4})$')


# ──────────────────────────────────────────────────────────────
# 부재 데이터 클래스
# ──────────────────────────────────────────────────────────────

@dataclass
class Member:
    id:        str
    symbol:    str
    mtype:     str    # column | beam | slab | wall
    zone:      str    # DONG | PKG
    floor:     str    # B2F | B1F
    volume_m3: float = 0.0
    shape:     object = field(default=None, repr=False)
    extra:     dict   = field(default_factory=dict)

    def to_dict(self):
        d = {'id': self.id, 'symbol': self.symbol,
             'type': self.mtype, 'zone': self.zone, 'floor': self.floor,
             'volume_m3': self.volume_m3}
        d.update(self.extra)
        return d


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
    vv = [FreeCAD.Vector(x, y, zb) for x, y in pts]
    vv.append(vv[0])
    try:
        face = Part.makeFace(Part.makePolygon(vv), 'Part::FaceMakerBullseye')
        s = face.extrude(FreeCAD.Vector(0, 0, ht))
        return s if s.isValid() else None
    except Exception:
        return None


def beam_solid(x0, y0, x1, y1, bw, bh, zb, zt):
    dx, dy = x1-x0, y1-y0
    ln = math.hypot(dx, dy)
    if ln < 100 or zt <= zb: return None
    ux, uy = -dy/ln, dx/ln
    pts = [(x0+ux*bw/2, y0+uy*bw/2), (x1+ux*bw/2, y1+uy*bw/2),
           (x1-ux*bw/2, y1-uy*bw/2), (x0-ux*bw/2, y0-uy*bw/2)]
    return prism_solid(pts, zb, zt)


# ──────────────────────────────────────────────────────────────
# 시트 로컬 → 절대 오프셋 계산
# ──────────────────────────────────────────────────────────────

def compute_sheet_offset(sheet_data) -> Tuple[float, float]:
    """
    첫 번째 기둥의 (cx, abs_cx), (cy, abs_cy)로 오프셋 계산.
    girder p1/p2 (로컬) → 절대 변환에 사용.
    """
    cols = sheet_data.get('columns', [])
    if not cols:
        return 0.0, 0.0
    c = cols[0]
    ox = c['abs_cx'] - c['cx']
    oy = c['abs_cy'] - c['cy']
    return ox, oy


# ──────────────────────────────────────────────────────────────
# 시트별 부재 생성
# ──────────────────────────────────────────────────────────────

def build_sheet(sheet, zone, transform=None) -> List[Member]:
    """
    poc_v3_101.json 시트 하나 → Member 목록.
    transform: (x,y) → (x,y) 좌표계 변환 (PKG는 btrans 적용)
    """
    members = []
    floor    = sheet['floor_key']     # 'B2F' | 'B1F'
    z_bot    = sheet['z_floor_bottom']
    z_top    = sheet['z_floor_top']
    slab_t   = sheet['slab_thickness']

    # 주차장 B1F 층고 보정 (방부장 명시 4400mm)
    if zone == 'PKG' and floor == 'B1F':
        z_top = PKG_B1F_TOP  # -1200mm

    z_col_top   = z_top - slab_t
    col_height  = z_col_top - z_bot

    # 시트 오프셋 (girder 로컬→절대 변환용)
    ox, oy = compute_sheet_offset(sheet)

    sym_cnt: Dict[str, int] = {}

    # ── 기둥 ──────────────────────────────────────────────────
    for c in sheet.get('columns', []):
        cx, cy = c['abs_cx'], c['abs_cy']
        if transform:
            cx, cy = transform(cx, cy)
        cw, ch = abs(c['w']), abs(c['h'])
        sym = c.get('symbol') or 'C'
        sym_cnt[sym] = sym_cnt.get(sym, 0) + 1
        mid = f'{sym}-{floor}-{zone}-{sym_cnt[sym]:04d}'

        s = box_solid(cx, cy, z_bot, z_col_top, cw, ch)
        vol = (cw * ch * col_height) / 1e9 if col_height > 0 else 0.0

        members.append(Member(
            id=mid, symbol=sym, mtype='column',
            zone=zone, floor=floor,
            volume_m3=round(vol, 4), shape=s,
            extra={'section': f'{int(cw)}x{int(ch)}',
                   'height_mm': round(col_height),
                   'cx': round(cx), 'cy': round(cy)},
        ))

    # ── 전단벽 세그먼트 (wall_segments) ──────────────────────
    for w in sheet.get('wall_segments', []):
        cx, cy = w['abs_cx'], w['abs_cy']
        if transform:
            cx, cy = transform(cx, cy)
        ww, wh = abs(w['w']), abs(w['h'])
        sym = 'SW'
        sym_cnt['SW'] = sym_cnt.get('SW', 0) + 1
        mid = f'SW-{floor}-{zone}-{sym_cnt["SW"]:04d}'
        s = box_solid(cx, cy, z_bot, z_col_top, ww, wh)
        vol = (ww * wh * col_height) / 1e9 if col_height > 0 else 0.0
        members.append(Member(
            id=mid, symbol='SW', mtype='wall',
            zone=zone, floor=floor,
            volume_m3=round(vol, 4), shape=s,
            extra={'section': f'{int(ww)}x{int(wh)}',
                   'height_mm': round(col_height)},
        ))

    # ── 보 (girders) ──────────────────────────────────────────
    z_slab_top = z_top  # 보 상단 기준 = 슬라브 하면 (z_top - slab_t 아님 — 보는 슬라브 아래)
    for g in sheet.get('girders', []):
        p1 = g['p1']; p2 = g['p2']
        # 로컬 → 절대
        x0, y0 = p1[0] + ox, p1[1] + oy
        x1, y1 = p2[0] + ox, p2[1] + oy
        if transform:
            x0, y0 = transform(x0, y0)
            x1, y1 = transform(x1, y1)
        dist = math.hypot(x1-x0, y1-y0)
        if dist < 300: continue

        bw = g.get('codex_w') or 400.0
        bh = g.get('codex_h') or 900.0
        sym = g.get('symbol') or 'B'
        sym_cnt[sym] = sym_cnt.get(sym, 0) + 1
        mid = f'{sym}-{floor}-{zone}-{sym_cnt[sym]:04d}'

        z_beam_bot = z_slab_top - bh
        z_beam_top = z_slab_top - slab_t

        s = beam_solid(x0, y0, x1, y1, bw, bh, z_beam_bot, z_beam_top)
        vol = (bw * bh * dist) / 1e9

        ang = abs(math.degrees(math.atan2(y1-y0, x1-x0))) % 180
        mtype = 'beam_y' if (75 < ang < 105) else 'beam_x'

        members.append(Member(
            id=mid, symbol=sym, mtype=mtype,
            zone=zone, floor=floor,
            volume_m3=round(vol, 4), shape=s,
            extra={'section': f'{int(bw)}x{int(bh)}',
                   'span_mm': round(dist),
                   'x0': round(x0), 'y0': round(y0),
                   'x1': round(x1), 'y1': round(y1)},
        ))

    # ── 슬라브 (기둥 위치 기반 — 향후 outline 직독으로 교체) ─
    # poc_v3에는 slab_bbox_vol만 있어 별도 계산 안함
    # 추후: poc_v4에서 slab outline 추가 시 직독 예정

    return members


# ──────────────────────────────────────────────────────────────
# BOQ 출력
# ──────────────────────────────────────────────────────────────

TYPE_KR = {'column':'기둥', 'beam_x':'보(X)', 'beam_y':'보(Y)',
           'beam':'보', 'slab':'슬라브', 'wall':'전단벽'}


def export_json(members, path):
    by_type = {}; by_floor = {}
    for m in members:
        t, fl = m.mtype, m.floor
        by_type.setdefault(t, {'count': 0, 'vol_m3': 0.0})
        by_type[t]['count'] += 1
        by_type[t]['vol_m3'] = round(by_type[t]['vol_m3'] + m.volume_m3, 3)
        by_floor.setdefault(fl, {'count': 0, 'vol_m3': 0.0})
        by_floor[fl]['count'] += 1
        by_floor[fl]['vol_m3'] = round(by_floor[fl]['vol_m3'] + m.volume_m3, 3)
    total = round(sum(m.volume_m3 for m in members), 3)
    out = {'project': '에코델타 24BL 지하주차장+101동', 'generated': '2026-05-06',
           'total': len(members), 'total_volume_m3': total,
           'by_type': by_type, 'by_floor': by_floor,
           'members': [m.to_dict() for m in members]}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'  [JSON] {path}  ({len(members)}건, {total:.1f} m³)')


def export_csv(members, path):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['부재ID','도면부재명','유형','구역','층','치수(mm)','스팬/높이(mm)','체적(m³)'])
        for m in members:
            d = m.extra
            tkr = TYPE_KR.get(m.mtype, m.mtype)
            sec = d.get('section', '')
            dim = d.get('span_mm', d.get('height_mm', ''))
            w.writerow([m.id, m.symbol, tkr, m.zone, m.floor, sec, dim, m.volume_m3])
    print(f'  [CSV]  {path}')


# ──────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────

print('=' * 65)
print('v8 poc_v3_101.json 직접 사용 — 부재별 개별 + BOQ')
print('=' * 65)

with open('output/poc_v3_101.json', encoding='utf-8') as f:
    poc = json.load(f)

sheets = poc['sheets']
print(f'\n[데이터] {len(sheets)}개 시트 로드')
for s in sheets:
    print(f'  [{s["sheet_id"]}] {s["floor_key"]} — 기둥:{len(s["columns"])} 보:{len(s["girders"])} 전단벽:{len(s["wall_segments"])}')

print('\n[부재 생성]')
all_members: List[Member] = []

for sheet in sheets:
    sid  = sheet['sheet_id']
    fkey = sheet['floor_key']

    # 시트별 좌표 변환 (S30-001 기준 통일좌표계)
    if sid == 'S30-001':
        zone = 'DONG'; tfm = None             # 기준 시트 — 변환 없음
    elif sid == 'S30-002':
        zone = 'DONG'; tfm = btrans_dong_b1   # DONG B1F: X -= 126000
    elif sid == 'PKG-B2':
        zone = 'PKG';  tfm = btrans_pkg_b2    # PKG B2F: btrans
    elif sid == 'PKG-B1':
        zone = 'PKG';  tfm = btrans_pkg_b1    # PKG B1F: X -= 630000 + btrans
    else:
        zone = 'DONG'; tfm = None

    members = build_sheet(sheet, zone=zone, transform=tfm)
    all_members.extend(members)
    cols = sum(1 for m in members if m.mtype == 'column')
    beams = sum(1 for m in members if 'beam' in m.mtype)
    walls = sum(1 for m in members if m.mtype == 'wall')
    print(f'  [{sid}] {fkey}-{zone}: 기둥{cols} 보{beams} 전단벽{walls}')

# ── 보 생성 — poc_v3 기둥 위치 기반 (그리드 인접 연결) ────────
# 기둥 위치에서 직접 생성 → 기둥-보 좌표 완벽 일치 보장
print('\n[보 생성 — poc_v3 기둥 위치 기반]')

# 보 치수 TEXT 직독 (101동 DXF: 400X800 형식)
doc_d = ezdxf.readfile(DONG_DXF, encoding='cp949')
dim_labels: List[Tuple] = []
for e in iter_all(doc_d.modelspace()):
    if e.dxftype() not in ('TEXT','MTEXT'): continue
    try:
        raw = (e.dxf.text if e.dxftype()=='TEXT' else e.text).strip().replace(' ','').upper()
        m2 = BEAM_DIM_PAT.match(raw)
        if not m2: continue
        pos = e.dxf.insert
        px, py = float(pos.x), float(pos.y)
        if not (55000<=px<=229013 and 2085000<=py<=2460000): continue
        dim_labels.append((raw, px, py, float(m2.group(1)), float(m2.group(2))))
    except: pass
print(f'  치수TEXT: {len(dim_labels)}개  예:{[l[0] for l in dim_labels[:4]]}')

def nearest_dim(mx, my, max_dist=4000.0):
    best, best_d = None, max_dist + 1
    for item in dim_labels:
        d = math.hypot(item[1]-mx, item[2]-my)
        if d < best_d: best_d, best = d, item
    return best

# DONG 기둥 전체 (S30-001 + S30-002, 변환 적용)
dong_all_cols = []
for sheet in poc['sheets']:
    sid = sheet['sheet_id']
    if 'PKG' in sid: continue
    if sid == 'S30-001':   tfm_c = lambda x,y: (x, y)
    elif sid == 'S30-002': tfm_c = lambda x,y: (x + DONG_B1F_X_CORR, y)
    else: continue
    for c in sheet['columns']:
        cx, cy = tfm_c(c['abs_cx'], c['abs_cy'])
        dong_all_cols.append((cx, cy))

print(f'  DONG 기둥 총: {len(dong_all_cols)}개')

# 그리드 추론 — 기둥 좌표 클러스터링
def infer_grid(positions, tol=2000.0):
    grid = []
    for p in sorted(positions):
        matched = False
        for i, g in enumerate(grid):
            if abs(p-g) < tol:
                grid[i] = (g+p)/2.0; matched = True; break
        if not matched:
            grid.append(p)
    return sorted(grid)

def snap_idx(val, grid, tol=2000.0):
    best_i, best_d = -1, tol+1
    for i, g in enumerate(grid):
        d = abs(val-g)
        if d < best_d: best_d, best_i = d, i
    return best_i if best_d <= tol else -1

x_grid = infer_grid([p[0] for p in dong_all_cols])
y_grid = infer_grid([p[1] for p in dong_all_cols])
print(f'  그리드: X{len(x_grid)}선 × Y{len(y_grid)}선')

# 그리드별 기둥 인덱스 매핑
col_at: Dict = {}  # (xi,yi) → (cx,cy)
for cx, cy in dong_all_cols:
    xi = snap_idx(cx, x_grid); yi = snap_idx(cy, y_grid)
    if xi >= 0 and yi >= 0:
        col_at[(xi, yi)] = (cx, cy)

sym_cnt_b: Dict[str, int] = {}

def add_grid_beams(floor_label, z_slab_top):
    # 같은 Y 그리드선: 인접 기둥 → X방향 보
    yi_groups: Dict[int, List] = {}
    for (xi, yi), pt in col_at.items():
        yi_groups.setdefault(yi, []).append((xi, pt))
    for yi, pts in yi_groups.items():
        pts.sort(key=lambda p: p[0])
        for i in range(len(pts)-1):
            xi1, (x0,y0) = pts[i]; xi2, (x1,y1) = pts[i+1]
            if xi2 != xi1+1: continue  # 인접한 열만
            dist = math.hypot(x1-x0, y1-y0)
            if dist < 300 or dist > 15000: continue
            mx, my = (x0+x1)/2, (y0+y1)/2
            hit = nearest_dim(mx, my)
            if hit: sym, _, _, bw, bh = hit
            else: bw, bh = 400.0, 900.0; sym = '400X900_EST'
            sym_cnt_b[sym] = sym_cnt_b.get(sym, 0) + 1
            mid = f'{sym}-{floor_label}-DONG-{sym_cnt_b[sym]:04d}'
            s = beam_solid(x0,y0,x1,y1, bw,bh, z_slab_top-bh, z_slab_top-SLAB_T)
            all_members.append(Member(
                id=mid, symbol=sym, mtype='beam_x', zone='DONG', floor=floor_label,
                volume_m3=round((bw*bh*dist)/1e9,4), shape=s,
                extra={'section':f'{int(bw)}x{int(bh)}','span_mm':round(dist)},
            ))
    # 같은 X 그리드선: 인접 기둥 → Y방향 보
    xi_groups: Dict[int, List] = {}
    for (xi, yi), pt in col_at.items():
        xi_groups.setdefault(xi, []).append((yi, pt))
    for xi, pts in xi_groups.items():
        pts.sort(key=lambda p: p[0])
        for i in range(len(pts)-1):
            yi1, (x0,y0) = pts[i]; yi2, (x1,y1) = pts[i+1]
            if yi2 != yi1+1: continue
            dist = math.hypot(x1-x0, y1-y0)
            if dist < 300 or dist > 15000: continue
            mx, my = (x0+x1)/2, (y0+y1)/2
            hit = nearest_dim(mx, my)
            if hit: sym, _, _, bw, bh = hit
            else: bw, bh = 400.0, 900.0; sym = '400X900_EST'
            sym_cnt_b[sym] = sym_cnt_b.get(sym, 0) + 1
            mid = f'{sym}-{floor_label}-DONG-{sym_cnt_b[sym]:04d}'
            s = beam_solid(x0,y0,x1,y1, bw,bh, z_slab_top-bh, z_slab_top-SLAB_T)
            all_members.append(Member(
                id=mid, symbol=sym, mtype='beam_y', zone='DONG', floor=floor_label,
                volume_m3=round((bw*bh*dist)/1e9,4), shape=s,
                extra={'section':f'{int(bw)}x{int(bh)}','span_mm':round(dist)},
            ))

add_grid_beams('B2F', SL_B1F)
add_grid_beams('B1F', TOWER_B1F_TOP)
b_added = sum(1 for m in all_members if 'beam' in m.mtype and m.zone=='DONG')
print(f'  DONG 보: B2F+B1F = {b_added}개')

b_added = sum(1 for m in all_members if 'beam' in m.mtype and m.zone=='DONG')
print(f'  DONG 보 추가: B2F+B1F = {b_added}개')

# FreeCAD 개별 등록
print('\n[FreeCAD 등록]')
fc_doc = FreeCAD.newDocument('v8_poc')
valid = []
for mbr in all_members:
    if mbr.shape is None: continue
    feat = fc_doc.addObject('Part::Feature', mbr.id[:63])
    feat.Shape = mbr.shape
    valid.append(mbr.shape)
fc_doc.recompute()
print(f'  {len(fc_doc.Objects)}개 Part::Feature 등록')

# STEP 출력
print('\n[STEP 출력]')
os.makedirs('output', exist_ok=True)
STEP = 'output/v8_poc.step'
try:
    Part.export(list(fc_doc.Objects), STEP)
    sz = os.path.getsize(STEP)
    if sz < 10_000: raise ValueError(f'{sz}B 불량')
    print(f'  [STEP] {STEP}  ({sz//1024} KB)')
except Exception as e:
    print(f'  fallback: {e}')
    cmpd = Part.makeCompound(valid)
    fa = fc_doc.addObject('Part::Feature', 'all')
    fa.Shape = cmpd; fc_doc.recompute()
    fa.Shape.exportStep(STEP)
    sz = os.path.getsize(STEP)
    print(f'  [STEP fallback] {STEP}  ({sz//1024} KB)')

# BOQ 출력
print('\n[BOQ 산출서]')
export_json(all_members, 'output/v8_boq.json')
export_csv(all_members, 'output/v8_boq.csv')

# 최종 집계
print('\n' + '=' * 65)
type_cnt: Dict[str, int] = {}
for m in all_members:
    type_cnt[m.mtype] = type_cnt.get(m.mtype, 0) + 1
print('부재 집계:')
for t in ['column', 'beam_x', 'beam_y', 'beam', 'slab', 'wall']:
    cnt = type_cnt.get(t, 0)
    if cnt == 0: continue
    vol = sum(m.volume_m3 for m in all_members if m.mtype == t)
    print(f'  {TYPE_KR[t]:7s}: {cnt:4d}개  {vol:9.1f} m³')
total = sum(m.volume_m3 for m in all_members)
print(f'\n  합계: {len(all_members)}부재 / {len(valid)}솔리드 / {total:.1f} m³')

# 심볼별 집계
sym_cnt: Dict[str, int] = {}
for m in all_members:
    sym_cnt[m.symbol] = sym_cnt.get(m.symbol, 0) + 1
print(f'\n  고유 부재 심볼: {len(sym_cnt)}종')
top_syms = sorted(sym_cnt.items(), key=lambda x: -x[1])[:10]
for sym, cnt in top_syms:
    print(f'  {sym:12s}: {cnt:4d}개')
print('=' * 65)
print('[완료] v8 poc 기반 BOQ 빌드')
