"""
build_v14_integrated.py — v4 정밀 모델링 통합 빌더
===================================================
1. PKG 다중 시트 분리 (X >= 1000000 기준 -630,000mm 오프셋 적용)
2. 101동 인접 주차장 클립 필터 적용 (B2F/B1F 개별 클립)
3. DONG-PKG 중복 부재 제거 (COLUMN, BEAM, WALL 중첩 검출)
4. SLAB 실제 형태 LWPOLYLINE 추출 및 오프셋 보정 (T=150mm)
5. FreeCAD 3D STEP 내보내기 + 정밀 BOQ 집계

실행:
  "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/build_v14_integrated.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ezdxf
import FreeCAD
import Part

from core.pipeline.boq_solid_builder import beam_solid, box_solid, prism_solid
from core.pipeline.member_data import Member, MemberCollection
from core.pipeline.wall_thickness import estimate_wall_thickness

# ─────────────────────────────────────────────────────────────
# 설정 및 경로
# ─────────────────────────────────────────────────────────────
ACCUMULATED = "output/members_accumulated.json"
DXF_PKG = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
COORD_CFG = "output/coord_config.json"

STEP_OUT = "output/v14_integrated.step"
BOQ_OUT = "output/v14_integrated_boq.json"

TX_PKG = -447970.0
TY_PKG = 3621813.0

b2f_clip = (552082.0, -1376738.0, 712082.0, -1216738.0)
b1f_clip = (1182082.0, -1376738.0, 1342082.0, -1216738.0)

SLAB_THICKNESS_MM = 150
SLAB_LAYER = "S-PC-SLAB"

# ─────────────────────────────────────────────────────────────
# 좌표 및 클립 함수
# ─────────────────────────────────────────────────────────────
def get_pkg_sheet_info(x: float) -> tuple[str, float, tuple[float, float, float, float]]:
    """X 좌표 기준으로 PKG 시트 이름, X 오프셋 보정값, 클립 범위를 결정."""
    if x < 1000000:
        return "B2F-Sheet", 0.0, b2f_clip
    else:
        return "B1F-Sheet", -630000.0, b1f_clip

def transform_coords(x: float, y: float, source: str) -> tuple[float, float]:
    if source == "DONG":
        return x, y
    _, dx, _ = get_pkg_sheet_info(x)
    return x + TX_PKG + dx, y + TY_PKG

def in_clip_pkg(x: float, y: float) -> bool:
    _, _, clip = get_pkg_sheet_info(x)
    return clip[0] <= x <= clip[2] and clip[1] <= y <= clip[3]

def dist_pt(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

# ─────────────────────────────────────────────────────────────
# 슬라브 다각형 면적 및 정렬 함수
# ─────────────────────────────────────────────────────────────
def shoelace_area(pts: list[tuple[float, float]]) -> float:
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0

def reorder_by_angle(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))

# ─────────────────────────────────────────────────────────────
# 메인 빌드 파이프라인
# ─────────────────────────────────────────────────────────────
def main():
    t0 = time.time()
    print("=" * 60)
    print("v14: 정밀 모델링 통합 빌더 개시 (Track 1-v4)")
    print("=" * 60)

    # 1. 부재 목록 로드
    if not Path(ACCUMULATED).exists():
        print(f"오류: {ACCUMULATED} 파일이 존재하지 않습니다.")
        return

    with open(ACCUMULATED, encoding="utf-8") as f:
        acc_data = json.load(f)
    raw_members = acc_data.get("members", []) if isinstance(acc_data, dict) else acc_data
    print(f"원본 부재 로드: {len(raw_members)}건")

    # 2. PKG 클립 필터 적용 및 좌표 변환 + 엄격한 노이즈 길이 필터 (DONG, PKG 공통)
    MIN_WALL_LEN_MM = 1200.0
    MIN_BEAM_LEN_MM = 2000.0

    dong_members: list[dict] = []
    pkg_candidates: list[dict] = []

    for m in raw_members:
        src = m.get("source")
        mtype = m.get("type")
        length = float(m.get("length_mm") or 0.0)

        if mtype == "SLAB":
            # SLAB은 DXF에서 원본 LWPOLYLINE을 직접 긁어올 것이므로 accumulated 리스트의 SLAB은 패스
            continue

        # DONG/PKG 공통 길이 노이즈 필터링
        if mtype == "WALL" and length < MIN_WALL_LEN_MM:
            continue
        if mtype == "BEAM" and length < MIN_BEAM_LEN_MM:
            continue

        if src == "DONG":
            # DONG은 좌표 변환 없이 그대로 사용
            m["ax"], m["ay"] = m["x"], m["y"]
            dong_members.append(m)
        elif src == "PKG":
            # PKG는 클립 필터 통과하는 것만
            if in_clip_pkg(m["x"], m["y"]):
                ax, ay = transform_coords(m["x"], m["y"], "PKG")
                m["ax"], m["ay"] = ax, ay
                pkg_candidates.append(m)

    print(f"1차 필터링 (클립 & 길이 필터 {MIN_WALL_LEN_MM}mm/{MIN_BEAM_LEN_MM}mm 적용 후): DONG={len(dong_members)}건, PKG={len(pkg_candidates)}건")

    # 3. DONG-PKG 중복 부재 제거
    # 기둥 중복 제거 (허용 오차 500mm로 확대)
    dong_cols = [m for m in dong_members if m["type"] == "COLUMN"]
    pkg_cols = [m for m in pkg_candidates if m["type"] == "COLUMN"]
    unique_pkg_cols = []
    dup_col_cnt = 0

    for pc in pkg_cols:
        is_dup = False
        p_pt = (pc["ax"], pc["ay"])
        for dc in dong_cols:
            d_pt = (dc["ax"], dc["ay"])
            z_overlap = max(0, min(dc["z_top"], pc["z_top"]) - max(dc["z_bot"], pc["z_bot"]))
            if z_overlap > 0 and dist_pt(p_pt, d_pt) < 500.0:
                is_dup = True
                break
        if is_dup:
            dup_col_cnt += 1
        else:
            unique_pkg_cols.append(pc)

    # 보 중복 제거 (허용 오차 1000mm, 각도 15도 적용)
    dong_beams = [m for m in dong_members if m["type"] == "BEAM"]
    pkg_beams = [m for m in pkg_candidates if m["type"] == "BEAM"]
    unique_pkg_beams = []
    dup_beam_cnt = 0

    for pb in pkg_beams:
        is_dup = False
        p_pt = (pb["ax"], pb["ay"])
        p_ang = float(pb.get("angle_deg") or 0.0)
        for db in dong_beams:
            d_pt = (db["ax"], db["ay"])
            z_overlap = max(0, min(db["z_top"], pb["z_top"]) - max(db["z_bot"], pb["z_bot"]))
            d_ang = float(db.get("angle_deg") or 0.0)
            ang_diff = abs(p_ang - d_ang) % 180
            if ang_diff > 90:
                ang_diff = 180 - ang_diff
            
            if z_overlap > 0 and dist_pt(p_pt, d_pt) < 1000.0 and ang_diff < 15.0:
                is_dup = True
                break
        if is_dup:
            dup_beam_cnt += 1
        else:
            unique_pkg_beams.append(pb)

    # 벽체 중복 제거 (허용 오차 800mm, 각도 15도 적용)
    dong_walls = [m for m in dong_members if m["type"] == "WALL"]
    pkg_walls = [m for m in pkg_candidates if m["type"] == "WALL"]
    unique_pkg_walls = []
    dup_wall_cnt = 0

    for pw in pkg_walls:
        is_dup = False
        p_pt = (pw["ax"], pw["ay"])
        p_ang = float(pw.get("angle_deg") or 0.0)
        for dw in dong_walls:
            d_pt = (dw["ax"], dw["ay"])
            z_overlap = max(0, min(dw["z_top"], pw["z_top"]) - max(dw["z_bot"], pw["z_bot"]))
            d_ang = float(dw.get("angle_deg") or 0.0)
            ang_diff = abs(p_ang - d_ang) % 180
            if ang_diff > 90:
                ang_diff = 180 - ang_diff
            
            if z_overlap > 0 and dist_pt(p_pt, d_pt) < 800.0 and ang_diff < 15.0:
                is_dup = True
                break
        if is_dup:
            dup_wall_cnt += 1
        else:
            unique_pkg_walls.append(pw)

    print(f"중복 제거 결과:")
    print(f"  기둥 중복 제거: {dup_col_cnt}개 (잔여 PKG 기둥 {len(unique_pkg_cols)}개)")
    print(f"  보 중복 제거:  {dup_beam_cnt}개 (잔여 PKG 보 {len(unique_pkg_beams)}개)")
    print(f"  벽체 중복 제거: {dup_wall_cnt}개 (잔여 PKG 벽체 {len(unique_pkg_walls)}개)")

    # 연결성(Connection) 필터 적용 (기둥과 닿지 않는 외톨이 보/벽체 노이즈 소거)
    cols = dong_cols + unique_pkg_cols
    col_centers = [(c["ax"], c["ay"], c["z_bot"], c["z_top"]) for c in cols]
    
    beams_candidates = dong_beams + unique_pkg_beams
    walls_candidates = dong_walls + unique_pkg_walls
    
    connected_beams = []
    connected_walls = []
    skipped_isolated_beam = 0
    skipped_isolated_wall = 0
    
    for m in beams_candidates:
        ax, ay = m["ax"], m["ay"]
        L = float(m.get("length_mm") or 1000.0)
        ang = math.radians(float(m.get("angle_deg") or 0.0))
        p0 = (ax - (L / 2) * math.cos(ang), ay - (L / 2) * math.sin(ang))
        p1 = (ax + (L / 2) * math.cos(ang), ay + (L / 2) * math.sin(ang))
        z_bot, z_top = m["z_bot"], m["z_top"]
        
        is_connected = False
        for cx, cy, cz_bot, cz_top in col_centers:
            z_overlap = max(0, min(z_top, cz_top) - max(z_bot, cz_bot))
            if z_overlap > 0:
                if dist_pt(p0, (cx, cy)) < 1500.0 or dist_pt(p1, (cx, cy)) < 1500.0:
                    is_connected = True
                    break
        if is_connected:
            connected_beams.append(m)
        else:
            skipped_isolated_beam += 1

    for m in walls_candidates:
        ax, ay = m["ax"], m["ay"]
        L = float(m.get("length_mm") or 1000.0)
        ang = math.radians(float(m.get("angle_deg") or 0.0))
        p0 = (ax - (L / 2) * math.cos(ang), ay - (L / 2) * math.sin(ang))
        p1 = (ax + (L / 2) * math.cos(ang), ay + (L / 2) * math.sin(ang))
        z_bot, z_top = m["z_bot"], m["z_top"]
        
        is_connected = False
        for cx, cy, cz_bot, cz_top in col_centers:
            z_overlap = max(0, min(z_top, cz_top) - max(z_bot, cz_bot))
            if z_overlap > 0:
                if dist_pt(p0, (cx, cy)) < 1500.0 or dist_pt(p1, (cx, cy)) < 1500.0:
                    is_connected = True
                    break
        if is_connected:
            connected_walls.append(m)
        else:
            skipped_isolated_wall += 1

    print(f"연결성 필터 결과:")
    print(f"  기둥 연결 안 된 외톨이 보 스킵: {skipped_isolated_beam}개 (남은 보: {len(connected_beams)}개)")
    print(f"  기둥 연결 안 된 외톨이 벽체 스킵: {skipped_isolated_wall}개 (남은 벽체: {len(connected_walls)}개)")

    # 정제된 부재 통합
    fnd_members = [m for m in dong_members if m["type"] == "FND"]
    final_structured_members = (
        cols +
        connected_beams +
        connected_walls +
        fnd_members
    )
    print(f"통합 정제된 부재 (SLAB 제외): {len(final_structured_members)}건")

    # 4. SLAB 실제 LWPOLYLINE 직접 채굴 (좌표 맵핑 및 시트 오프셋 보정)
    print(f"\n[SLAB] DXF 로드 및 실제 형상 추출: {DXF_PKG}")
    doc_pkg = ezdxf.readfile(DXF_PKG)
    msp_pkg = doc_pkg.modelspace()
    
    raw_slab_polys = []
    for e in msp_pkg.query("LWPOLYLINE"):
        if e.dxf.layer != SLAB_LAYER:
            continue
        pts = [(p[0], p[1]) for p in e.get_points()]
        if len(pts) < 3:
            continue
        
        # 클립 필터
        cx_avg = sum(p[0] for p in pts) / len(pts)
        cy_avg = sum(p[1] for p in pts) / len(pts)
        if in_clip_pkg(cx_avg, cy_avg):
            raw_slab_polys.append(pts)

    print(f"  클립 내부 S-PC-SLAB 폴리라인 수집: {len(raw_slab_polys)}개")

    # FreeCAD 도큐먼트 개설
    fc_doc = FreeCAD.newDocument("V14Integrated")
    shapes_with_names = []
    enriched_slabs = []
    slab_failed = 0

    z_slab_bot = -9050 - SLAB_THICKNESS_MM
    z_slab_top = -9050

    for idx, raw_pts in enumerate(raw_slab_polys, 1):
        # 중심 X 기준으로 시트 오프셋 계산
        cx_avg = sum(p[0] for p in raw_pts) / len(raw_pts)
        _, dx, _ = get_pkg_sheet_info(cx_avg)
        
        # 좌표 통일
        pts = [(x + TX_PKG + dx, y + TY_PKG) for x, y in raw_pts]

        # self-crossing 보정
        area_before = shoelace_area(pts)
        if area_before < 1.0:
            pts = reorder_by_angle(pts)
            area_after = shoelace_area(pts)
        else:
            area_after = area_before

        area_m2 = area_after / 1_000_000.0
        vol_m3 = area_m2 * (SLAB_THICKNESS_MM / 1000.0)

        # 3D 솔리드 생성
        shape = prism_solid(pts, zb=z_slab_bot, zt=z_slab_top)
        slab_id = f"SL-PKG-B2F-{idx:04d}"

        if shape is None:
            slab_failed += 1
            continue

        feat = fc_doc.addObject("Part::Feature", slab_id)
        feat.Shape = shape
        shapes_with_names.append((shape, slab_id))

        enriched_slabs.append({
            "id": slab_id, "type": "SLAB", "floor": "B2F", "source": "PKG",
            "x": round(sum(p[0] for p in pts)/len(pts), 1),
            "y": round(sum(p[1] for p in pts)/len(pts), 1),
            "z_bot": z_slab_bot, "z_top": z_slab_top,
            "area_m2": round(area_m2, 4),
            "volume_m3": round(vol_m3, 4),
            "layer": SLAB_LAYER,
        })

    print(f"  SLAB 솔리드 빌드 완료: 성공 {len(enriched_slabs)} / 실패 {slab_failed}")

    # 5. COLUMN, BEAM, WALL, FND 3D 솔리드 빌드
    n_col = n_beam = n_wall = n_fnd = 0
    builder_boq_items = []

    for m in final_structured_members:
        mtype = m["type"]
        mid = m["id"]
        ax, ay = m["ax"], m["ay"]
        zb = float(m["z_bot"])
        zt = float(m["z_top"])

        # ── 기둥 ──────────────────────────────────
        if mtype == "COLUMN":
            sec = m.get("section", "600x600")
            # section parsing
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
                    "id": mid, "type": "COLUMN", "floor": m["floor"], "source": m["source"],
                    "x": ax, "y": ay, "z_bot": zb, "z_top": zt,
                    "section": sec, "volume_m3": round(vol_m3, 4), "layer": m.get("layer", "")
                })

        # ── 보 ────────────────────────────────────
        elif mtype == "BEAM":
            L = float(m.get("length_mm") or 1000.0)
            if L < 100:
                continue
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

            # 보 Z 정합 (슬라브 매입 트리밍 보정)
            # 보의 Z 범위는 z_top - bh 에서 z_top - SLAB_T (보 높이에서 슬라브 두께 150mm 제외)
            s = beam_solid(x0, y0, x1, y1, bw=bw, bh=bh, zb=zt - bh, zt=zt - SLAB_THICKNESS_MM)
            if s:
                feat = fc_doc.addObject("Part::Feature", mid)
                feat.Shape = s
                shapes_with_names.append((s, mid))
                n_beam += 1

                vol_m3 = (bw * bh * L) / 1e9
                builder_boq_items.append({
                    "id": mid, "type": "BEAM", "floor": m["floor"], "source": m["source"],
                    "x": ax, "y": ay, "z_bot": zt - bh, "z_top": zt - SLAB_THICKNESS_MM,
                    "section": sec, "volume_m3": round(vol_m3, 4), "layer": m.get("layer", "")
                })

        # ── 벽체 ──────────────────────────────────
        elif mtype == "WALL":
            L = float(m.get("length_mm") or 1000.0)
            if L < 100:
                continue
            thickness = estimate_wall_thickness(m.get("layer", ""))
            ang = math.radians(float(m.get("angle_deg") or 0.0))
            x0 = ax - (L / 2) * math.cos(ang)
            y0 = ay - (L / 2) * math.sin(ang)
            x1 = ax + (L / 2) * math.cos(ang)
            y1 = ay + (L / 2) * math.sin(ang)

            s = beam_solid(x0, y0, x1, y1, bw=thickness, bh=thickness, zb=zb, zt=zt - SLAB_THICKNESS_MM)
            if s:
                feat = fc_doc.addObject("Part::Feature", mid)
                feat.Shape = s
                shapes_with_names.append((s, mid))
                n_wall += 1

                height_w = (zt - SLAB_THICKNESS_MM) - zb
                vol_m3 = (thickness * height_w * L) / 1e9
                builder_boq_items.append({
                    "id": mid, "type": "WALL", "floor": m["floor"], "source": m["source"],
                    "x": ax, "y": ay, "z_bot": zb, "z_top": zt - SLAB_THICKNESS_MM,
                    "section": f"{int(thickness)}x{int(height_w)}", "volume_m3": round(vol_m3, 4), "layer": m.get("layer", "")
                })

        # ── 기초 ──────────────────────────────────
        elif mtype == "FND":
            s = box_solid(ax, ay, zb, zt, 1000, 1000)  # 임시 box 형태
            if s:
                feat = fc_doc.addObject("Part::Feature", mid)
                feat.Shape = s
                shapes_with_names.append((s, mid))
                n_fnd += 1
                
                vol_m3 = (1000 * 1000 * (zt - zb)) / 1e9
                builder_boq_items.append({
                    "id": mid, "type": "FND", "floor": m["floor"], "source": m["source"],
                    "x": ax, "y": ay, "z_bot": zb, "z_top": zt,
                    "volume_m3": round(vol_m3, 4), "layer": m.get("layer", "")
                })

    print(f"구조 부재 솔리드 빌드 완료:")
    print(f"  COLUMN: {n_col}개")
    print(f"  BEAM:   {n_beam}개")
    print(f"  WALL:   {n_wall}개")
    print(f"  FND:    {n_fnd}개")

    # FreeCAD Recompute
    fc_doc.recompute()

    # 6. STEP 파일 내보내기
    print(f"\n[STEP] 저장 중: {STEP_OUT} ...")
    Part.export([o for o in fc_doc.Objects], str(STEP_OUT))
    size_mb = Path(STEP_OUT).stat().st_size / 1024 / 1024
    print(f"[STEP] 저장 완료: {STEP_OUT} ({size_mb:.1f} MB)")

    # 7. BOQ 데이터 집계 및 저장
    total_boq_list = builder_boq_items + enriched_slabs
    by_type_boq = {}
    for item in total_boq_list:
        t = item["type"]
        by_type_boq.setdefault(t, {"count": 0, "volume_m3": 0.0, "area_m2": 0.0})
        by_type_boq[t]["count"] += 1
        if "volume_m3" in item:
            by_type_boq[t]["volume_m3"] += item["volume_m3"]
        if "area_m2" in item:
            by_type_boq[t]["area_m2"] += item["area_m2"]

    # 소수점 보정
    for t in by_type_boq:
        by_type_boq[t]["volume_m3"] = round(by_type_boq[t]["volume_m3"], 2)
        by_type_boq[t]["area_m2"] = round(by_type_boq[t]["area_m2"], 2)

    boq_output_data = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "total_count": len(total_boq_list),
        "by_type": by_type_boq,
        "members": total_boq_list
    }

    with open(BOQ_OUT, "w", encoding="utf-8") as f:
        json.dump(boq_output_data, f, ensure_ascii=False, indent=2)

    print(f"\n[BOQ] 저장 완료: {BOQ_OUT}")
    print("수량 집계 요약:")
    for t, stat in by_type_boq.items():
        print(f"  {t:7s}: count={stat['count']:5d}개, volume={stat['volume_m3']:8.2f} m³, area={stat['area_m2']:8.2f} m²")

    # BoundBox 연산 및 출력
    all_shapes = [o.Shape for o in fc_doc.Objects if hasattr(o, "Shape") and o.Shape]
    if all_shapes:
        compound = Part.makeCompound(all_shapes)
        bbox = compound.BoundBox
        print(f"\n[최종 모델 BoundBox]")
        print(f"  X: [{bbox.XMin:.1f}, {bbox.XMax:.1f}]  ({bbox.XLength/1000:.1f}m)")
        print(f"  Y: [{bbox.YMin:.1f}, {bbox.YMax:.1f}]  ({bbox.YLength/1000:.1f}m)")
        print(f"  Z: [{bbox.ZMin:.1f}, {bbox.ZMax:.1f}]  ({bbox.ZLength/1000:.2f}m)")

    FreeCAD.closeDocument(fc_doc.Name)
    print(f"\n총 소요 시간: {time.time() - t0:.1f}초")

main()
