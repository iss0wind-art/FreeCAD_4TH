"""
structural_extractor.py — 골조 전용 통합 추출기
=================================================
콘크리트 골조 4부재만 추출:
  기둥 (Column)    — INSERT 블록 + HATCH 단면
  보   (Beam)      — LINE/LWPOLYLINE on 보 레이어
  슬라브 (Slab)   — LWPOLYLINE 외곽 (실제 건물 형태)
  전단벽 (Shear)  — LINE 페어 on 구조벽 레이어

[원칙]
  조적·마감·창호·설비·가구 = 무시
  도면에 있는 값만 사용 — 추정 없음
  다음 도면에도 즉시 적용 가능한 일반화 로직
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import ezdxf

from core.dxf_parser.entity_scanner import iter_all
from core.dxf_parser.structural_filter import (
    is_structural, is_structural_block, _STRUCTURAL,
)
from core.dxf_parser.full_extractor import (
    ColumnPrim, SlabOutline, _parse_section, _shoelace_area, _in_clip,
)
from core.line_pairing import LineSeg, WallPair, pair_walls


# ─────────────────────────────────────────────────────────────
# 보 레이어 패턴
# ─────────────────────────────────────────────────────────────

_BEAM_LAYER = re.compile(
    r'(S[-_]GIRDER|S[-_]BEAM|S[-_]PC[-_]GIRDER'
    r'|00[-_]BEAM|00[-_]APT\)?BEAM|GIRDER|PC[-_]GIRDER)',
    re.IGNORECASE,
)
_SHEAR_LAYER = re.compile(
    r'(00[-_]SHEAR|SHEAR[-_]WALL|A[-_]WALL[-_]RC'
    r'|S[-_]WALL(?![-_]SYMBOL)|전단벽|CORE[-_]WALL)',
    re.IGNORECASE,
)
_SLAB_LAYER = re.compile(
    r'(S[-_]PC[-_]SLAB|S[-_]SLAB|00[-_]SLAB|SLAB)',
    re.IGNORECASE,
)
_COL_LAYER = re.compile(
    r'(00[-_]COLUMN|S[-_]기둥|S[-_]COL|STRUCT[-_]COL|COL(?!OR))',
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────
# 자료구조
# ─────────────────────────────────────────────────────────────

@dataclass
class BeamLine:
    """보 중심선 세그먼트."""
    x0: float
    y0: float
    x1: float
    y1: float
    layer: str = ''
    width: float = 400.0   # 기본 폭 (mm, codex 없을 시)
    height: float = 900.0  # 기본 높이 (mm)

    @property
    def length(self) -> float:
        return math.hypot(self.x1-self.x0, self.y1-self.y0)


@dataclass
class StructuralData:
    """골조 추출 결과 전체."""
    columns: List[ColumnPrim] = field(default_factory=list)
    beams: List[BeamLine] = field(default_factory=list)
    slab_outlines: List[SlabOutline] = field(default_factory=list)
    shear_walls: List[WallPair] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f'기둥 {len(self.columns)}개 | '
            f'보 {len(self.beams)}개 | '
            f'슬라브 외곽 {len(self.slab_outlines)}개 | '
            f'전단벽 {len(self.shear_walls)}개'
        )

    def stats(self) -> dict:
        return {
            'columns': len(self.columns),
            'beams': len(self.beams),
            'slab_outlines': len(self.slab_outlines),
            'shear_walls': len(self.shear_walls),
        }


# ─────────────────────────────────────────────────────────────
# 추출기
# ─────────────────────────────────────────────────────────────

class StructuralExtractor:
    """골조 전용 통합 추출기.

    사용:
        ext = StructuralExtractor()
        data = ext.extract(doc, clip=(xmin,ymin,xmax,ymax))
        print(data.summary())
    """

    def __init__(self,
                 min_col_size: float = 100.0,
                 max_col_size: float = 2500.0,
                 min_slab_area_m2: float = 50.0,
                 max_slab_area_m2: float = 100_000.0,
                 min_beam_length: float = 500.0,
                 shear_max_thickness: float = 600.0,
                 shear_min_length: float = 500.0):
        self.min_col = min_col_size
        self.max_col = max_col_size
        self.min_slab = min_slab_area_m2 * 1_000_000  # m² → mm²
        self.max_slab = max_slab_area_m2 * 1_000_000
        self.min_beam = min_beam_length
        self.shear_max_t = shear_max_thickness
        self.shear_min_l = shear_min_length

    def extract(self, doc,
                clip: Optional[Tuple[float,float,float,float]] = None) -> StructuralData:
        """골조 4부재 일괄 추출."""
        msp = doc.modelspace()
        result = StructuralData()
        seen_cols: set = set()

        # 선분 수집
        beam_lines: List[LineSeg] = []
        shear_lines: List[LineSeg] = []
        col_lines: List[LineSeg] = []   # 기둥 레이어 LINE (지하주차장 방식)
        idx = 0

        for e in iter_all(msp):
            t = e.dxftype()
            try:
                layer = e.dxf.layer
            except Exception:
                continue

            # ── 기둥: INSERT ──────────────────────────────────
            if t == 'INSERT':
                col = self._col_from_insert(e, clip, seen_cols, layer)
                if col:
                    result.columns.append(col)

            # ── 기둥: HATCH (단면 채움) ────────────────────────
            elif t == 'HATCH':
                col = self._col_from_hatch(e, clip, seen_cols, layer)
                if col:
                    result.columns.append(col)

            # ── 기둥·보·전단벽: LINE ──────────────────────────
            elif t == 'LINE':
                if _COL_LAYER.search(layer):
                    seg = self._line_to_seg(e, clip, idx)
                    if seg:
                        col_lines.append(seg)
                elif _BEAM_LAYER.search(layer):
                    seg = self._line_to_seg(e, clip, idx)
                    if seg:
                        beam_lines.append(seg)
                elif _SHEAR_LAYER.search(layer):
                    seg = self._line_to_seg(e, clip, idx)
                    if seg and seg.length >= self.shear_min_l:
                        shear_lines.append(seg)

            # ── 보·슬라브: LWPOLYLINE ──────────────────────────
            elif t == 'LWPOLYLINE':
                if _COL_LAYER.search(layer):
                    # 지하주차장: 기둥이 LWPOLYLINE으로 그려질 수 있음
                    col = self._col_from_hatch_pts(e, clip, seen_cols, layer)
                    if col:
                        result.columns.append(col)
                elif _BEAM_LAYER.search(layer):
                    seg = self._lwpoly_to_segs(e, clip, idx)
                    beam_lines.extend(seg)
                else:
                    # 큰 닫힌 폴리라인 → 슬라브 외곽 후보
                    outline = self._slab_from_lwpoly(e, clip)
                    if outline:
                        result.slab_outlines.append(outline)

            idx += 1

        # ── 기둥 레이어 LINE → 사각형 기둥 복원 ──────────────
        if col_lines:
            rect_cols = self._rect_cols_from_lines(col_lines, seen_cols)
            result.columns.extend(rect_cols)

        # ── LINE → BeamLine 변환 ──────────────────────────────
        for seg in beam_lines:
            if seg.length >= self.min_beam:
                result.beams.append(BeamLine(
                    x0=seg.p1[0], y0=seg.p1[1],
                    x1=seg.p2[0], y1=seg.p2[1],
                    layer=seg.layer,
                ))

        # ── 전단벽 LINE 페어링 ────────────────────────────────
        if shear_lines:
            result.shear_walls = pair_walls(
                shear_lines,
                max_dist=self.shear_max_t,
                min_length=self.shear_min_l,
                overlap_min_ratio=0.3,
            )

        # 슬라브 면적 정렬 (큰 것 먼저)
        result.slab_outlines.sort(key=lambda s: -s.area_m2)

        return result

    # ─────────────────────────────────────────────────────────
    # 내부: 기둥
    # ─────────────────────────────────────────────────────────

    def _col_from_insert(self, e, clip, seen, layer) -> Optional[ColumnPrim]:
        try:
            bname = e.dxf.name
            if not is_structural_block(bname):
                return None
            pos = e.dxf.insert
            if not _in_clip(pos.x, pos.y, clip):
                return None
            key = (round(pos.x/100)*100, round(pos.y/100)*100)
            if key in seen:
                return None
            seen.add(key)
            xsc = e.dxf.get('xscale', 1.0)
            ysc = e.dxf.get('yscale', 1.0)
            rot = e.dxf.get('rotation', 0.0)
            w, h = _parse_section(bname, xsc, ysc)
            return ColumnPrim(cx=pos.x, cy=pos.y, w=w, h=h,
                              rotation=rot, source='INSERT',
                              block_name=bname, layer=layer)
        except Exception:
            return None

    def _col_from_hatch_pts(self, e, clip, seen, layer) -> Optional[ColumnPrim]:
        """LWPOLYLINE 닫힌 사각형 → 기둥 (지하주차장 기둥 레이어용)."""
        try:
            flags = e.dxf.flags
            if not (flags & 1):
                return None
            pts = [(p[0], p[1]) for p in e.get_points()]
            if len(pts) < 3:
                return None
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            cx = (min(xs)+max(xs))/2; cy = (min(ys)+max(ys))/2
            if not _in_clip(cx, cy, clip): return None
            w = max(xs)-min(xs); h = max(ys)-min(ys)
            if not (self.min_col <= w <= self.max_col and
                    self.min_col <= h <= self.max_col): return None
            key = (round(cx/100)*100, round(cy/100)*100)
            if key in seen: return None
            seen.add(key)
            return ColumnPrim(cx=cx, cy=cy, w=w, h=h,
                              source='LWPOLY', layer=layer)
        except Exception:
            return None

    def _rect_cols_from_lines(self, segs: List[LineSeg],
                              seen: set) -> List[ColumnPrim]:
        """기둥 레이어 LINE 4개 → 사각형 기둥 복원.

        H선 2개 + V선 2개가 교차하면 기둥 사각형.
        간단화: 각 선의 중점을 군집화 → 사각형 추정.
        """
        import math as _m
        cols = []
        # 수평·수직 LINE만 (기울기 <5° or >85°)
        h_segs = [s for s in segs if _m.degrees(s.angle) < 5 or _m.degrees(s.angle) > 85]

        # 중점 기반 클러스터링 (간단화)
        midpoints = [(s.midpoint, s) for s in h_segs]

        # 600mm 반경 이내 LINE 그룹 → 사각형 추정
        used = set()
        for i, (mp_i, seg_i) in enumerate(midpoints):
            if i in used:
                continue
            cluster = [(i, mp_i, seg_i)]
            for j, (mp_j, seg_j) in enumerate(midpoints):
                if j <= i or j in used:
                    continue
                dist = _m.hypot(mp_i[0]-mp_j[0], mp_i[1]-mp_j[1])
                if dist < 3000:  # 3m 이내
                    cluster.append((j, mp_j, seg_j))

            if len(cluster) >= 2:
                all_pts = []
                for idx_c, _, seg_c in cluster:
                    all_pts += [seg_c.p1, seg_c.p2]
                    used.add(idx_c)
                xs = [p[0] for p in all_pts]; ys = [p[1] for p in all_pts]
                cx = (min(xs)+max(xs))/2; cy = (min(ys)+max(ys))/2
                w = max(xs)-min(xs); h = max(ys)-min(ys)
                if not (self.min_col <= w <= self.max_col and
                        self.min_col <= h <= self.max_col):
                    continue
                key = (round(cx/100)*100, round(cy/100)*100)
                if key in seen:
                    continue
                seen.add(key)
                cols.append(ColumnPrim(cx=cx, cy=cy, w=w, h=h,
                                       source='LINE_RECT',
                                       layer=segs[0].layer if segs else ''))
        return cols

    def _col_from_hatch(self, e, clip, seen, layer) -> Optional[ColumnPrim]:
        try:
            pts: List[Tuple[float,float]] = []
            for path in e.paths:
                try:
                    pts = [(p[0],p[1]) for p in path.vertices]
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
            # 기둥 크기 필터
            if not (self.min_col <= w <= self.max_col and
                    self.min_col <= h <= self.max_col):
                return None
            key = (round(cx/100)*100, round(cy/100)*100)
            if key in seen:
                return None
            seen.add(key)
            return ColumnPrim(cx=cx, cy=cy, w=w, h=h,
                              source='HATCH', layer=layer)
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────
    # 내부: 보·선분
    # ─────────────────────────────────────────────────────────

    def _line_to_seg(self, e, clip, idx: int) -> Optional[LineSeg]:
        try:
            s = e.dxf.start
            en = e.dxf.end
            cx, cy = (s.x+en.x)/2, (s.y+en.y)/2
            if not _in_clip(cx, cy, clip):
                return None
            return LineSeg(p1=(s.x,s.y), p2=(en.x,en.y),
                           layer=e.dxf.layer, line_id=idx)
        except Exception:
            return None

    def _lwpoly_to_segs(self, e, clip, idx: int) -> List[LineSeg]:
        segs = []
        try:
            pts = [(p[0],p[1]) for p in e.get_points()]
            layer = e.dxf.layer
            for i in range(len(pts)-1):
                x0,y0 = pts[i]; x1,y1 = pts[i+1]
                cx,cy = (x0+x1)/2,(y0+y1)/2
                if _in_clip(cx,cy,clip):
                    segs.append(LineSeg(p1=(x0,y0),p2=(x1,y1),
                                        layer=layer,line_id=idx+i))
        except Exception:
            pass
        return segs

    # ─────────────────────────────────────────────────────────
    # 내부: 슬라브
    # ─────────────────────────────────────────────────────────

    _EXCLUDE_SLAB = re.compile(r'Defpoints|BORD|FRAME|BORDER|도곽', re.IGNORECASE)

    def _slab_from_lwpoly(self, e, clip) -> Optional[SlabOutline]:
        try:
            layer = e.dxf.layer
            if self._EXCLUDE_SLAB.search(layer):
                return None
            # 슬라브 레이어 우선. 없으면 일반 closed LWPOLYLINE도 허용
            flags = e.dxf.flags
            is_closed = bool(flags & 1)
            pts = [(p[0],p[1]) for p in e.get_points()]
            if len(pts) < 4:
                return None
            area = _shoelace_area(pts)
            if not (self.min_slab <= area <= self.max_slab):
                return None
            # 닫힌 폴리라인만 (열린 것도 건물 윤곽이면 사용)
            if not is_closed and area < 500_000_000:  # 500m² 미만 열린 선 = 제외
                return None
            cx = sum(p[0] for p in pts)/len(pts)
            cy = sum(p[1] for p in pts)/len(pts)
            if not _in_clip(cx, cy, clip):
                return None
            return SlabOutline(pts=pts, area_m2=area/1_000_000,
                               layer=layer, is_closed=is_closed)
        except Exception:
            return None


# ─────────────────────────────────────────────────────────────
# 편의 함수
# ─────────────────────────────────────────────────────────────

def extract_structural(dxf_path: str,
                       encoding: str = 'cp949',
                       clip=None,
                       **kwargs) -> StructuralData:
    """파일 경로에서 직접 추출."""
    doc = ezdxf.readfile(dxf_path, encoding=encoding)
    return StructuralExtractor(**kwargs).extract(doc, clip=clip)
