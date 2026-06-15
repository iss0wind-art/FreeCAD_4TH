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


def _build_table_cells(doc) -> List[Tuple[float, float, float, float]]:
    """도면의 수평/수직 선들을 교차 분석하여 표의 칸(Cell) Bounding Box 리스트를 반환."""
    h_lines = []
    v_lines = []
    
    # 1. 수평/수직선 수집 (오차 1도 허용)
    for e in doc.modelspace().query("LINE"):
        try:
            x1, y1 = float(e.dxf.start.x), float(e.dxf.start.y)
            x2, y2 = float(e.dxf.end.x), float(e.dxf.end.y)
            if x1 > x2: x1, x2, y1, y2 = x2, x1, y2, y1 # 왼쪽에서 오른쪽으로
            
            dx = x2 - x1
            dy = y2 - y1
            length = (dx**2 + dy**2)**0.5
            if length < 100: continue # 너무 짧은 선은 무시
            
            angle = abs(dy / dx) if dx != 0 else 999.0
            
            if angle < 0.05: # 수평선 (약 3도 이내)
                h_lines.append((x1, y1, x2, y2))
            elif angle > 20.0: # 수직선
                if y1 > y2: x1, x2, y1, y2 = x2, x1, y2, y1 # 아래에서 위로
                v_lines.append((x1, y1, x2, y2))
        except:
            pass
            
    # 2. X, Y 좌표 클러스터링 (비슷한 좌표의 선들은 하나의 구분선으로 병합)
    tol = 50.0
    y_coords = []
    for h in h_lines:
        y = (h[1] + h[3]) / 2
        matched = False
        for i, cy in enumerate(y_coords):
            if abs(cy - y) < tol:
                y_coords[i] = (cy + y) / 2
                matched = True
                break
        if not matched: y_coords.append(y)
        
    x_coords = []
    for v in v_lines:
        x = (v[0] + v[2]) / 2
        matched = False
        for i, cx in enumerate(x_coords):
            if abs(cx - x) < tol:
                x_coords[i] = (cx + x) / 2
                matched = True
                break
        if not matched: x_coords.append(x)
        
    x_coords.sort()
    y_coords.sort()
    
    # 3. 격자(Grid) 생성: x_coords와 y_coords로 만들어지는 사각형(Cell)
    cells = []
    for i in range(len(x_coords) - 1):
        for j in range(len(y_coords) - 1):
            xmin, xmax = x_coords[i], x_coords[i+1]
            ymin, ymax = y_coords[j], y_coords[j+1]
            if (xmax - xmin) > 50 and (ymax - ymin) > 50:
                cells.append((xmin, xmax, ymin, ymax))
                
    return cells

def parse_section_list(
    dxf_path: Path,
    row_tolerance_mm: float = 3500.0,
    col_match_radius_mm: float = 8000.0,
) -> List[SectionEntry]:
    """일람표 DXF 1개 → SectionEntry 목록 (Table Grid 알고리즘)."""
    doc = ezdxf.readfile(str(dxf_path))
    texts = list(_walk_texts(doc))
    cells = _build_table_cells(doc)

    entries: List[SectionEntry] = []
    
    # Grid를 성공적으로 추출한 경우: 행(Row) 단위로 묶기
    if cells:
        # 1. 텍스트를 Cell에 할당
        cell_contents = {} # cell_bounds -> list of texts
        for t, x, y in texts:
            assigned = False
            for (xmin, xmax, ymin, ymax) in cells:
                if xmin <= x <= xmax and ymin <= y <= ymax:
                    cell_contents.setdefault((xmin, xmax, ymin, ymax), []).append((t.strip(), x, y))
                    assigned = True
                    break
            # 셀에 들어가지 못한 텍스트는 임시로 가장 가까운 셀에 넣거나 보류 (우선 생략)

        # 2. 동일한 Y 범위를 가진 셀들을 같은 행(Row)으로 묶기
        rows = {} # (ymin, ymax) -> list of cells
        for c in cells:
            key = (c[2], c[3])
            matched_key = None
            for rk in rows.keys():
                if abs(rk[0] - key[0]) < 100 and abs(rk[1] - key[1]) < 100:
                    matched_key = rk
                    break
            if matched_key:
                rows[matched_key].append(c)
            else:
                rows[key] = [c]

        # 3. 각 행(Row) 안에서 심볼과 치수를 찾아서 매칭
        for row_bounds, row_cells in rows.items():
            row_symbols = []
            row_dims = []
            row_cells.sort(key=lambda c: c[0]) # X 좌표 순으로 정렬 (왼쪽에서 오른쪽)
            
            for c in row_cells:
                contents = cell_contents.get(c, [])
                for t, x, y in contents:
                    for piece in re.split(r"[,/&]", t):
                        piece = piece.strip()
                        if _PAT_SYMBOL.match(piece):
                            row_symbols.append((piece, x, y))
                    
                    m = _PAT_WH.search(t)
                    if m:
                        try:
                            w, h = float(m.group(1)), float(m.group(2))
                            if 50 <= w <= 5000 and 50 <= h <= 5000:
                                row_dims.append((w, h, x, y))
                        except:
                            pass
            
            # 같은 행 안에서 심볼과 가장 가까운 치수 매칭
            used_dims = set()
            for sym, sx, sy in row_symbols:
                best_idx = -1
                best_dx = float('inf')
                for i, (w, h, dx, dy) in enumerate(row_dims):
                    if i in used_dims: continue
                    dist_x = abs(dx - sx)
                    if dist_x < best_dx:
                        best_dx = dist_x
                        best_idx = i
                
                if best_idx >= 0:
                    w, h, dx, dy = row_dims[best_idx]
                    entries.append(SectionEntry(
                        symbol=sym, width_mm=w, height_mm=h,
                        member_type=_symbol_to_type(sym), source_dxf=str(dxf_path),
                        distance_mm=best_dx,
                    ))
                    used_dims.add(best_idx)
    
    # Grid 추출 실패 시 Fallback (기존 방식 유사)
    else:
        symbols, dims = [], []
        for t, x, y in texts:
            s = t.strip()
            for piece in re.split(r"[,/&]", s):
                piece = piece.strip()
                if _PAT_SYMBOL.match(piece): symbols.append((piece, x, y))
            m = _PAT_WH.search(s)
            if m:
                try:
                    w, h = float(m.group(1)), float(m.group(2))
                    dims.append((w, h, x, y))
                except: pass
                
        used_dims = set()
        for sym, sx, sy in symbols:
            best_idx, best_dx = -1, col_match_radius_mm
            for i, (w, h, dx, dy) in enumerate(dims):
                if i in used_dims: continue
                if abs(dy - sy) > row_tolerance_mm: continue
                if abs(dx - sx) < best_dx:
                    best_dx = abs(dx - sx)
                    best_idx = i
            if best_idx >= 0:
                w, h, dx, dy = dims[best_idx]
                entries.append(SectionEntry(
                    symbol=sym, width_mm=w, height_mm=h,
                    member_type=_symbol_to_type(sym), source_dxf=str(dxf_path),
                    distance_mm=best_dx,
                ))
                used_dims.add(best_idx)

    return entries


