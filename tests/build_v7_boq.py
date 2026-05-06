"""
build_v7_boq.py — 부재별 개별 모델링 + BOQ 산출 (v7 최종)
==========================================================
도면 직독 원칙 (도면에 있는 것만 — 추정·생성 없음):
  기둥 위치  → StructuralExtractor d.columns (HATCH/INSERT)
  기둥 이름  → 도면 TEXT 직독 (C1, C2, PC1 등)
  보 위치    → StructuralExtractor d.beams (S-GIRDER LINE) ← 핵심
  보 이름    → 도면 TEXT 직독 (RB1, RG3A, REG13B 등)
  보 치수    → codex_beams_basement.json (S40-151~156 일람표)
  슬라브     → 격자 패널 (4코너 기둥 존재 확인)
  전단벽     → d.shear_walls (A-WALL-RC LINE 페어링)

부재 ID: {도면원래명}-{층}-{구역}-{일련번호}
  예) RB1A-B2F-PKG-0001, C2-B1F-DONG-0012

출력:
  output/v7_boq.step        3D 형상 (개별 Part::Feature)
  output/v7_boq.json        전 부재 목록 + 수량
  output/v7_boq_summary.csv 요약 집계

실행: freecadcmd tests/build_v7_boq.py
"""
import sys, os, math, json, csv, re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict

os.chdir('D:/Git/FreeCAD_4TH')
sys.path.insert(0, 'D:/Git/FreeCAD_4TH')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import Part, FreeCAD
import ezdxf
from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.entity_scanner import iter_all

# ── 확정 치수 (도면 직독 — 추정 없음) ───────────────────────
SL_B2F       = -9050.0
SL_B1F       = -5600.0
SL_1F        =   370.0
PKG_B1F_H    = 4400.0
PKG_B1F_TOP  = SL_B1F + PKG_B1F_H    # -1200mm  방부장 명시
TOWER_B1F_TOP = SL_1F                  # +370mm   도면 직독
SLAB_T_B2F   = 150.0                   # S40-051~057 직독
SLAB_T_B1F   = 150.0                   # S40-061~070 직독

# 기본 보 치수 (codex 미매칭 시 최후 폴백)
DEFAULT_BW, DEFAULT_BH = 400.0, 900.0

# 좌표 통일 (주차장 도면 → 통일계)
TX_PKG, TY_PKG = -425013.0, 3616519.0
def btrans(x, y): return x + TX_PKG, y + TY_PKG

# 도면 경로
DONG_DXF  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
BSMNT_DXF = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'
DONG_CLIP  = (69013, 2241258, 229013, 2401258)
BSMNT_CLIP = (552082.0, -1376738.0, 712082.0, -1216738.0)

# 보 일람표 (codex) 로드
with open('output/codex_beams_basement.json', encoding='utf-8') as f:
    _RAW = json.load(f)
BEAM_CODEX: Dict[str, dict] = {e['symbol']: e for e in _RAW['부재_법전']}
print(f'[codex] 보 일람표: {len(BEAM_CODEX)}종 로드')

# ── 부재명 패턴 ─────────────────────────────────────────────
# 기둥: C1, C2A, AC1, EC2A, PC2(S), ARW1, BW1, W10 등
COL_LABEL_PAT  = re.compile(
    r'^(?:PC|EC|AC|ARW|BW|C|G|SW|LW|W)\d+[A-Za-z]?(?:\([ST]\))?$', re.I)
# 보 심볼: RB1, RG3A, REG13B (지하주차장 일람표 방식)
BEAM_SYM_PAT   = re.compile(r'^R[BG]\d+[A-Za-z]*$|^REG\d+[A-Za-z]*$')
# 보 치수 직독: 400X800, 500x600 (101동 평면도 방식)
BEAM_DIM_PAT   = re.compile(r'^(\d{3,4})[Xx](\d{3,4})$')


# ──────────────────────────────────────────────────────────────
# 부재 데이터 클래스
# ──────────────────────────────────────────────────────────────

@dataclass
class Member:
    id:        str
    symbol:    str     # 도면 원래 이름 (RB1, C2, ...)
    mtype:     str     # column | beam | slab | wall
    zone:      str     # PKG | DONG
    floor:     str     # B2F | B1F
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
    if ht <= 0 or w < 10 or h < 10:
        return None
    s = Part.makeBox(w, h, ht, FreeCAD.Vector(cx - w/2, cy - h/2, zb))
    return s if s.isValid() else None


