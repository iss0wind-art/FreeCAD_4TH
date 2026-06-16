from __future__ import annotations
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
import ezdxf
from core.dxf_parser.entity_scanner import iter_clip, iter_all
from core.dxf_parser.structural_filter import is_structural, is_structural_block, _STRUCTURAL
from core.dxf_parser.full_extractor import _parse_section, _shoelace_area, _in_clip
from core.line_pairing import LineSeg, WallPair

# ─────────────────────────────────────────────────────────────
# 1. 정규식 패턴
# ─────────────────────────────────────────────────────────────
_BEAM_LAYER = re.compile(r'(S[-_]GIRDER|S[-_]BEAM|S[-_]PC[-_]GIRDER|00[-_]BEAM|00[-_]APT\)?BEAM|GIRDER|PC[-_]GIRDER|구조.*보)', re.IGNORECASE)
_SHEAR_LAYER = re.compile(r'(00[-_]SHEAR|SHEAR[-_]WALL|A[-_]WALL[-_]RC|S[-_]WALL(?![-_]SYMBOL)|전단벽|CORE[-_]WALL|구조.*벽)', re.IGNORECASE)
_SLAB_LAYER = re.compile(r'(S[-_]PC[-_]SLAB|S[-_]SLAB|00[-_]SLAB|SLAB|S[-_]SL|00[-_]S[-_]L|구조.*슬래브)', re.IGNORECASE)
_OUTLINE_LAYER = re.compile(r'(OUTLINE|A[-_]HAT|00[-_]OUTLINE|구조.*외곽)', re.IGNORECASE)
_COL_LAYER = re.compile(r'(00[-_]COLUMN|S[-_]기둥|S[-_]COL|STRUCT[-_]COL|COL(?!OR)|柱|구조.*기둥)', re.IGNORECASE)
_SLAB_LABEL_PAT = re.compile(r'(\d?S\d[A-Z]?|T\s*[=]?\s*\d{2,3}|THK\s*\d{2,3}|\(\d{3}\))', re.IGNORECASE)

# [수동 덧방 / 바이패스 레이어 패턴]
_ADD_COL_LAYER = re.compile(r'(ADD[-_]COL|덧방[-_]기둥)', re.IGNORECASE)
_ADD_BEAM_LAYER = re.compile(r'(ADD[-_]BEAM|덧방[-_]보)', re.IGNORECASE)
_ADD_WALL_LAYER = re.compile(r'(ADD[-_]WALL|덧방[-_]벽체)', re.IGNORECASE)
_ADD_SLAB_LAYER = re.compile(r'(ADD[-_]SLAB|덧방[-_]슬라브)', re.IGNORECASE)

# ─────────────────────────────────────────────────────────────
# 2. 자료구조
# ─────────────────────────────────────────────────────────────
@dataclass
class ColumnPrim:
    cx: float; cy: float; w: float; h: float; rotation: float = 0.0
    symbol: str = "NOCOL"; source: str = ""; block_name: str = ""; layer: str = ""
    bypass_filter: bool = False

@dataclass
class SlabOutline:
    pts: List[Tuple[float, float]]; area_m2: float; symbol: str = "NOSLAB"; layer: str = ""
    bypass_filter: bool = False

@dataclass
class BeamLine:
    x0: float; y0: float; x1: float; y1: float; layer: str = ''
    width: float = 400.0; height: float = 700.0; symbol: str = "NOBEAM"; volume_m3: float = 0.0
    bypass_filter: bool = False
    @property
    def length(self) -> float: return math.hypot(self.x1-self.x0, self.y1-self.y0)

@dataclass
class StructuralData:
    columns: List[ColumnPrim] = field(default_factory=list)
    beams: List[BeamLine] = field(default_factory=list)
    slab_outlines: List[SlabOutline] = field(default_factory=list)
    shear_walls: List[WallPair] = field(default_factory=list)

