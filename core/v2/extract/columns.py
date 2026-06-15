"""
columns.py — COLUMN 추출 (v4 P4 #4)
=====================================
LWPOLYLINE 닫힌 작은 polygon → bbox → COLUMN 인스턴스.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from core.v2.io.dxf_loader import get_flattened_entities


@dataclass
class ExtractedColumn:
    """추출된 기둥 1개."""
    cx: float
    cy: float
    width_mm: float
    height_mm: float
    layer: str
    section_symbol: Optional[str] = None


def extract_columns(
    doc,
    column_layers: List[str],
    min_size_mm: float = 100.0,
    max_size_mm: float = 2500.0,
) -> List[ExtractedColumn]:
    """COLUMN 레이어의 엔티티 → 기둥 (블록 내부 포함, LINE 클러스터링 지원)."""
    column_layer_set = set(l.upper() for l in column_layers)

    # LWPOLYLINE, LINE 둘 다 가져오기
    all_ents = get_flattened_entities(
        doc, 
        target_layers=column_layer_set, 
        target_types={"LWPOLYLINE", "POLYLINE", "LINE"}
    )

    columns: List[ExtractedColumn] = []
    
    # 1단계: 명확하게 닫힌 폴리라인은 먼저 기둥으로 취급
    unprocessed_pts = [] # (x, y) 포인트들 모음 (LINE, 열린 POLYLINE)
    for e in all_ents:
        et = e.dxftype()
        if et in ("LWPOLYLINE", "POLYLINE") and e.is_closed:
            try:
                pts = [(p[0], p[1]) for p in e.get_points()]
            except Exception:
                continue
            if len(pts) < 3:
                continue

            xmin, xmax = min(p[0] for p in pts), max(p[0] for p in pts)
            ymin, ymax = min(p[1] for p in pts), max(p[1] for p in pts)
            w, h = xmax - xmin, ymax - ymin

            if min_size_mm <= w <= max_size_mm and min_size_mm <= h <= max_size_mm:
                columns.append(ExtractedColumn(
                    cx=(xmin + xmax) / 2, cy=(ymin + ymax) / 2,
                    width_mm=w, height_mm=h, layer=e.dxf.layer,
                ))
        else:
            # 닫히지 않은 선들은 점으로 분해해서 클러스터링 후보로 넣기
            if et == "LINE":
                unprocessed_pts.append((e.dxf.start.x, e.dxf.start.y, e.dxf.layer))
                unprocessed_pts.append((e.dxf.end.x, e.dxf.end.y, e.dxf.layer))
            elif et in ("LWPOLYLINE", "POLYLINE"):
                try:
                    for p in e.get_points():
                        unprocessed_pts.append((p[0], p[1], e.dxf.layer))
                except:
                    pass

    # 2단계: 남은 점들을 반경 거리 기반으로 클러스터링 (Healer Logic)
    # 기둥 최대 크기(max_size_mm) 정도를 클러스터링 기준으로 삼음
    clusters = [] # list of [(x, y, layer), ...]
    merge_radius = max_size_mm * 1.2 # 이 반경 안의 점들은 같은 기둥일 확률이 높음

    # 간단한 Union-Find 대신 O(N^2)로 클러스터링 (기둥 개수가 적을 때 유효, 많으면 최적화 필요)
    # 현장 도면 처리 성능을 위해 Grid 기반 공간 분할로 클러스터링 속도 향상
    grid = {}
    cell_size = merge_radius
    for pt in unprocessed_pts:
        cx, cy = int(pt[0] // cell_size), int(pt[1] // cell_size)
        grid.setdefault((cx, cy), []).append(pt)

    visited = set()
    for pt in unprocessed_pts:
        if pt in visited: continue
        
        # 새 클러스터 시작
        cluster = []
        stack = [pt]
        visited.add(pt)
        
        while stack:
            curr = stack.pop()
            cluster.append(curr)
            
            # 인접 셀 검사
            cx, cy = int(curr[0] // cell_size), int(curr[1] // cell_size)
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    for neighbor in grid.get((cx+dx, cy+dy), []):
                        if neighbor not in visited:
                            dist = ((curr[0]-neighbor[0])**2 + (curr[1]-neighbor[1])**2)**0.5
                            if dist <= merge_radius:
                                visited.add(neighbor)
                                stack.append(neighbor)
        
        if len(cluster) >= 4: # 적어도 4개 이상의 점이 모여야 기둥으로 판단
            xmin, xmax = min(p[0] for p in cluster), max(p[0] for p in cluster)
            ymin, ymax = min(p[1] for p in cluster), max(p[1] for p in cluster)
            w, h = xmax - xmin, ymax - ymin
            
            if min_size_mm <= w <= max_size_mm and min_size_mm <= h <= max_size_mm:
                # 가장 많이 등장한 레이어를 대표 레이어로 선정
                layer_counts = {}
                for p in cluster:
                    layer_counts[p[2]] = layer_counts.get(p[2], 0) + 1
                dom_layer = max(layer_counts, key=layer_counts.get)
                
                # 기존에 추가된 완전한 기둥과 영역이 겹치는지 확인 (중복 방지)
                cx_cand, cy_cand = (xmin + xmax) / 2, (ymin + ymax) / 2
                is_overlap = False
                for c in columns:
                    if abs(c.cx - cx_cand) < c.width_mm/2 and abs(c.cy - cy_cand) < c.height_mm/2:
                        is_overlap = True
                        break
                
                if not is_overlap:
                    columns.append(ExtractedColumn(
                        cx=cx_cand, cy=cy_cand,
                        width_mm=w, height_mm=h, layer=dom_layer,
                    ))

    return columns