def prism_solid(pts, zb, zt):
    ht = zt - zb
    if ht <= 0 or len(pts) < 3:
        return None
    vv = [FreeCAD.Vector(x, y, zb) for x, y in pts] + [FreeCAD.Vector(pts[0][0], pts[0][1], zb)]
    try:
        face = Part.makeFace(Part.makePolygon(vv), 'Part::FaceMakerBullseye')
        s = face.extrude(FreeCAD.Vector(0, 0, ht))
        return s if s.isValid() else None
    except Exception:
        return None


def beam_solid(x0, y0, x1, y1, bw, bh, zb, zt):
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy)
    if ln < 100 or zt <= zb:
        return None
    ux, uy = -dy/ln, dx/ln
    pts = [(x0+ux*bw/2, y0+uy*bw/2), (x1+ux*bw/2, y1+uy*bw/2),
           (x1-ux*bw/2, y1-uy*bw/2), (x0-ux*bw/2, y0-uy*bw/2)]
    return prism_solid(pts, zb, zt)


# ──────────────────────────────────────────────────────────────
# 도면 TEXT 라벨 직독
# ──────────────────────────────────────────────────────────────

def extract_labels(dxf_doc, clip,
                   pattern: re.Pattern,
                   transform=None) -> List[Tuple[str, float, float]]:
    """DXF TEXT/MTEXT에서 pattern에 맞는 라벨 추출."""
    msp = dxf_doc.modelspace()
    result = []
    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            raw = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            txt = raw.replace(' ', '').upper()
            if not pattern.match(txt):
                continue
            pos = e.dxf.insert
            px, py = float(pos.x), float(pos.y)
            if clip and not (clip[0] <= px <= clip[2] and clip[1] <= py <= clip[3]):
                continue
            if transform:
                px, py = transform(px, py)
            result.append((txt, px, py))
        except Exception:
            pass
    return result


def extract_beam_dim_labels(dxf_doc, clip,
                             transform=None) -> List[Tuple[str, float, float, float, float]]:
    """
    NNNxNNN 형식 보 치수 TEXT 직독.
    반환: [(symbol, px, py, bw, bh), ...]
    """
    msp = dxf_doc.modelspace()
    result = []
    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            raw = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            txt = raw.replace(' ', '').upper()
            m = BEAM_DIM_PAT.match(txt)
            if not m:
                continue
            pos = e.dxf.insert
            px, py = float(pos.x), float(pos.y)
            if clip and not (clip[0] <= px <= clip[2] and clip[1] <= py <= clip[3]):
                continue
            if transform:
                px, py = transform(px, py)
            result.append((txt, px, py, float(m.group(1)), float(m.group(2))))
        except Exception:
            pass
    return result


def nearest_label(mx, my, labels, max_dist=3500.0):
    """(mx,my)에서 가장 가까운 라벨 반환."""
    best, best_d = None, max_dist + 1
    for item in labels:
        lx, ly = item[1], item[2]
        d = math.hypot(lx - mx, ly - my)
        if d < best_d:
            best_d, best = d, item
    return best   # None 또는 tuple


def beam_dims_from_codex(symbol) -> Tuple[float, float]:
    """codex에서 보 폭·높이 조회. 없으면 기본값."""
    if symbol and symbol in BEAM_CODEX:
        e = BEAM_CODEX[symbol]
        return float(e['width']), float(e['height'])
    return DEFAULT_BW, DEFAULT_BH


# ──────────────────────────────────────────────────────────────
# 그리드 추론 (슬라브 패널용)
# ──────────────────────────────────────────────────────────────

def infer_grid(positions: List[float], tol=1500.0) -> List[float]:
    grid = []
    for p in sorted(positions):
        matched = False
        for i, g in enumerate(grid):
            if abs(p - g) < tol:
                grid[i] = (g + p) / 2.0
                matched = True
                break
        if not matched:
            grid.append(p)
    return sorted(grid)


def snap_idx(val, grid, tol=1500.0):
    best_i, best_d = -1, tol + 1
    for i, g in enumerate(grid):
        d = abs(val - g)
        if d < best_d:
            best_d, best_i = d, i
    return best_i if best_d <= tol else -1


# ──────────────────────────────────────────────────────────────
# 기둥 생성 (도면 TEXT 이름 직독)
# ──────────────────────────────────────────────────────────────

