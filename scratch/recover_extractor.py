import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import ezdxf

# ─────────────────────────────────────────────────────────────
# 1. 자료구조 정의
# ─────────────────────────────────────────────────────────────

@dataclass
class ColumnPrim:
    cx: float; cy: float; w: float; h: float
    rotation: float = 0.0
    symbol: str = "NOCOL"
    source: str = ""
    block_name: str = ""
    layer: str = ""

@dataclass
class SlabOutline:
    pts: List[Tuple[float, float]]
    area_m2: float
    symbol: str = "NOSLAB"
    layer: str = ""

@dataclass
class BeamLine:
    x0: float; y0: float; x1: float; y1: float
    layer: str = ''; width: float = 400.0; height: float = 700.0
    symbol: str = "NOBEAM"; volume_m3: float = 0.0
    @property
    def length(self) -> float: return math.hypot(self.x1-self.x0, self.y1-self.y0)

@dataclass
class StructuralData:
    columns: List[ColumnPrim] = field(default_factory=list)
    beams: List[BeamLine] = field(default_factory=list)
    slab_outlines: List[SlabOutline] = field(default_factory=list)
    shear_walls: List[object] = field(default_factory=list) # WallPair 임시 object

# ─────────────────────────────────────────────────────────────
# 2. 추출기 엔진
# ─────────────────────────────────────────────────────────────

class StructuralExtractor:
    def __init__(self, min_col_size=100.0, max_col_size=2500.0, min_slab_area_m2=10.0, codex=None):
        self.min_col = min_col_size; self.max_col = max_col_size
        self.min_slab = min_slab_area_m2 * 1_000_000
        self.min_beam = 500.0; self.codex = codex

    def extract(self, doc, clip=None, grid=None):
        from core.dxf_parser.entity_scanner import iter_clip
        from core.dxf_parser.full_extractor import _in_clip, _parse_section
        from core.dxf_parser.structural_filter import is_structural_block
        
        result = StructuralData(); msp = doc.modelspace(); texts = []; seen_cols = set()
        beam_lines = []; col_lines = []
        
        _COL_LY = re.compile(r'STR.*(COL|柱|기둥)|S-COL|구조.*기둥', re.IGNORECASE)
        _BEAM_LY = re.compile(r'STR.*BEAM|S-BEAM|구조.*보', re.IGNORECASE)
        _SLAB_LY = re.compile(r'STR.*SLAB|S-SLAB|구조.*슬래브', re.IGNORECASE)

        for e in iter_clip(msp, clip):
            t = e.dxftype()
            if t in ('TEXT', 'MTEXT'):
                txt = e.plain_text() if t == 'MTEXT' else e.dxf.text
                pos = e.dxf.insert
                if _in_clip(pos.x, pos.y, clip): texts.append((pos.x, pos.y, txt))
            
            try: layer = e.dxf.layer
            except: continue
            
            if t == 'INSERT':
                col = self._col_from_insert(e, clip, seen_cols, layer)
                if col: self._match_column_label(col, texts); result.columns.append(col)
            elif t == 'LWPOLYLINE':
                if _BEAM_LY.search(layer):
                    pts = e.get_points()
                    for i in range(len(pts)-1): beam_lines.append((pts[i], pts[i+1], layer))
                elif _SLAB_LY.search(layer):
                    pts = e.get_points(); area = self._area(pts)
                    if area >= self.min_slab:
                        s = SlabOutline(pts=pts, area_m2=area/1e6); self._match_slab_labels(s, texts); result.slab_outlines.append(s)

        # 격자 기반 명명 (마지막 수단)
        if grid:
            if result.columns: self._apply_grid_to_columns(result.columns, grid)
        return result

    def _col_from_insert(self, e, clip, seen, layer):
        from core.dxf_parser.full_extractor import _in_clip, _parse_section
        from core.dxf_parser.structural_filter import is_structural_block
        bn = e.dxf.name
        if not is_structural_block(bn): return None
        pos = e.dxf.insert
        if not _in_clip(pos.x, pos.y, clip): return None
        w, h = _parse_section(bn, e.dxf.get("xscale", 1.0), e.dxf.get("yscale", 1.0))
        return ColumnPrim(cx=pos.x, cy=pos.y, w=w, h=h, source="INSERT", layer=layer)

    def _match_column_label(self, col, texts):
        pat = re.compile(r'([ST]?C\d+[A-Z0-9-]*)', re.IGNORECASE)
        for tx, ty, txt in texts:
            if math.hypot(tx-col.cx, ty-col.cy) < 3000:
                m = pat.search(txt)
                if m: col.symbol = m.group(1).upper(); return

    def _match_slab_labels(self, slab, texts):
        pat = re.compile(r'(\d?S\d[A-Z]?|T[=]?\d{2,3}|THK\d{2,3})', re.IGNORECASE)
        cx, cy = sum(p[0] for p in slab.pts)/len(slab.pts), sum(p[1] for p in slab.pts)/len(slab.pts)
        for tx, ty, txt in texts:
            if math.hypot(tx-cx, ty-cy) < 6000:
                m = pat.search(txt)
                if m: slab.symbol = m.group(1).upper(); return

    def _apply_grid_to_columns(self, cols, grid):
        for c in cols:
            if c.symbol != "NOCOL": continue
            nx = [gl for gl in grid.x_lines if abs(gl.position-c.cx)<3000]
            ny = [gl for gl in grid.y_lines if abs(gl.position-c.cy)<3000]
            if nx and ny: c.symbol = f"C({nx[0].label}/{ny[0].label})"

    def _area(self, pts):
        return 0.5 * abs(sum(pts[i][0]*pts[i+1][1] - pts[i+1][0]*pts[i][1] for i in range(len(pts)-1)))

def parse_structural_frame(dxf_path, **kwargs):
    from core.dxf_parser.safe_reader import safe_readfile
    doc = safe_readfile(dxf_path); ext = StructuralExtractor(**kwargs)
    return ext.extract(doc, clip=kwargs.get("clip"), grid=kwargs.get("grid"))
