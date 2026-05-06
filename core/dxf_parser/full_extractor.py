"""
full_extractor.py — DXF 완전 파싱기
=====================================
하나도 빠트리지 않는 구조 부재 추출.

[추출 대상]
  기둥  — INSERT 블록명 패턴 + HATCH(채워진 단면) + closed LWPOLYLINE
  슬라브 — 건물 외곽 LWPOLYLINE (가장 큰 닫힌 폴리라인)
  보    — 코어 codex와 매핑 (LINE/LWPOLYLINE on beam layer)
  벽    — LWPOLYLINE 쌍 (core/line_pairing.py)
  단차  — TEXT (level_parser.py)

[v3 결함 해소]
  슬라브 외곽: 기둥 BBox 사각형 → 실제 LWPOLYLINE 추출
  기둥 단면: INSERT 블록명 파싱 (C400X800) + HATCH 폴백

[다음 사람에게]
  extractor = FullExtractor()
  result = extractor.extract(doc, clip=(xmin,ymin,xmax,ymax))
  print(result.summary())
  # result.columns → 기둥 목록
  # result.slab_outlines → 슬라브 외곽 (실제 형태)
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

import ezdxf

from core.dxf_parser.entity_scanner import iter_all

sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ─────────────────────────────────────────────────────────────
# 레이어 패턴
# ─────────────────────────────────────────────────────────────

_COL_BLOCK = re.compile(
    r'C\d{3,}'          # C400, C600 등
    r'|COL|기둥|COLUMN'  # 일반 명칭
    r'|PC[-_]C'          # PC-C 프리캐드
    r'|B\d[-_]B\d\s+[EP]?C\d'  # B2-B1 C2, B2-B1 EC1, B2-B1 PC2
    r'|[EP]?C\d{1,2}\b',  # EC1, PC2, C2 단독
    re.IGNORECASE,
)
_COL_LAYER = re.compile(r'S[-_]?기둥|S[-_]?COL|STRUCT[-_]?COL', re.IGNORECASE)
_BEAM_LAYER = re.compile(r'S[-_]?보|BEAM|GIRDER|S[-_]?B\d', re.IGNORECASE)
_SLAB_LAYER = re.compile(r'S[-_]?슬|SLAB|FLOOR|S[-_]?SL|S[-_]?F\d', re.IGNORECASE)
_WALL_LAYER = re.compile(r'WALL|벽|S[-_]?W\d|전단벽|SHEAR', re.IGNORECASE)
_OUTLINE_LAYER = re.compile(r'A[-_]?외곽|OUTLINE|건물외벽|BLDG[-_]?OUT', re.IGNORECASE)

_SECTION_SIZE = re.compile(r'(\d{3,4})[xX×*](\d{3,4})', re.IGNORECASE)
_SECTION_SQ = re.compile(r'[Cc](\d{3,4})\b')


# ─────────────────────────────────────────────────────────────
# 자료구조
# ─────────────────────────────────────────────────────────────

@dataclass
class ColumnPrim:
    """기둥 원시 데이터 (도면 좌표계)."""
    cx: float
    cy: float
    w: float            # 단면 너비 (X방향, mm)
    h: float            # 단면 높이 (Y방향, mm)
    rotation: float = 0.0
    source: str = 'INSERT'   # INSERT | HATCH | LWPOLY
    block_name: str = ''
    layer: str = ''

    def bbox(self) -> Tuple[float,float,float,float]:
        hw, hh = self.w/2, self.h/2
        return (self.cx-hw, self.cy-hh, self.cx+hw, self.cy+hh)


@dataclass
class SlabOutline:
    """슬라브 외곽선 — LWPOLYLINE 실제 형태."""
    pts: List[Tuple[float, float]]
    area_m2: float = 0.0
    layer: str = ''
    is_closed: bool = True

    def bbox(self) -> Tuple[float,float,float,float]:
        xs = [p[0] for p in self.pts]
        ys = [p[1] for p in self.pts]
        return (min(xs), min(ys), max(xs), max(ys))


@dataclass
class WallLine:
    """벽 중심선 또는 외면선 세그먼트."""
    x0: float
    y0: float
    x1: float
    y1: float
    layer: str = ''

    @property
    def length(self) -> float:
        import math
        return math.hypot(self.x1-self.x0, self.y1-self.y0)


@dataclass
class ExtractResult:
    """추출 결과 전체."""
    columns: List[ColumnPrim] = field(default_factory=list)
    slab_outlines: List[SlabOutline] = field(default_factory=list)
    wall_lines: List[WallLine] = field(default_factory=list)
    layer_stats: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> str:
        top_slab = (f'{self.slab_outlines[0].area_m2:.0f} m²'
                    if self.slab_outlines else '없음')
        return (
            f'기둥 {len(self.columns)}개 | '
            f'슬라브 외곽 {len(self.slab_outlines)}개 (최대 {top_slab}) | '
            f'벽선 {len(self.wall_lines)}개'
        )

    def column_count_by_source(self) -> Dict[str, int]:
        cnt: Dict[str, int] = defaultdict(int)
        for c in self.columns:
            cnt[c.source] += 1
        return dict(cnt)


# ─────────────────────────────────────────────────────────────
# 추출기
# ─────────────────────────────────────────────────────────────

class FullExtractor:
    """DXF 완전 파싱기.

    사용:
        extractor = FullExtractor()
        result = extractor.extract(doc, clip=(xmin,ymin,xmax,ymax))
        print(result.summary())
    """

    def __init__(self,
                 min_slab_area_m2: float = 50.0,
                 col_hatch_on_col_layer_only: bool = False):
        """
        min_slab_area_m2: 슬라브로 인식할 최소 면적 (기본 50m²)
        col_hatch_on_col_layer_only: True면 기둥 레이어 HATCH만 추출
        """
        self.min_slab_area = min_slab_area_m2 * 1_000_000  # m² → mm²
        self.col_hatch_on_col_layer_only = col_hatch_on_col_layer_only

    def extract(self, doc,
                clip: Optional[Tuple[float,float,float,float]] = None) -> ExtractResult:
        """DXF 도면에서 모든 구조 부재 추출.

        Args:
            doc: ezdxf 도면 객체
            clip: (xmin,ymin,xmax,ymax) — 영역 제한 (None=전체)
        """
        msp = doc.modelspace()
        result = ExtractResult()
        layer_stats: Dict[str, int] = defaultdict(int)
        seen_cols: set = set()  # 중복 제거

        for e in iter_all(msp):
            t = e.dxftype()
            try:
                layer = e.dxf.layer
            except Exception:
                layer = ''
            layer_stats[layer] += 1

            if t == 'INSERT':
                col = self._col_from_insert(e, clip, seen_cols)
                if col:
                    result.columns.append(col)

            elif t == 'HATCH':
                if self.col_hatch_on_col_layer_only and not _COL_LAYER.search(layer):
                    continue
                col = self._col_from_hatch(e, clip, seen_cols)
                if col:
                    result.columns.append(col)

            elif t == 'LWPOLYLINE':
                # 슬라브 외곽 후보
                outline = self._slab_from_lwpoly(e, clip)
                if outline:
                    result.slab_outlines.append(outline)
                # 벽선 후보
                if _WALL_LAYER.search(layer):
                    wl = self._wall_from_lwpoly(e, clip)
                    if wl:
                        result.wall_lines.extend(wl)

            elif t == 'LINE':
                if _WALL_LAYER.search(layer) or _BEAM_LAYER.search(layer):
                    wl = self._wall_from_line(e, clip)
                    if wl:
                        result.wall_lines.append(wl)

        result.layer_stats = dict(layer_stats)

        # 슬라브 외곽 정렬 (큰 것 먼저)
        result.slab_outlines.sort(key=lambda s: -s.area_m2)

        return result

    # ─── 기둥 INSERT ────────────────────────────────────────

    def _col_from_insert(self, e, clip, seen) -> Optional[ColumnPrim]:
        try:
            pos = e.dxf.insert
            if not _in_clip(pos.x, pos.y, clip):
                return None
            bname = e.dxf.name
            if not _COL_BLOCK.search(bname):
                return None

            xsc = e.dxf.get('xscale', 1.0)
            ysc = e.dxf.get('yscale', 1.0)
            rot = e.dxf.get('rotation', 0.0)
            w, h = _parse_section(bname, xsc, ysc)

            key = (round(pos.x), round(pos.y))
            if key in seen:
                return None
            seen.add(key)

            return ColumnPrim(
                cx=pos.x, cy=pos.y, w=w, h=h,
                rotation=rot, source='INSERT',
                block_name=bname, layer=e.dxf.layer,
            )
        except Exception:
            return None

    # ─── 기둥 HATCH ─────────────────────────────────────────

    def _col_from_hatch(self, e, clip, seen) -> Optional[ColumnPrim]:
        try:
            pts: List[Tuple[float,float]] = []
            for path in e.paths:
                try:
                    pts = [(p[0], p[1]) for p in path.vertices]
                    if len(pts) >= 3:
                        break
                except Exception:
                    pass
            if len(pts) < 3:
                return None
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cx = (min(xs)+max(xs))/2
            cy = (min(ys)+max(ys))/2
            if not _in_clip(cx, cy, clip):
                return None
            w = max(xs)-min(xs)
            h = max(ys)-min(ys)
            # 슬라브 크기가 아닌 기둥 크기인지 — 최대 2m×2m
            if w > 2000 or h > 2000 or w < 100 or h < 100:
                return None
            key = (round(cx), round(cy))
            if key in seen:
                return None
            seen.add(key)
            return ColumnPrim(
                cx=cx, cy=cy, w=w, h=h,
                source='HATCH', layer=e.dxf.layer,
            )
        except Exception:
            return None

    # ─── 슬라브 LWPOLYLINE ──────────────────────────────────

    # Defpoints, 도곽 등 제외할 레이어
    _EXCLUDE_LAYERS = re.compile(
        r'Defpoints|도곽|도면번호|TITLE|BORDER|SHEET|FRAME',
        re.IGNORECASE,
    )
    # 최대 슬라브 면적 (100,000 m² 초과 = 도곽 경계로 판단)
    _MAX_SLAB_M2 = 100_000.0

    def _slab_from_lwpoly(self, e, clip) -> Optional[SlabOutline]:
        try:
            layer = e.dxf.layer
            if self._EXCLUDE_LAYERS.search(layer):
                return None
            flags = e.dxf.flags
            if not (flags & 1):  # 닫힌 폴리라인만
                return None
            pts = [(p[0], p[1]) for p in e.get_points()]
            if len(pts) < 4:
                return None

            area_mm2 = _shoelace_area(pts)
            area_m2 = area_mm2 / 1_000_000
            if area_mm2 < self.min_slab_area:  # min_slab_area는 mm² 단위
                return None
            if area_m2 > self._MAX_SLAB_M2:
                return None  # 도곽 경계 제외

            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            if not _in_clip(cx, cy, clip):
                return None

            return SlabOutline(
                pts=pts,
                area_m2=area_m2,
                layer=layer,
                is_closed=True,
            )
        except Exception:
            return None

    # ─── 벽선 LWPOLYLINE ─────────────────────────────────────

    def _wall_from_lwpoly(self, e, clip) -> List[WallLine]:
        lines = []
        try:
            pts = [(p[0], p[1]) for p in e.get_points()]
            layer = e.dxf.layer
            for i in range(len(pts)-1):
                x0,y0 = pts[i]
                x1,y1 = pts[i+1]
                cx,cy = (x0+x1)/2, (y0+y1)/2
                if _in_clip(cx, cy, clip):
                    lines.append(WallLine(x0,y0,x1,y1,layer=layer))
        except Exception:
            pass
        return lines

    # ─── 벽선 LINE ──────────────────────────────────────────

    def _wall_from_line(self, e, clip) -> Optional[WallLine]:
        try:
            s = e.dxf.start
            en = e.dxf.end
            cx,cy = (s.x+en.x)/2, (s.y+en.y)/2
            if not _in_clip(cx, cy, clip):
                return None
            return WallLine(s.x,s.y,en.x,en.y,layer=e.dxf.layer)
        except Exception:
            return None


# ─────────────────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────────────────

def _in_clip(x: float, y: float,
             clip: Optional[Tuple[float,float,float,float]]) -> bool:
    if clip is None:
        return True
    return clip[0] <= x <= clip[2] and clip[1] <= y <= clip[3]


def _shoelace_area(pts: List[Tuple[float,float]]) -> float:
    n = len(pts)
    return abs(sum(
        pts[i][0] * pts[(i+1)%n][1] - pts[(i+1)%n][0] * pts[i][1]
        for i in range(n)
    ) / 2)


def _parse_section(block_name: str, xsc: float, ysc: float) -> Tuple[float, float]:
    """블록명에서 단면 치수 파싱.

    패턴 예:
      C400X800  → (400, 800)
      C500      → (500, 500)
      TC600X900 → (600, 900)
    """
    m = _SECTION_SIZE.search(block_name)
    if m:
        return float(m.group(1)) * xsc, float(m.group(2)) * ysc

    m2 = _SECTION_SQ.search(block_name)
    if m2:
        d = float(m2.group(1))
        return d * xsc, d * ysc

    return 500.0 * xsc, 500.0 * ysc


def extract_slab_outline_dominant(doc, clip=None,
                                   min_area_m2: float = 100.0) -> Optional[SlabOutline]:
    """도면에서 가장 큰 LWPOLYLINE 외곽 = 건물 슬라브 형태.

    v3에서 BoundingBox로 처리하던 것의 대체.
    실제 건물 외곽선을 반환한다.
    """
    extractor = FullExtractor(min_slab_area_m2=min_area_m2)
    result = extractor.extract(doc, clip=clip)
    if not result.slab_outlines:
        return None
    return result.slab_outlines[0]  # 면적 최대 = 건물 외곽