def build_columns(raw_cols, zone, floor, z_bot, z_top,
                  col_labels) -> List[Member]:
    slab_t = SLAB_T_B2F if floor == 'B2F' else SLAB_T_B1F
    z_col_top = z_top - slab_t
    height = z_col_top - z_bot
    members = []
    sym_cnt: Dict[str, int] = {}

    for (cx, cy, cw, ch) in raw_cols:
        symbol = nearest_label(cx, cy, col_labels, max_dist=2500)
        if not symbol:
            symbol = 'C'

        # 같은 심볼 내 일련번호
        sym_cnt[symbol] = sym_cnt.get(symbol, 0) + 1
        mid = f'{symbol}-{floor}-{zone}-{sym_cnt[symbol]:04d}'

        s = box_solid(cx, cy, z_bot, z_col_top, cw, ch)
        vol = (abs(cw) * abs(ch) * height) / 1e9 if height > 0 else 0.0

        members.append(Member(
            id=mid, symbol=symbol, mtype='column',
            zone=zone, floor=floor,
            volume_m3=round(vol, 4), shape=s,
            extra={'section': f'{int(abs(cw))}x{int(abs(ch))}',
                   'height_mm': round(height),
                   'cx': round(cx), 'cy': round(cy)},
        ))
    return members


# ──────────────────────────────────────────────────────────────
# 보 생성 — 도면 LINE 직독 (d.beams) + TEXT 이름 + codex 치수
# ──────────────────────────────────────────────────────────────

def build_beams(beam_lines, zone, floor, z_slab_top,
                beam_dim_labels, transform=None) -> List[Member]:
    """
    ▶ beam_lines: d.beams — S-GIRDER LINE 좌표 (도면 직독)
    ▶ beam_dim_labels: extract_beam_dim_labels() 결과
                       [(symbol, px, py, bw, bh), ...]
                       - 101동: '400X800' TEXT → bw=400, bh=800 직독
                       - 주차장: 없을 수 있음 → codex 폴백
    ▶ 보 치수: TEXT 직독 > codex > 기본값 우선순위
    """
    slab_t = SLAB_T_B2F if floor == 'B2F' else SLAB_T_B1F
    members = []
    sym_cnt: Dict[str, int] = {}

    for bm in beam_lines:
        if transform:
            x0, y0 = transform(bm.x0, bm.y0)
            x1, y1 = transform(bm.x1, bm.y1)
        else:
            x0, y0 = bm.x0, bm.y0
            x1, y1 = bm.x1, bm.y1

        dist = math.hypot(x1-x0, y1-y0)
        if dist < 300:
            continue

        # 보 중심점 → nearest 치수 TEXT
        mx, my = (x0+x1)/2, (y0+y1)/2
        hit = nearest_label(mx, my, beam_dim_labels, max_dist=4000)

        if hit:
            symbol, _, _, bw, bh = hit   # NNNxNNN 직독
        else:
            # 폴백: 스팬 기반 추정
            bw = 600.0 if dist > 7000 else 400.0
            bh = 900.0
            symbol = f'{int(bw)}X{int(bh)}_EST'

        sym_cnt[symbol] = sym_cnt.get(symbol, 0) + 1
        mid = f'{symbol}-{floor}-{zone}-{sym_cnt[symbol]:04d}'

        z_beam_bot = z_slab_top - bh
        z_beam_top = z_slab_top - slab_t

        s = beam_solid(x0, y0, x1, y1, bw, bh, z_beam_bot, z_beam_top)
        vol = (bw * bh * dist) / 1e9

        ang = abs(math.degrees(math.atan2(y1-y0, x1-x0))) % 180
        mtype = 'beam_y' if (90 - 15 < ang < 90 + 15) else 'beam_x'

        members.append(Member(
            id=mid, symbol=symbol, mtype=mtype,
            zone=zone, floor=floor,
            volume_m3=round(vol, 4), shape=s,
            extra={'section': f'{int(bw)}x{int(bh)}',
                   'span_mm': round(dist),
                   'x0': round(x0), 'y0': round(y0),
                   'x1': round(x1), 'y1': round(y1)},
        ))
    return members


# ──────────────────────────────────────────────────────────────
# 슬라브 생성 (격자 패널 — 4코너 기둥 존재 확인)
# ──────────────────────────────────────────────────────────────

