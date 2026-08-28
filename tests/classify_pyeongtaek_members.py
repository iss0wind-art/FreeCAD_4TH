import ezdxf
import sys
import re
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.dxf_parser.entity_scanner import iter_all

# ── 경로 ────────────────────────────────────────────────────
DXF_PLAN = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S21-001~012 구조평면도.dxf"
COL_SPECS_JSON = Path("output/pyeongtaek_column_specs.json")
BEAM_SPECS_JSON = Path("output/pyeongtaek_beam_specs.json")
OUT_MEMBERS_JSON = Path("output/pyeongtaek_members_accumulated.json")

# ── 시트 및 층 정의 ──────────────────────────────────────────
SHEET_PITCH = 420500.0

FLOORS = {
    1: 'B1F',
    2: '1F',
    3: '2F',
    4: '3F',
    5: '4F',
    6: '5F',
    7: '6F',
    8: '7F',
    9: '8F',
    10: '9F',
    11: '10F',
    12: '지붕층'
}

# 층고 높이 (SL 절대 표고 mm)
FLOOR_Z = {
    'B1F': {'z_bot': 16850.0, 'z_top': 23000.0},
    '1F':  {'z_bot': 23000.0, 'z_top': 30000.0},
    '2F':  {'z_bot': 30000.0, 'z_top': 37000.0},
    '3F':  {'z_bot': 37000.0, 'z_top': 44000.0},
    '4F':  {'z_bot': 44000.0, 'z_top': 51000.0},
    '5F':  {'z_bot': 51000.0, 'z_top': 58000.0},
    '6F':  {'z_bot': 58000.0, 'z_top': 63100.0},
    '7F':  {'z_bot': 63100.0, 'z_top': 68200.0},
    '8F':  {'z_bot': 68200.0, 'z_top': 73300.0},
    '9F':  {'z_bot': 73300.0, 'z_top': 78700.0},
    '10F': {'z_bot': 78700.0, 'z_top': 83800.0},
    '지붕층': {'z_bot': 83800.0, 'z_top': 87600.0} # 지붕층 위는 옥탑지붕 표고
}

# ── 기둥 및 보 레이어 정의 ─────────────────────────────────────
# 기둥 단면: S-DEF-IDEN 또는 S-FLOR-BYND 레이어 아래 폴리라인들
# 보 라인: S-FLOR-GIRD 레이어 아래 라인들
COL_LAYERS = {'S-DEF-IDEN', 'S-FLOR-BYND'}
BEAM_LAYERS = {'S-FLOR-GIRD'}
TEXT_LAYERS = {'S-ANNO-TEXT'}

def centroid(pts: List[Tuple[float, float]]) -> Tuple[float, float]:
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return cx, cy

