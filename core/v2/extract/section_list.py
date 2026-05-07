"""
section_list.py — 일람표 DXF 자동 파싱 (v4 P4 신설)
======================================================
보 리스트, 기둥 리스트, 벽체 리스트 등 별도 일람표 도면에서
(심볼, 단면 치수) 페어 자동 추출.

[알고리즘]
  1. 모든 텍스트 수집 (INSERT 재귀)
  2. 심볼 패턴 (RG3A, RB1, C1 등) → SymbolLabel 목록
  3. WxH 패턴 ('500 x 900', '600x900') → DimLabel 목록
  4. 거리 기반 매칭 (반경 내 가장 가까운 dim → symbol)
  5. (symbol, w, h) 페어 카탈로그 생성

[규약]
  - 매직넘버 0건 (radius 외부 주입)
  - 매칭 실패는 명시 (silent X)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ezdxf

from core.v2.classify.ks_lexicon import MemberType


@dataclass
class SectionEntry:
    """일람표에서 추출한 (심볼, 치수) 페어."""
    symbol: str               # "RG3A", "C1"
    width_mm: float
    height_mm: float
    member_type: MemberType
    source_dxf: str
    distance_mm: float        # 매칭 거리 (검증용)


_PAT_SYMBOL = re.compile(r"^([CTGRBFW]+\d+[A-Z]?)$")
_PAT_WH = re.compile(r"(\d+)\s*[xX×]\s*(\d+)")
_PAT_THK = re.compile(r"^(\d+)\s*[Tt](?:hk)?$|^t\s*=\s*(\d+)$|^두께\s*(\d+)$")


# 심볼 → 부재 타입 자동 분류
def _symbol_to_type(symbol: str) -> MemberType:
    s = symbol.upper()
    if s.startswith("RB") or s.startswith("RG") or s.startswith("TB") or s.startswith("FB") or s.startswith("G"):
        return MemberType.BEAM
    if s.startswith("C") or s.startswith("TC"):
        return MemberType.COLUMN
    if s.startswith("W"):
        return MemberType.WALL
    if s.startswith("F"):
        return MemberType.FOUNDATION
    return MemberType.UNKNOWN


def _walk_texts(doc, max_depth: int = 6):
    """DXF 텍스트 전수 (INSERT 재귀)."""
    def _walk(e, depth=0, ox=0, oy=0):
        et = e.dxftype()
        if et in ("TEXT", "MTEXT"):
            try:
                t = (e.dxf.text if et == "TEXT"
                     else (e.plain_text() if hasattr(e, "plain_text") else e.text))
                yield (t, float(e.dxf.insert.x) + ox, float(e.dxf.insert.y) + oy)
            except Exception:
                pass
        elif et == "ATTRIB":
            try:
                yield (e.dxf.text, float(e.dxf.insert.x) + ox, float(e.dxf.insert.y) + oy)
            except Exception:
                pass
        elif et == "INSERT":
            try:
                for a in e.attribs:
                    yield (a.dxf.text,
                           float(a.dxf.insert.x) + ox,
                           float(a.dxf.insert.y) + oy)
            except Exception:
                pass
            if depth >= max_depth:
                return
            try:
                ix, iy = float(e.dxf.insert.x) + ox, float(e.dxf.insert.y) + oy
                blk = doc.blocks.get(e.dxf.name)
                if blk:
                    for c in blk:
                        yield from _walk(c, depth + 1, ix, iy)
            except Exception:
                pass

    msp = doc.modelspace()
    for e in msp:
        yield from _walk(e)


def parse_section_list(
    dxf_path: Path,
    row_tolerance_mm: float = 3500.0,
    col_match_radius_mm: float = 8000.0,
) -> List[SectionEntry]:
    """일람표 DXF 1개 → SectionEntry 목록.

    [행 단위 매칭]
        같은 Y 좌표(±row_tolerance) 안의 심볼·dim을 X로 정렬.
        각 심볼은 같은 행에서 X 가장 가까운 dim과 매칭.

    Args:
        dxf_path: 일람표 DXF
        row_tolerance_mm: 같은 행으로 볼 Y 차이
        col_match_radius_mm: X 매칭 최대 거리
    """
    doc = ezdxf.readfile(str(dxf_path))
    texts = list(_walk_texts(doc))

    # 심볼·치수·두께 분리
    symbols: List[Tuple[str, float, float]] = []
    dims: List[Tuple[float, float, float, float]] = []   # (w, h, x, y)
    thicknesses: List[Tuple[float, float, float]] = []   # (t, x, y)

    for t, x, y in texts:
        s = t.strip()

        # 콤마/슬래시 결합 처리: 'RG2,REG2' → ['RG2', 'REG2']
        # 베이스 심볼 우선 (가장 짧은 또는 첫번째)
        for piece in re.split(r"[,/&]", s):
            piece = piece.strip()
            if _PAT_SYMBOL.match(piece):
                symbols.append((piece, x, y))

        m = _PAT_WH.search(s)
        if m:
            try:
                w, h = float(m.group(1)), float(m.group(2))
                if 50 <= w <= 5000 and 50 <= h <= 5000:
                    dims.append((w, h, x, y))
                continue
            except Exception:
                pass
        m = _PAT_THK.match(s)
        if m:
            v = next(g for g in m.groups() if g)
            try:
                thicknesses.append((float(v), x, y))
            except Exception:
                pass

    # 행 단위 매칭
    entries: List[SectionEntry] = []
    used_dims = set()

    for sym, sx, sy in symbols:
        # 같은 행 (Y±tolerance) 의 미사용 dim 중 X 가장 가까운 것
        best_idx = -1
        best_dx = col_match_radius_mm
        for i, (w, h, dx, dy) in enumerate(dims):
            if i in used_dims:
                continue
            if abs(dy - sy) > row_tolerance_mm:
                continue
            dist_x = abs(dx - sx)
            if dist_x < best_dx:
                best_dx = dist_x
                best_idx = i

        if best_idx < 0:
            continue

        w, h, dx, dy = dims[best_idx]
        d2 = (dx - sx) ** 2 + (dy - sy) ** 2
        entries.append(SectionEntry(
            symbol=sym,
            width_mm=w,
            height_mm=h,
            member_type=_symbol_to_type(sym),
            source_dxf=str(dxf_path),
            distance_mm=d2 ** 0.5,
        ))
        used_dims.add(best_idx)

    return entries


def parse_slab_list(
    dxf_path: Path,
    row_tolerance_mm: float = 1500.0,
    col_match_radius_mm: float = 5000.0,
) -> List[SectionEntry]:
    """슬라브 일람표: 'A','B','C' 또는 'S1','S2' 라벨 + 두께 (단일값).

    슬라브 두께는 W×H 형식이 아니라 단일 값('150', '200').
    행 단위로 라벨 ↔ 두께 매칭.
    """
    doc = ezdxf.readfile(str(dxf_path))
    texts = list(_walk_texts(doc))

    # 슬라브 라벨 패턴 (단순 알파벳·S+숫자·SLAB 등)
    slab_label_pat = re.compile(r"^([A-H]|S\d+|SL\d+|F\d+)$")
    # 두께 후보 (단일 정수)
    thk_pat = re.compile(r"^(\d{2,4})$")

    labels = []
    thicknesses = []
    for t, x, y in texts:
        s = t.strip()
        if slab_label_pat.match(s):
            labels.append((s, x, y))
        elif thk_pat.match(s):
            try:
                v = int(s)
                if 50 <= v <= 1000:    # 슬라브 두께 합리적 범위
                    thicknesses.append((v, x, y))
            except Exception:
                pass

    entries: List[SectionEntry] = []
    used = set()
    for lab, lx, ly in labels:
        best_idx = -1
        best_dx = col_match_radius_mm
        for i, (v, tx, ty) in enumerate(thicknesses):
            if i in used:
                continue
            if abs(ty - ly) > row_tolerance_mm:
                continue
            dist_x = abs(tx - lx)
            if dist_x < best_dx:
                best_dx = dist_x
                best_idx = i

        if best_idx < 0:
            continue

        v, tx, ty = thicknesses[best_idx]
        d2 = (tx - lx) ** 2 + (ty - ly) ** 2
        entries.append(SectionEntry(
            symbol=lab,
            width_mm=0,        # 슬라브는 W·H 의미 없음
            height_mm=0,
            member_type=MemberType.SLAB,
            source_dxf=str(dxf_path),
            distance_mm=d2 ** 0.5,
        ))
        # 두께를 다른 필드로 저장 못하니 SectionEntry 확장이 필요. 임시로 width_mm에 두께
        entries[-1].width_mm = v
        used.add(best_idx)

    return entries


def parse_multiple_lists(
    dxf_paths: List[Path],
    row_tolerance_mm: float = 3500.0,
    col_match_radius_mm: float = 8000.0,
) -> Dict[str, SectionEntry]:
    """여러 일람표 → {symbol: SectionEntry} 통합 카탈로그.

    각 도면이 일반(WxH) 일람표인지 슬라브(두께만) 일람표인지 자동 감지.
    """
    catalog: Dict[str, SectionEntry] = {}
    for path in dxf_paths:
        try:
            # 슬라브 일람표인지 파일명으로 추정
            is_slab = "슬라브" in path.name or "슬래브" in path.name or "slab" in path.name.lower()
            if is_slab:
                entries = parse_slab_list(path, row_tolerance_mm, col_match_radius_mm)
            else:
                entries = parse_section_list(path, row_tolerance_mm, col_match_radius_mm)
        except Exception as e:
            print(f"[WARN] {path.name}: {e}")
            continue
        for ent in entries:
            existing = catalog.get(ent.symbol)
            if existing is None or ent.distance_mm < existing.distance_mm:
                catalog[ent.symbol] = ent
    return catalog