def build_slabs(col_positions, zone, floor, z_slab_bot, z_slab_top,
                slab_t, max_span=11000.0) -> List[Member]:
    x_grid = infer_grid([p[0] for p in col_positions])
    y_grid = infer_grid([p[1] for p in col_positions])

    col_set = set()
    for (x, y) in col_positions:
        xi = snap_idx(x, x_grid)
        yi = snap_idx(y, y_grid)
        if xi >= 0 and yi >= 0:
            col_set.add((xi, yi))

    members = []
    seq = 0
    for xi in range(len(x_grid) - 1):
        for yi in range(len(y_grid) - 1):
            if not all(c in col_set for c in
                       [(xi, yi), (xi+1, yi), (xi, yi+1), (xi+1, yi+1)]):
                continue
            xa, xb = x_grid[xi], x_grid[xi+1]
            ya, yb = y_grid[yi], y_grid[yi+1]
            if abs(xb-xa) > max_span or abs(yb-ya) > max_span:
                continue

            pts = [(xa, ya), (xb, ya), (xb, yb), (xa, yb)]
            s = prism_solid(pts, z_slab_bot, z_slab_top)
            area = (abs(xb-xa) * abs(yb-ya)) / 1e6
            vol = area * slab_t / 1000.0
            seq += 1
            mid = f'SL-{floor}-{zone}-{seq:04d}'
            members.append(Member(
                id=mid, symbol='SL', mtype='slab',
                zone=zone, floor=floor,
                volume_m3=round(vol, 4), shape=s,
                extra={'thickness_mm': slab_t,
                       'area_m2': round(area, 2),
                       'grid': f'X{xi+1}X{xi+2}_Y{yi+1}Y{yi+2}'},
            ))
    return members


# ──────────────────────────────────────────────────────────────
# 전단벽 생성
# ──────────────────────────────────────────────────────────────

def build_walls(raw_walls, zone, floor, z_bot, z_top, slab_t,
                transform=None, limit=80) -> List[Member]:
    z_wall_top = z_top - slab_t
    height = z_wall_top - z_bot
    members = []
    for seq, wp in enumerate(raw_walls):
        if seq >= limit: break
        if wp.thickness < 150 or wp.overlap_length < 1500: continue
        p1, p2 = wp.centerline_p1, wp.centerline_p2
        x0, y0 = transform(*p1) if transform else p1
        x1, y1 = transform(*p2) if transform else p2
        dx, dy = x1-x0, y1-y0
        ln = math.hypot(dx, dy)
        if ln < 100: continue
        ux, uy = -dy/ln, dx/ln
        t = wp.thickness
        pts = [(x0+ux*t/2, y0+uy*t/2), (x1+ux*t/2, y1+uy*t/2),
               (x1-ux*t/2, y1-uy*t/2), (x0-ux*t/2, y0-uy*t/2)]
        s = prism_solid(pts, z_bot, z_wall_top)
        vol = (t * ln * height) / 1e9
        members.append(Member(
            id=f'SW-{floor}-{zone}-{seq+1:04d}',
            symbol='SW', mtype='wall',
            zone=zone, floor=floor,
            volume_m3=round(vol, 4), shape=s,
            extra={'thickness_mm': round(t), 'length_mm': round(ln),
                   'height_mm': round(height)},
        ))
    return members


# ──────────────────────────────────────────────────────────────
# BOQ 출력
# ──────────────────────────────────────────────────────────────

TYPE_KR = {'column':'기둥', 'beam_x':'보(X)', 'beam_y':'보(Y)',
           'beam':'보', 'slab':'슬라브', 'wall':'전단벽'}


def export_json(members, path):
    by_type = {}
    by_floor = {}
    for m in members:
        t, fl = m.mtype, m.floor
        by_type.setdefault(t, {'count': 0, 'vol_m3': 0.0})
        by_type[t]['count'] += 1
        by_type[t]['vol_m3'] = round(by_type[t]['vol_m3'] + m.volume_m3, 3)
        by_floor.setdefault(fl, {'count': 0, 'vol_m3': 0.0})
        by_floor[fl]['count'] += 1
        by_floor[fl]['vol_m3'] = round(by_floor[fl]['vol_m3'] + m.volume_m3, 3)

    total = round(sum(m.volume_m3 for m in members), 3)
    out = {
        'project': '에코델타 24BL 지하주차장+101동',
        'generated': '2026-05-06',
        'total': len(members),
        'total_volume_m3': total,
        'by_type': by_type,
        'by_floor': by_floor,
        'members': [m.to_dict() for m in members],
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'  [JSON] {path}  ({len(members)}건, {total:.1f} m³)')