# ─────────────────────────────────────────────────────────────
# 3. 추출기 엔진 (슈퍼 전파 및 폐합 엔진)
# ─────────────────────────────────────────────────────────────
class StructuralExtractor:
    def __init__(self, min_col_size=100.0, max_col_size=2500.0, min_slab_area_m2=10.0, **kwargs):
        self.min_col = min_col_size; self.max_col = max_col_size
        self.min_slab = min_slab_area_m2 * 1_000_000; self.min_beam = 500.0

    def extract(self, doc, clip=None, grid=None, **kwargs) -> StructuralData:
        result = StructuralData(); msp = doc.modelspace(); text_entities = []
        seen_cols = set(); col_lines = []; beam_lines = []; wall_lines = []
        slab_segments = []
        
        for idx, e in enumerate(iter_clip(msp, clip)):
            t = e.dxftype(); layer = getattr(e.dxf, 'layer', '0')
            if t in ('TEXT', 'MTEXT'):
                txt = e.plain_text() if t == 'MTEXT' else e.dxf.text
                if _in_clip(e.dxf.insert.x, e.dxf.insert.y, clip): text_entities.append((e.dxf.insert.x, e.dxf.insert.y, txt))
            
            # --- [수동 덧방 / 바이패스 처리 분기] ---
            if _ADD_COL_LAYER.search(layer):
                if t == 'INSERT':
                    col = self._col_from_insert(e, clip, seen_cols, layer)
                    if col:
                        col.bypass_filter = True
                        result.columns.append(col)
                elif t == 'LWPOLYLINE':
                    col = self._col_from_hatch_pts(e, clip, seen_cols, layer)
                    if col:
                        col.bypass_filter = True
                        result.columns.append(col)
                continue
            
            elif _ADD_BEAM_LAYER.search(layer):
                if t == 'LINE':
                    s, en = e.dxf.start, e.dxf.end
                    b_line = BeamLine(x0=s.x, y0=s.y, x1=en.x, y1=en.y, layer=layer, bypass_filter=True, symbol="ADD_BEAM")
                    result.beams.append(b_line)
                elif t == 'LWPOLYLINE':
                    pts = e.get_points()
                    for i in range(len(pts)-1):
                        b_line = BeamLine(x0=pts[i][0], y0=pts[i][1], x1=pts[i+1][0], y1=pts[i+1][1], layer=layer, bypass_filter=True, symbol="ADD_BEAM")
                        result.beams.append(b_line)
                continue
                
            elif _ADD_WALL_LAYER.search(layer):
                # 덧방 벽체는 단선을 200mm 두께 벽체로 즉시 빌드
                if t == 'LINE':
                    s, en = e.dxf.start, e.dxf.end
                    w_pair = WallPair(line_a_id=idx, line_b_id=-1, distance=200.0, overlap_length=math.hypot(en.x-s.x, en.y-s.y),
                                      angle=math.atan2(en.y-s.y, en.x-s.x), centerline_p1=(s.x, s.y), centerline_p2=(en.x, en.y),
                                      confidence=1.0, bypass_filter=True)
                    result.shear_walls.append(w_pair)
                elif t == 'LWPOLYLINE':
                    pts = e.get_points()
                    for i in range(len(pts)-1):
                        w_pair = WallPair(line_a_id=idx*100+i, line_b_id=-1, distance=200.0, overlap_length=math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]),
                                          angle=math.atan2(pts[i+1][1]-pts[i][1], pts[i+1][0]-pts[i][0]), centerline_p1=(pts[i][0], pts[i][1]), centerline_p2=(pts[i+1][0], pts[i+1][1]),
                                          confidence=1.0, bypass_filter=True)
                        result.shear_walls.append(w_pair)
                continue

            elif _ADD_SLAB_LAYER.search(layer):
                if t == 'LWPOLYLINE':
                    pts = [(p[0], p[1]) for p in e.get_points()]; area = _shoelace_area(pts)
                    result.slab_outlines.append(SlabOutline(pts=pts, area_m2=area/1e6, symbol="ADD_SLAB", layer=layer, bypass_filter=True))
                continue
            
            # --- [기존 자동 추출 로직] ---
            if t == 'INSERT' and _COL_LAYER.search(layer):
                col = self._col_from_insert(e, clip, seen_cols, layer)
                if col: result.columns.append(col)
            elif t == 'LWPOLYLINE':
                if _COL_LAYER.search(layer):
                    col = self._col_from_hatch_pts(e, clip, seen_cols, layer)
                    if col: result.columns.append(col)
                elif _BEAM_LAYER.search(layer):
                    pts = e.get_points()
                    for i in range(len(pts)-1): beam_lines.append(LineSeg(p1=pts[i], p2=pts[i+1], layer=layer))
                elif _SHEAR_LAYER.search(layer):
                    pts = e.get_points()
                    for i in range(len(pts)-1): wall_lines.append(LineSeg(p1=pts[i], p2=pts[i+1], layer=layer))
                elif _SLAB_LAYER.search(layer) or _OUTLINE_LAYER.search(layer):
                    pts = [(p[0], p[1]) for p in e.get_points()]; area = _shoelace_area(pts)
                    if area >= self.min_slab: 
                        result.slab_outlines.append(SlabOutline(pts=pts, area_m2=area/1e6, symbol="NOSLAB", layer=layer))
                    else:
                        for i in range(len(pts)-1): slab_segments.append((pts[i], pts[i+1]))
            elif t == 'LINE':
                if _COL_LAYER.search(layer):
                    seg = self._line_to_seg(e, clip, idx)
                    if seg: col_lines.append(seg)
                elif _BEAM_LAYER.search(layer):
                    seg = self._line_to_seg(e, clip, idx)
                    if seg: beam_lines.append(seg)
                elif _SHEAR_LAYER.search(layer):
                    seg = self._line_to_seg(e, clip, idx)
                    if seg: wall_lines.append(seg)
                elif _SLAB_LAYER.search(layer):
                    s, en = e.dxf.start, e.dxf.end
                    slab_segments.append(((s.x, s.y), (en.x, en.y)))

        if col_lines: result.columns.extend(self._rect_cols_from_lines(col_lines, seen_cols))
        for seg in beam_lines:
            if seg.length >= self.min_beam: result.beams.append(BeamLine(x0=seg.p1[0], y0=seg.p1[1], x1=seg.p2[0], y1=seg.p2[1], layer=seg.layer))

        # [NEW] 슈퍼 전파 엔진 가동
        if result.beams:
            self._propagate_beam_labels(result.beams, text_entities)

        # [NEW] 슬래브 폐합 엔진 가동
        if slab_segments:
            result.slab_outlines.extend(self._heal_slab_outlines(slab_segments, text_entities))

        if text_entities:
            for c in result.columns: self._match_column_label(c, text_entities)
            for s in result.slab_outlines: self._match_slab_labels(s, text_entities)
            
        if grid:
            self._apply_grid_fallback(result.beams, grid)
            self._apply_grid_to_columns(result.columns, grid)

        # [NEW] 전단벽 추출 (Pairing logic)
        if wall_lines:
            result.shear_walls = self._pair_wall_lines(wall_lines)

        # 모든 부재 라벨 매칭 마무리
        self._match_all_labels(result, text_entities, grid)
        
        return result

    def _propagate_beam_labels(self, beams: List[BeamLine], texts: List[Tuple[float, float, str]]):
        """연결된 보들을 그룹화하여 공격적으로 라벨을 전파."""
        if not beams: return
        point_to_beams: Dict[Tuple[int, int], List[int]] = {}
        def to_key(x, y): return (round(x/200)*200, round(y/200)*200) # 허용 오차 확대 (200mm)
        
        for i, b in enumerate(beams):
            for p in [(b.x0, b.y0), (b.x1, b.y1)]:
                key = to_key(*p); point_to_beams.setdefault(key, []).append(i)
        
        visited = [False] * len(beams)
        pat = re.compile(r'^(([A-Z0-9-]{0,5})(G|B)\d+[A-Z]?|(\d{3,4}[xX]\d{3,4}))$', re.IGNORECASE)
        
        for i in range(len(beams)):
            if visited[i]: continue
            group = []; stack = [i]; visited[i] = True
            while stack:
                curr_idx = stack.pop(); group.append(curr_idx); b = beams[curr_idx]
                for p in [(b.x0, b.y0), (b.x1, b.y1)]:
                    key = to_key(*p)
                    for neighbor in point_to_beams.get(key, []):
                        if not visited[neighbor]: visited[neighbor] = True; stack.append(neighbor)
            
            # 공격적 탐색: 중점 + 양 끝점 + 넓은 반경 (5000mm)
            best_label, best_w, best_h = None, 400.0, 700.0
            for idx in group:
                b = beams[idx]
                search_pts = [(b.x0, b.y0), (b.x1, b.y1), ((b.x0+b.x1)/2, (b.y0+b.y1)/2)]
                for tx, ty, txt in texts:
                    is_near = any(math.hypot(tx-px, ty-py) < 5000 for px, py in search_pts)
                    if is_near and pat.match(txt):
                        best_label, best_w, best_h = self._parse_beam_label(txt); break
                if best_label: break
            
            if best_label:
                for idx in group:
                    if beams[idx].symbol == "NOBEAM":
                        beams[idx].symbol, beams[idx].width, beams[idx].height = best_label, best_w, best_h
                        beams[idx].volume_m3 = (beams[idx].width * beams[idx].height * beams[idx].length) / 1e9

    def _heal_slab_outlines(self, segments, texts) -> List[SlabOutline]:
        """끊어진 슬래브 선들을 이어붙여 폐합 시도."""
        if not segments: return []
        from shapely.geometry import LineString
        from shapely.ops import unary_union, polygonize
        
        lines = [LineString([(p[0], p[1]) for p in seg]) for seg in segments]
        merged = unary_union(lines)
        polys = list(polygonize(merged))
        
        healed = []
        for poly in polys:
            if poly.area >= self.min_slab:
                pts = list(poly.exterior.coords)
                healed.append(SlabOutline(pts=pts, area_m2=poly.area/1e6, symbol="NOSLAB", layer="HEALED_SLAB"))
        return healed

    def _col_from_insert(self, e, clip, seen, layer):
        if not is_structural_block(e.dxf.name): return None
        pos = e.dxf.insert; w, h = _parse_section(e.dxf.name, e.dxf.get('xscale', 1.0), e.dxf.get('yscale', 1.0))
        return ColumnPrim(cx=pos.x, cy=pos.y, w=w, h=h, rotation=e.dxf.get('rotation', 0.0), source='INSERT', block_name=e.dxf.name, layer=layer)

    def _col_from_hatch_pts(self, e, clip, seen, layer):
        try:
            pts = [(p[0],p[1]) for p in e.get_points()]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            cx, cy, w, h = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2, max(xs)-min(xs), max(ys)-min(ys)
            if not _in_clip(cx, cy, clip): return None
            if self.min_col<=w<=self.max_col and self.min_col<=h<=self.max_col:
                key = (round(cx/100)*100, round(cy/100)*100); seen.add(key)
                return ColumnPrim(cx=cx, cy=cy, w=w, h=h, source='LWPOLY', layer=layer)
        except: pass
        return None

    def _rect_cols_from_lines(self, segs, seen):
        cols = []
        midpoints = [(s.midpoint, s) for s in segs if math.degrees(s.angle)<5 or math.degrees(s.angle)>85]
        used = set()
        for i, (mp_i, seg_i) in enumerate(midpoints):
            if i in used: continue
            cluster = [(i, mp_i, seg_i)]
            for j, (mp_j, seg_j) in enumerate(midpoints):
                if j>i and j not in used and math.hypot(mp_i[0]-mp_j[0], mp_i[1]-mp_j[1])<3000: cluster.append((j, mp_j, seg_j))
            if len(cluster)>=2:
                all_pts = []; [all_pts.extend([s.p1, s.p2]) for _,_,s in cluster]; [used.add(idx) for idx,_,_ in cluster]
                xs, ys = [p[0] for p in all_pts], [p[1] for p in all_pts]
                cx, cy, w, h = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2, max(xs)-min(xs), max(ys)-min(ys)
                if self.min_col<=w<=self.max_col and self.min_col<=h<=self.max_col:
                    key = (round(cx/100)*100, round(cy/100)*100); seen.add(key)
                    cols.append(ColumnPrim(cx=cx, cy=cy, w=w, h=h, source='LINE_RECT', layer=segs[0].layer))
        return cols

    def _pair_wall_lines(self, lines: List[LineSeg]) -> List[WallPair]:
        """평행한 두 선을 묶어 벽체로 인식 (Wall Pairing)."""
        from core.line_pairing import pair_walls
        return pair_walls(lines)

    def _is_parallel(self, l1, l2, tol=0.05):
        a1, a2 = l1.angle % math.pi, l2.angle % math.pi
        return abs(a1 - a2) < tol or abs(a1 - a2) > (math.pi - tol)

    def _line_distance(self, l1, l2):
        # 중점 간의 거리를 법선 방향으로 투영하여 근사적 두께 계산
        m1 = ((l1.p1[0]+l1.p2[0])/2, (l1.p1[1]+l1.p2[1])/2)
        m2 = ((l2.p1[0]+l2.p2[0])/2, (l2.p1[1]+l2.p2[1])/2)
        return math.hypot(m1[0]-m2[0], m1[1]-m2[1])

    def _match_column_label(self, col, texts):
        pat = re.compile(r'([ST]?C\d+[A-Z0-9-]*)', re.IGNORECASE)
        best_dist = 5000.0
        best_sym = None
        for tx, ty, txt in texts:
            dist = math.hypot(tx-col.cx, ty-col.cy)
            if dist < best_dist:
                m = pat.search(txt)
                if m:
                    best_dist = dist
                    best_sym = m.group(1).upper()
        if best_sym:
            col.symbol = best_sym

    def _match_all_labels(self, data, texts, grid=None):
        """추출된 모든 부재에 대해 최적 라벨 매칭."""
        for col in data.columns:
            if col.symbol == "NOCOL": self._match_column_label(col, texts)
        
        for slab in data.slab_outlines:
            if slab.symbol == "NOSLAB": self._match_slab_labels(slab, texts)
            
        if grid:
            self._apply_grid_to_columns(data.columns, grid)
            self._apply_grid_fallback(data.beams, grid)
        pat = re.compile(r'([ST]?C\d+[A-Z0-9-]*)', re.IGNORECASE)
        best_dist = 5000.0
        best_sym = None
        for tx, ty, txt in texts:
            dist = math.hypot(tx-col.cx, ty-col.cy)
            if dist < best_dist:
                m = pat.search(txt)
                if m:
                    best_dist = dist
                    best_sym = m.group(1).upper()
        if best_sym:
            col.symbol = best_sym

    def _match_slab_labels(self, slab, texts):
        if not slab.pts: return
        from shapely.geometry import Polygon, Point
        try:
            poly = Polygon(slab.pts)
            if not poly.is_valid: poly = poly.buffer(0)
            
            # 1차: 폴리곤 내부 검색 (약간의 여유값 buffer 500mm 추가)
            check_poly = poly.buffer(500)
            for tx, ty, txt in texts:
                if check_poly.contains(Point(tx, ty)):
                    m = _SLAB_LABEL_PAT.search(txt)
                    if m:
                        slab.symbol = m.group(1).upper().replace(" ", "")
                        return
            
            # 2차: 최단 거리 검색 (폴백 - 3000mm 이내)
            best_dist = 3000.0
            best_label = None
            for tx, ty, txt in texts:
                dist = poly.distance(Point(tx, ty))
                if dist < best_dist:
                    m = _SLAB_LABEL_PAT.search(txt)
                    if m:
                        best_dist = dist
                        best_label = m.group(1).upper().replace(" ", "")
            
            if best_label:
                slab.symbol = best_label
                return

            # 3차: 중심점 근처 검색 (최후의 보루 - 15000mm)
            cx, cy = poly.centroid.x, poly.centroid.y
            for tx, ty, txt in texts:
                if math.hypot(tx-cx, ty-cy) < 15000:
                    m = _SLAB_LABEL_PAT.search(txt)
                    if m:
                        slab.symbol = m.group(1).upper().replace(" ", "")
                        return
        except Exception as e:
            print(f"  [Slab Match Error] {e}")

    def _apply_grid_fallback(self, beams, grid):
        """라벨이 없는 보에 대해 인근 격자선 정보를 기반으로 임시 식별자 부여."""
        if not grid: return
        for b in beams:
            if b.symbol != "NOBEAM": continue
            # 보의 중점 기준
            mx, my = (b.x0+b.x1)/2, (b.y0+b.y1)/2
            # 인근 격자 탐색 (반경 10m)
            nx = sorted([gl for gl in grid.x_lines if abs(gl.position - mx) < 10000], key=lambda g: abs(g.position - mx))
            ny = sorted([gl for gl in grid.y_lines if abs(gl.position - my) < 10000], key=lambda g: abs(g.position - my))
            
            if nx or ny:
                x_lab = nx[0].label if nx else "?"
                y_lab = ny[0].label if ny else "?"
                b.symbol = f"({x_lab}/{y_lab})"

    def _apply_grid_to_columns(self, cols, grid):
        for c in cols:
            if c.symbol != "NOCOL": continue
            nx = [gl for gl in grid.x_lines if abs(gl.position-c.cx)<3000]
            ny = [gl for gl in grid.y_lines if abs(gl.position-c.cy)<3000]
            if nx and ny: c.symbol = f"C({nx[0].label}/{ny[0].label})"

    def _parse_beam_label(self, label):
        nm = re.search(r'([a-zA-Z]+[0-9]+[a-zA-Z]*)', label); name = nm.group(1).upper() if nm else label.upper()
        sz = re.search(r'(\d{3,4})\s*[xX*]\s*(\d{3,4})', label)
        if sz: return name, float(sz.group(1)), float(sz.group(2))
        return name, 400.0, 700.0

    def _line_to_seg(self, e, clip, idx):
        s, en = e.dxf.start, e.dxf.end
        if _in_clip((s.x+en.x)/2, (s.y+en.y)/2, clip): return LineSeg(p1=(s.x,s.y), p2=(en.x,en.y), layer=e.dxf.layer, line_id=idx)
        return None

def extract_structural(dxf_path, **kwargs):
    from core.dxf_parser.safe_reader import safe_readfile
    doc = safe_readfile(dxf_path); return StructuralExtractor(**kwargs).extract(doc, clip=kwargs.get('clip'))

def parse_structural_frame(dxf_path, **kwargs):
    from core.dxf_parser.safe_reader import safe_readfile
    doc = safe_readfile(dxf_path); return StructuralExtractor(**kwargs).extract(doc, clip=kwargs.get('clip'), grid=kwargs.get('grid'))