def main():
    print("Reading specifications...")
    if not COL_SPECS_JSON.exists():
        print(f"Error: {COL_SPECS_JSON} does not exist.")
        return
    with open(COL_SPECS_JSON, encoding='utf-8') as f:
        col_specs = json.load(f)
        
    print("Reading dxf plan...")
    doc = ezdxf.readfile(DXF_PLAN, encoding='utf-8', errors='replace')
    msp = doc.modelspace()
    
    print("Collecting entities...")
    raw_texts = []
    col_polys = []
    beam_lines = []
    
    for e in iter_all(msp):
        layer = e.dxf.layer
        etype = e.dxftype()
        
        if etype in ('TEXT', 'MTEXT'):
            txt = (e.dxf.text if etype == 'TEXT' else e.text).strip()
            pos = getattr(e.dxf, 'insert', None)
            if pos and txt:
                raw_texts.append((txt, pos.x, pos.y))
                
        elif etype == 'LWPOLYLINE' and layer in COL_LAYERS:
            pts = [(p[0], p[1]) for p in e.get_points()]
            if len(pts) >= 3:
                cx, cy = centroid(pts)
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                w = max(xs) - min(xs)
                h = max(ys) - min(ys)
                # 닫힌 기둥 형태인지 체크 (400mm ~ 2500mm 단면폭)
                if 400 <= w <= 2500 and 400 <= h <= 2500:
                    col_polys.append({
                        'cx': cx, 'cy': cy, 'w': w, 'h': h, 'pts': pts, 'layer': layer
                    })
                    
        elif etype == 'LINE' and layer in BEAM_LAYERS:
            s, en = e.dxf.start, e.dxf.end
            L = math.hypot(en.x - s.x, en.y - s.y)
            if L >= 300: # 최소 300mm 이상
                dx = en.x - s.x
                dy = en.y - s.y
                ang = math.degrees(math.atan2(dy, dx)) % 180
                beam_lines.append({
                    'x1': s.x, 'y1': s.y, 'x2': en.x, 'y2': en.y,
                    'cx': (s.x + en.x)/2, 'cy': (s.y + en.y)/2,
                    'L': L, 'angle': ang, 'layer': layer
                })

    print(f"Collected: Texts={len(raw_texts)}, Column Polys={len(col_polys)}, Beam Lines={len(beam_lines)}")
    
    # ── 부재 매칭 및 층 정렬 ───────────────────────────────
    members = []
    counters = {}
    
    def next_id(mtype: str, floor: str) -> str:
        key = f"{mtype}-{floor}"
        counters[key] = counters.get(key, 0) + 1
        return f"{mtype}-PT-{floor}-{counters[key]:04d}"
        
    # 기둥 번호 매칭 정규식 (C1, C2, SC1, SRC1 등)
    col_pattern = re.compile(r'^([A-Z]*C\d+[A-Z]*)$', re.IGNORECASE)
    
    print("Processing columns (label-centric matching)...")
    col_count = 0
    # 1. 기둥 라벨 필터링
    col_labels = []
    for txt, tx, ty in raw_texts:
        if col_pattern.match(txt):
            col_labels.append((txt.upper(), tx, ty))
            
    # 2. 각 라벨 기준 가장 가까운 폴리라인 매칭 (1:1)
    matched_poly_ids = set() # 중복 매칭 방지
    for label, lx, ly in col_labels:
        sheet_idx = int(math.floor(lx / SHEET_PITCH)) + 1
        floor = FLOORS.get(sheet_idx)
        if not floor:
            continue
            
        zb = FLOOR_Z[floor]['z_bot']
        zt = FLOOR_Z[floor]['z_top']
        
        best_poly = None
        best_dist = 1500.0 # 1.5m 이내
        
        for idx, p in enumerate(col_polys):
            if idx in matched_poly_ids:
                continue
            d = math.hypot(p['cx'] - lx, p['cy'] - ly)
            if d < best_dist:
                best_dist = d
                best_poly = (idx, p)
                
        if best_poly:
            pidx, p = best_poly
            matched_poly_ids.add(pidx)
            
            cx, cy = p['cx'], p['cy']
            ax = cx - SHEET_PITCH * (sheet_idx - 1)
            ay = cy
            
            # 기둥 스펙 조회 (단면 사이즈 결정)
            sec = f"{round(p['w'])}x{round(p['h'])}"
            specs = col_specs.get(label, [])
            matched_spec = None
            for sp in specs:
                sp_fl = sp.get('floor', '')
                if floor in sp_fl or ('지하1' in sp_fl and floor == 'B1F') or ('지상1' in sp_fl and floor == '1F'):
                    matched_spec = sp.get('size')
                    break
            if matched_spec:
                sec = matched_spec
                
            members.append({
                'id': next_id('COL', floor),
                'type': 'COLUMN',
                'floor': floor,
                'source': 'PT_PLAN',
                'x': round(cx, 1), 'y': round(cy, 1),
                'ax': round(ax, 1), 'ay': round(ay, 1),
                'z_bot': zb, 'z_top': zt,
                'section': sec,
                'symbol': label,
                'layer': p['layer']
            })
            col_count += 1
            
    print(f"Processed columns: {col_count} matching columns found.")
    
    # 보 라벨 매칭 정규식 (G1, RG1, B1, CG1 등)
    beam_pattern = re.compile(r'\b(R?[GBC][GBC]?\d+[A-Z]?)\b', re.IGNORECASE)
    
    print("Processing beams...")
    beam_count = 0
    for b in beam_lines:
        cx, cy = b['cx'], b['cy']
        sheet_idx = int(math.floor(cx / SHEET_PITCH)) + 1
        floor = FLOORS.get(sheet_idx)
        if not floor:
            continue
            
        zb = FLOOR_Z[floor]['z_bot']
        zt = FLOOR_Z[floor]['z_top']
        
        ax = cx - SHEET_PITCH * (sheet_idx - 1)
        ay = cy
        
        # 보 라벨 매칭 (근처 ±2000mm 이내 TEXT)
        beam_name = "NOBEAM"
        best_dist = 2000.0
        for txt, tx, ty in raw_texts:
            if beam_pattern.match(txt):
                d = math.hypot(tx - cx, ty - cy)
                if d < best_dist:
                    best_dist = d
                    beam_name = txt.upper()
                    
        members.append({
            'id': next_id('BM', floor),
            'type': 'BEAM',
            'floor': floor,
            'source': 'PT_PLAN',
            'x': round(cx, 1), 'y': round(cy, 1),
            'ax': round(ax, 1), 'ay': round(ay, 1),
            'z_bot': zb, 'z_top': zt,
            'length_mm': round(b['L'], 1),
            'angle_deg': round(b['angle'], 1),
            'section': "400x900",
            'symbol': beam_name,
            'layer': b['layer']
        })
        beam_count += 1
        
    print(f"Processed beams: {beam_count} matching beams found.")
    
    # ── 최종 저장 ──────────────────────────────────────────────
    OUT_MEMBERS_JSON.parent.mkdir(exist_ok=True)
    
    by_type = {}
    for m in members:
        by_type[m['type']] = by_type.get(m['type'], 0) + 1
        
    data = {
        'meta': {
            'total': len(members),
            'by_type': by_type,
            'last_updated': Path(DXF_PLAN).stat().st_mtime
        },
        'members': members
    }
    
    with open(OUT_MEMBERS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"\n[성공] 평택 고덕 부재 추출 완료 -> {OUT_MEMBERS_JSON} ({len(members)}건)")
    for t, cnt in by_type.items():
        print(f"  - {t}: {cnt}개")

if __name__ == "__main__":
    main()