def export_csv(members, path):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['부재ID', '도면부재명', '유형', '구역', '층', '치수(mm)',
                    '스팬/높이(mm)', '면적(m²)', '체적(m³)'])
        for m in members:
            d = m.extra
            tkr = TYPE_KR.get(m.mtype, m.mtype)
            sec = d.get('section', '')
            dim = d.get('span_mm', d.get('height_mm', d.get('length_mm', '')))
            area = d.get('area_m2', '')
            w.writerow([m.id, m.symbol, tkr, m.zone, m.floor,
                        sec, dim, area, m.volume_m3])
    print(f'  [CSV]  {path}')


# ──────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────

print('=' * 65)
print('v7 부재별 개별 모델링 + BOQ (도면 직독 — d.beams 사용)')
print('=' * 65)

# ── 1. 도면 파싱 ─────────────────────────────────────────────
print('\n[1] 도면 파싱...')
ext = StructuralExtractor(min_col_size=100, max_col_size=3000,
                          min_slab_area_m2=50)

doc_b = ezdxf.readfile(BSMNT_DXF, encoding='cp949')
d_pkg = ext.extract(doc_b, clip=BSMNT_CLIP)
print(f'  주차장: 기둥{len(d_pkg.columns)}  보LINE{len(d_pkg.beams)}  '
      f'전단벽{len(d_pkg.shear_walls)}')

doc_d = ezdxf.readfile(DONG_DXF, encoding='cp949')
d_dong = ext.extract(doc_d, clip=DONG_CLIP)
print(f'  101동:  기둥{len(d_dong.columns)}  보LINE{len(d_dong.beams)}  '
      f'전단벽{len(d_dong.shear_walls)}')

# ── 2. 부재명 TEXT 직독 ──────────────────────────────────────
print('\n[2] 도면 부재명 TEXT 직독...')

# 기둥 이름 (C1, PC2(S), EC1, ARW1...)
pkg_col_lbl  = extract_labels(doc_b, BSMNT_CLIP, COL_LABEL_PAT, transform=btrans)
dong_col_lbl = extract_labels(doc_d, DONG_CLIP,  COL_LABEL_PAT)
print(f'  주차장 기둥라벨:{len(pkg_col_lbl)}  예:{[l[0] for l in pkg_col_lbl[:5]]}')
print(f'  101동  기둥라벨:{len(dong_col_lbl)}  예:{[l[0] for l in dong_col_lbl[:5]]}')

# 보 치수 직독 (NNNxNNN 방식 — 101동)
# 주차장 도면에는 없음 → 빈 리스트 → 기본값 사용
pkg_beam_dim  = extract_beam_dim_labels(doc_b, BSMNT_CLIP, transform=btrans)
dong_beam_dim = extract_beam_dim_labels(doc_d, DONG_CLIP)
print(f'  주차장 보치수TEXT:{len(pkg_beam_dim)}')
print(f'  101동  보치수TEXT:{len(dong_beam_dim)}  예:{[l[0] for l in dong_beam_dim[:5]]}')

# ── 3. 부재 생성 ─────────────────────────────────────────────
print('\n[3] 부재별 개별 솔리드 생성...')
all_members: List[Member] = []

# 주차장 좌표 변환
pkg_cols = [(btrans(c.cx, c.cy)[0], btrans(c.cx, c.cy)[1],
             abs(c.w), abs(c.h)) for c in d_pkg.columns]
pkg_xy   = [(cx, cy) for cx, cy, _, _ in pkg_cols]

# ─── 주차장 B2F ──────────────────────────────────────────────
print('  [B2F 주차장]')
m = build_columns(pkg_cols, 'PKG', 'B2F', SL_B2F, SL_B1F, pkg_col_lbl)
all_members.extend(m); print(f'    기둥: {len(m)}')

m = build_beams(d_pkg.beams, 'PKG', 'B2F', SL_B1F,
                pkg_beam_dim, transform=btrans)
all_members.extend(m); print(f'    보: {len(m)}')

m = build_slabs(pkg_xy, 'PKG', 'B2F',
                SL_B1F - SLAB_T_B2F, SL_B1F, SLAB_T_B2F)
all_members.extend(m); print(f'    슬라브 패널: {len(m)}')

# ─── 주차장 B1F ──────────────────────────────────────────────
print('  [B1F 주차장]')
m = build_columns(pkg_cols, 'PKG', 'B1F', SL_B1F, PKG_B1F_TOP, pkg_col_lbl)
all_members.extend(m); print(f'    기둥: {len(m)}')

m = build_beams(d_pkg.beams, 'PKG', 'B1F', PKG_B1F_TOP,
                pkg_beam_dim, transform=btrans)
all_members.extend(m); print(f'    보: {len(m)}')

