"""
build_pyeongtaek_integrated.py — 평택 고덕 3D STEP 모델 및 BOQ 빌더
========================================================================
1. output/pyeongtaek_members_accumulated.json 로드
2. 기둥-보 연결성 토폴로지 필터 적용 (외톨이 부재 제거)
3. FreeCAD 3D 솔리드 구축 (COLUMN, BEAM)
4. 2D Spatial Grid Index를 통한 Boolean Cut 겹침 트리밍 런타임 최적화
5. 3D STEP 파일 내보내기 + BOQ 물량 집계

실행:
  "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/build_pyeongtaek_integrated.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import FreeCAD
import Part

try:
    from core.pipeline.boq_solid_builder import beam_solid, box_solid
    from core.pipeline.member_data import Member
except Exception as e:
    import traceback
    with open("pyeongtaek_error.log", "w", encoding="utf-8") as f:
        traceback.print_exc(file=f)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# 설정 및 경로
# ─────────────────────────────────────────────────────────────
ACCUMULATED = "output/pyeongtaek_members_accumulated.json"
STEP_OUT = "output/pyeongtaek_integrated.step"
BOQ_OUT = "output/pyeongtaek_integrated_boq.json"

# ─────────────────────────────────────────────────────────────
# 공간 분할 (Spatial Grid Index) 관련 클래스 및 헬퍼
# ─────────────────────────────────────────────────────────────
GRID_SIZE = 10000.0  # 10m x 10m 셀 크기

def get_grid_keys(xmin: float, xmax: float, ymin: float, ymax: float) -> set[tuple[int, int]]:
    x_min_cell = int(math.floor(xmin / GRID_SIZE))
    x_max_cell = int(math.floor(xmax / GRID_SIZE))
    y_min_cell = int(math.floor(ymin / GRID_SIZE))
    y_max_cell = int(math.floor(ymax / GRID_SIZE))
    
    keys = set()
    for gx in range(x_min_cell, x_max_cell + 1):
        for gy in range(y_min_cell, y_max_cell + 1):
            keys.add((gx, gy))
    return keys

class CachedObj:
    def __init__(self, obj):
        self.obj = obj
        self.name = obj.Name
        bbox = obj.Shape.BoundBox
        self.bbox_tuple = (bbox.XMin, bbox.XMax, bbox.YMin, bbox.YMax, bbox.ZMin, bbox.ZMax)
        self.grid_keys = get_grid_keys(bbox.XMin, bbox.XMax, bbox.YMin, bbox.YMax)

    def update_bbox(self):
        bbox = self.obj.Shape.BoundBox
        self.bbox_tuple = (bbox.XMin, bbox.XMax, bbox.YMin, bbox.YMax, bbox.ZMin, bbox.ZMax)
        self.grid_keys = get_grid_keys(bbox.XMin, bbox.XMax, bbox.YMin, bbox.YMax)

def intersect_bbox(b1: tuple[float, ...], b2: tuple[float, ...]) -> bool:
    return (b1[0] <= b2[1] and b1[1] >= b2[0] and
            b1[2] <= b2[3] and b1[3] >= b2[2] and
            b1[4] <= b2[5] and b1[5] >= b2[4])

def dist_pt(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

# ─────────────────────────────────────────────────────────────
# 메인 빌드 파이프라인
# ─────────────────────────────────────────────────────────────
def main():
    t0 = time.time()
    print("=" * 60)
    print("평택 고덕 3D 통합 빌더 (공간 분할 최적화) 개시")
    print("=" * 60)

    # 1. 부재 목록 로드
    if not Path(ACCUMULATED).exists():
        print(f"오류: {ACCUMULATED} 파일이 존재하지 않습니다.")
        return

    with open(ACCUMULATED, encoding="utf-8") as f:
        acc_data = json.load(f)
    raw_members = acc_data.get("members", [])
    print(f"원본 부재 로드: {len(raw_members)}건")

    # 2. 1차 필터링 (길이 필터 적용)
    MIN_BEAM_LEN_MM = 1500.0

    filtered_cols = []
    filtered_beams = []

    for m in raw_members:
        mtype = m.get("type")
        length = float(m.get("length_mm") or 0.0)

        if mtype == "COLUMN":
            filtered_cols.append(m)
        elif mtype == "BEAM":
            if length >= MIN_BEAM_LEN_MM:
                filtered_beams.append(m)

    print(f"1차 필터링 완료: 기둥 {len(filtered_cols)}개, 보 {len(filtered_beams)}개")

    # 3. 연결성(Connection) 필터 적용 (기둥과 닿지 않는 외톨이 보 노이즈 소거)
    # 기둥 중심점 및 높이 범위 구축
    col_centers = [(c["ax"], c["ay"], c["z_bot"], c["z_top"]) for c in filtered_cols]
    
    # 공간 인덱스를 활용한 빠른 연결성 매칭
    col_spatial_grid = {}
    for cx, cy, cz_bot, cz_top in col_centers:
        keys = get_grid_keys(cx - 1500, cx + 1500, cy - 1500, cy + 1500)
        for key in keys:
            col_spatial_grid.setdefault(key, []).append((cx, cy, cz_bot, cz_top))

    connected_beams = []
    skipped_isolated_beam = 0

    for m in filtered_beams:
        ax, ay = m["ax"], m["ay"]
        L = float(m.get("length_mm") or 1000.0)
        ang = math.radians(float(m.get("angle_deg") or 0.0))
        p0 = (ax - (L / 2) * math.cos(ang), ay - (L / 2) * math.sin(ang))
        p1 = (ax + (L / 2) * math.cos(ang), ay + (L / 2) * math.sin(ang))
        z_bot, z_top = m["z_bot"], m["z_top"]

        # 보가 속하는 그리드 키 계산
        xmin, xmax = min(p0[0], p1[0]), max(p0[0], p1[0])
        ymin, ymax = min(p0[1], p1[1]), max(p0[1], p1[1])
        b_keys = get_grid_keys(xmin - 500, xmax + 500, ymin - 500, ymax + 500)

        is_connected = False
        candidates = set()
        for key in b_keys:
            if key in col_spatial_grid:
                for c in col_spatial_grid[key]:
                    candidates.add(c)

        for cx, cy, cz_bot, cz_top in candidates:
            z_overlap = max(0, min(z_top, cz_top) - max(z_bot, cz_bot))
            if z_overlap > 0:
                if dist_pt(p0, (cx, cy)) < 1500.0 or dist_pt(p1, (cx, cy)) < 1500.0:
                    is_connected = True
                    break

        if is_connected:
            connected_beams.append(m)
        else:
            skipped_isolated_beam += 1

    print(f"연결성 필터 결과:")
    print(f"  기둥 연결 안 된 외톨이 보 스킵: {skipped_isolated_beam}개 (남은 보: {len(connected_beams)}개)")

    final_structured_members = filtered_cols + connected_beams
    print(f"최종 정제된 구조 부재: {len(final_structured_members)}건")

    # FreeCAD 도큐먼트 개설
    fc_doc = FreeCAD.newDocument("PyeongtaekIntegrated")
    shapes_with_names = []
    builder_boq_items = []
    
    n_col = n_beam = 0

    # 4. 기둥 및 보 3D 솔리드 빌드
    for m in final_structured_members:
        mtype = m["type"]
        mid = m["id"]
        ax, ay = m["ax"], m["ay"]
        zb = float(m["z_bot"])
        zt = float(m["z_top"])
        floor = m["floor"]

        # ── 기둥 ──────────────────────────────────
        if mtype == "COLUMN":
            sec = m.get("section", "600x600")
            try:
                w, h = map(float, sec.lower().split("x"))
            except ValueError:
                w, h = 600.0, 600.0
            
            s = box_solid(ax, ay, zb, zt, w, h)
            if s:
                feat = fc_doc.addObject("Part::Feature", mid)
                feat.Shape = s
                shapes_with_names.append((s, mid))
                n_col += 1
                
                vol_m3 = (w * h * (zt - zb)) / 1e9
                builder_boq_items.append({
                    "id": mid, "type": "COLUMN", "floor": floor, "source": m["source"],
                    "x": ax, "y": ay, "z_bot": zb, "z_top": zt,
                    "section": sec, "volume_m3": round(vol_m3, 4), "layer": m.get("layer", "")
                })

        # ── 보 ────────────────────────────────────
        elif mtype == "BEAM":
            L = float(m.get("length_mm") or 1000.0)
            ang = math.radians(float(m.get("angle_deg") or 0.0))
            x0 = ax - (L / 2) * math.cos(ang)
            y0 = ay - (L / 2) * math.sin(ang)
            x1 = ax + (L / 2) * math.cos(ang)
            y1 = ay + (L / 2) * math.sin(ang)
            
            sec = m.get("section", "400x900")
            try:
                bw, bh = map(float, sec.lower().split("x"))
            except ValueError:
                bw, bh = 400.0, 900.0
            
            # 슬래브 두께(예: 150mm) 제외
            s = beam_solid(x0, y0, x1, y1, bw=bw, bh=bh, zb=zt - bh, zt=zt)
            if s:
                feat = fc_doc.addObject("Part::Feature", mid)
                feat.Shape = s
                shapes_with_names.append((s, mid))
                n_beam += 1

                vol_m3 = (bw * bh * L) / 1e9
                builder_boq_items.append({
                    "id": mid, "type": "BEAM", "floor": floor, "source": m["source"],
                    "x": ax, "y": ay, "z_bot": zt - bh, "z_top": zt,
                    "section": sec, "volume_m3": round(vol_m3, 4), "layer": m.get("layer", "")
                })

    print(f"구조 부재 솔리드 빌드 완료:")
    print(f"  COLUMN: {n_col}개")
    print(f"  BEAM:   {n_beam}개")

    # 5. 3D Solid Overlap Trim (Boolean Cut) - 공간 분할 최적화
    print("\n[Trim] 3D 부재 간 기하 겹침 정밀 트리밍 개시 (Spatial Grid Index)...")
    t_trim_start = time.time()
    
    col_objs = [o for o in fc_doc.Objects if "COL" in o.Name]
    beam_objs = [o for o in fc_doc.Objects if "BM" in o.Name]

    # 5-1. 기둥 객체 캐싱 및 그리드 인덱싱
    col_grid: dict[tuple[int, int], list[CachedObj]] = {}
    cached_cols: list[CachedObj] = []
    for c in col_objs:
        if not hasattr(c, "Shape") or not c.Shape:
            continue
        try:
            c_cached = CachedObj(c)
            cached_cols.append(c_cached)
            for key in c_cached.grid_keys:
                col_grid.setdefault(key, []).append(c_cached)
        except Exception:
            pass

    # 5-2. 보(BEAM) 트리밍 (보 ↔ 기둥)
    n_beam_trimmed = 0
    for b in beam_objs:
        if not hasattr(b, "Shape") or not b.Shape:
            continue
        try:
            b_cached = CachedObj(b)
            
            candidates = set()
            for key in b_cached.grid_keys:
                if key in col_grid:
                    for c_cached in col_grid[key]:
                        candidates.add(c_cached)
                        
            for c_cached in candidates:
                if intersect_bbox(b_cached.bbox_tuple, c_cached.bbox_tuple):
                    try:
                        cut_shape = b.Shape.cut(c_cached.obj.Shape)
                        if cut_shape and len(cut_shape.Solids) > 0:
                            b.Shape = cut_shape
                            n_beam_trimmed += 1
                    except Exception:
                        pass
        except Exception:
            pass

    print(f"[Trim] 트리밍 완료 (소요시간: {time.time() - t_trim_start:.1f}초):")
    print(f"  보 트리밍 적용:  {n_beam_trimmed}회")

    # FreeCAD Recompute
    fc_doc.recompute()

    # 6. STEP 파일 내보내기
    print(f"\n[STEP] 저장 중: {STEP_OUT} ...")
    Part.export([o for o in fc_doc.Objects], str(STEP_OUT))
    size_mb = Path(STEP_OUT).stat().st_size / 1024 / 1024
    print(f"[STEP] 저장 완료: {STEP_OUT} ({size_mb:.1f} MB)")

    # 7. BOQ 데이터 집계 및 저장
    by_type_boq = {}
    for item in builder_boq_items:
        t = item["type"]
        by_type_boq.setdefault(t, {"count": 0, "volume_m3": 0.0})
        by_type_boq[t]["count"] += 1
        if "volume_m3" in item:
            by_type_boq[t]["volume_m3"] += item["volume_m3"]

    for t in by_type_boq:
        by_type_boq[t]["volume_m3"] = round(by_type_boq[t]["volume_m3"], 2)

    boq_output_data = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "total_count": len(builder_boq_items),
        "by_type": by_type_boq,
        "members": builder_boq_items
    }

    with open(BOQ_OUT, "w", encoding="utf-8") as f:
        json.dump(boq_output_data, f, ensure_ascii=False, indent=2)

    print(f"\n[BOQ] 저장 완료: {BOQ_OUT}")
    print("수량 집계 요약:")
    for t, stat in by_type_boq.items():
        print(f"  {t:7s}: count={stat['count']:5d}개, volume={stat['volume_m3']:8.2f} m³")

    # BoundBox 연산 및 출력
    all_shapes = [o.Shape for o in fc_doc.Objects if hasattr(o, "Shape") and o.Shape]
    if all_shapes:
        compound = Part.makeCompound(all_shapes)
        bbox = compound.BoundBox
        print(f"\n[최종 모델 BoundBox]")
        print(f"  X: [{bbox.XMin:.1f}, {bbox.XMax:.1f}]  ({bbox.XLength/1000:.1f}m)")
        print(f"  Y: [{bbox.YMin:.1f}, {bbox.YMax:.1f}]  ({bbox.YLength/1000:.1f}m)")
        print(f"  Z: [{bbox.ZMin:.1f}, {bbox.ZMax:.1f}]  ({bbox.ZLength/1000:.1f}m)")

    FreeCAD.closeDocument(fc_doc.Name)
    print(f"\n총 소요 시간: {time.time() - t0:.1f}초")

try:
    main()
except Exception as e:
    import traceback
    with open("pyeongtaek_error.log", "w", encoding="utf-8") as f:
        traceback.print_exc(file=f)
    sys.exit(1)