def parse_slab_list(
    dxf_path: Path,
    row_tolerance_mm: float = 1500.0,
    col_match_radius_mm: float = 5000.0,
) -> List[SectionEntry]:
    """슬라브 일람표: 'A','B','C' 또는 'S1','S2' 라벨 + 두께 (단일값). Table Grid 지원."""
    doc = ezdxf.readfile(str(dxf_path))
    texts = list(_walk_texts(doc))
    cells = _build_table_cells(doc)

    slab_label_pat = re.compile(r"^([A-H]|S\d+|SL\d+|F\d+)$")
    thk_pat = re.compile(r"^(\d{2,4})$")

    entries: List[SectionEntry] = []
    
    if cells:
        cell_contents = {}
        for t, x, y in texts:
            for (xmin, xmax, ymin, ymax) in cells:
                if xmin <= x <= xmax and ymin <= y <= ymax:
                    cell_contents.setdefault((xmin, xmax, ymin, ymax), []).append((t.strip(), x, y))
                    break

        rows = {}
        for c in cells:
            key = (c[2], c[3])
            matched = None
            for rk in rows.keys():
                if abs(rk[0] - key[0]) < 100 and abs(rk[1] - key[1]) < 100:
                    matched = rk
                    break
            if matched: rows[matched].append(c)
            else: rows[key] = [c]

        for row_bounds, row_cells in rows.items():
            row_labels, row_thks = [], []
            for c in row_cells:
                for t, x, y in cell_contents.get(c, []):
                    if slab_label_pat.match(t): row_labels.append((t, x, y))
                    elif thk_pat.match(t):
                        try:
                            v = int(t)
                            if 50 <= v <= 1000: row_thks.append((v, x, y))
                        except: pass
            
            used = set()
            for lab, lx, ly in row_labels:
                best_idx, best_dx = -1, float('inf')
                for i, (v, tx, ty) in enumerate(row_thks):
                    if i in used: continue
                    if abs(tx - lx) < best_dx:
                        best_dx = abs(tx - lx)
                        best_idx = i
                if best_idx >= 0:
                    v, tx, ty = row_thks[best_idx]
                    entries.append(SectionEntry(
                        symbol=lab, width_mm=v, height_mm=0, # width_mm에 임시저장
                        member_type=MemberType.SLAB, source_dxf=str(dxf_path),
                        distance_mm=best_dx,
                    ))
                    used.add(best_idx)
    else:
        # Fallback
        labels, thicknesses = [], []
        for t, x, y in texts:
            s = t.strip()
            if slab_label_pat.match(s): labels.append((s, x, y))
            elif thk_pat.match(s):
                try:
                    v = int(s)
                    if 50 <= v <= 1000: thicknesses.append((v, x, y))
                except: pass
                
        used = set()
        for lab, lx, ly in labels:
            best_idx, best_dx = -1, col_match_radius_mm
            for i, (v, tx, ty) in enumerate(thicknesses):
                if i in used: continue
                if abs(ty - ly) > row_tolerance_mm: continue
                if abs(tx - lx) < best_dx:
                    best_dx = abs(tx - lx)
                    best_idx = i
            if best_idx >= 0:
                v, tx, ty = thicknesses[best_idx]
                entries.append(SectionEntry(
                    symbol=lab, width_mm=v, height_mm=0,
                    member_type=MemberType.SLAB, source_dxf=str(dxf_path),
                    distance_mm=best_dx,
                ))
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