m = build_slabs(pkg_xy, 'PKG', 'B1F',
                PKG_B1F_TOP - SLAB_T_B1F, PKG_B1F_TOP, SLAB_T_B1F)
all_members.extend(m); print(f'    슬라브 패널: {len(m)}')

# ─── 주차장 전단벽 ───────────────────────────────────────────
m = build_walls(d_pkg.shear_walls, 'PKG', 'B2F',
                SL_B2F, SL_B1F, SLAB_T_B2F, transform=btrans)
all_members.extend(m); print(f'  전단벽: {len(m)}')

# 101동
dong_cols = [(c.cx, c.cy, abs(c.w), abs(c.h)) for c in d_dong.columns]
dong_xy   = [(c.cx, c.cy) for c in d_dong.columns]

# ─── 101동 B2F ───────────────────────────────────────────────
print('  [B2F 101동]')
m = build_columns(dong_cols, 'DONG', 'B2F', SL_B2F, SL_B1F, dong_col_lbl)
all_members.extend(m); print(f'    기둥: {len(m)}')

m = build_beams(d_dong.beams, 'DONG', 'B2F', SL_B1F, dong_beam_dim)
all_members.extend(m); print(f'    보: {len(m)}')

m = build_slabs(dong_xy, 'DONG', 'B2F',
                SL_B1F - SLAB_T_B2F, SL_B1F, SLAB_T_B2F)
all_members.extend(m); print(f'    슬라브 패널: {len(m)}')

# ─── 101동 B1F ───────────────────────────────────────────────
print('  [B1F 101동]')
m = build_columns(dong_cols, 'DONG', 'B1F', SL_B1F, TOWER_B1F_TOP, dong_col_lbl)
all_members.extend(m); print(f'    기둥: {len(m)}')

m = build_beams(d_dong.beams, 'DONG', 'B1F', TOWER_B1F_TOP, dong_beam_dim)
all_members.extend(m); print(f'    보: {len(m)}')

m = build_slabs(dong_xy, 'DONG', 'B1F',
                TOWER_B1F_TOP - SLAB_T_B1F, TOWER_B1F_TOP, SLAB_T_B1F)
all_members.extend(m); print(f'    슬라브 패널: {len(m)}')

# ── 4. FreeCAD 개별 Part::Feature 등록 ──────────────────────
print('\n[4] FreeCAD 등록...')
fc_doc = FreeCAD.newDocument('v7_boq')
valid_shapes = []

for mbr in all_members:
    if mbr.shape is None:
        continue
    lbl = mbr.id[:63]
    feat = fc_doc.addObject('Part::Feature', lbl)
    feat.Shape = mbr.shape
    valid_shapes.append(mbr.shape)

fc_doc.recompute()
print(f'  등록: {len(fc_doc.Objects)}개 부재')

# ── 5. STEP 출력 ─────────────────────────────────────────────
print('\n[5] STEP 출력...')
os.makedirs('output', exist_ok=True)
STEP = 'output/v7_boq.step'

try:
    Part.export(list(fc_doc.Objects), STEP)
    sz = os.path.getsize(STEP)
    if sz < 10_000:
        raise ValueError(f'파일 크기 불량: {sz}B')
    print(f'  [STEP] {STEP}  ({sz//1024} KB)')
except Exception as e:
    print(f'  Part.export 실패({e}) → compound fallback')
    cmpd = Part.makeCompound(valid_shapes)
    fa = fc_doc.addObject('Part::Feature', 'all')
    fa.Shape = cmpd
    fc_doc.recompute()
    fa.Shape.exportStep(STEP)
    sz = os.path.getsize(STEP)
    print(f'  [STEP fallback] {STEP}  ({sz//1024} KB)')

# ── 6. BOQ 출력 ──────────────────────────────────────────────
print('\n[6] BOQ 산출서...')
export_json(all_members, 'output/v7_boq.json')
export_csv(all_members, 'output/v7_boq_summary.csv')

# ── 최종 집계 ────────────────────────────────────────────────
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
print(f'\n  합계: {len(all_members)}부재 / {len(valid_shapes)}솔리드 / {total:.1f} m³')

# 도면 TEXT 매칭 통계
matched = sum(1 for m in all_members
              if not m.symbol.endswith('_EST') and m.symbol not in ('C','SW','SL'))
print(f'  도면 TEXT 매칭: {matched}/{len(all_members)} 부재')
print('=' * 65)
print('[완료] v7 부재별 개별 + BOQ 산출 완료')
