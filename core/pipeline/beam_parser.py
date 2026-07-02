"""beam_parser — Phase -0.5: 보 완전 파싱 + 슬라브 경계 사전 폐합 검증.

개정 지시서 2026-07-02:
  1. 일반보/테두리보 구분 인식
  2. Phase -1 벽체와 결합해 "슬라브 경계(벽 OR 보) 완전 폐합" 사전 검증
  3. 벽도 보도 없는 경계 미완성 구간 목록화 → Phase 0 원본 재확인 플래그

전 함수 [AUTO] — 순수 기하 연산. 테두리보 구분은 외곽 근접 기하 판정
(일람표 EB 마크의 평면 위치 표기가 없어 텍스트 매칭 불가 — 기하 기준 명시).
"""

import json
import math
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import ezdxf
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, FLOOR_BLOCKS, SHEETS, _entity_lines, _in_sheet,
    collect_floor_data, snap_segments)

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "output" / "reports"
STATUS_PATH = ROOT / "output" / "parse_status.json"

EDGE_BAND_MM = 600     # 건물 외피 경계에서 이 거리 이내 중점 → 테두리보 후보


# [AUTO] 순수 기하 연산 — 거더/보 블록 세그먼트 수집
# 블록 내부에 도곽 밖 비표시 콘텐츠(편집 잔재)가 다량 존재함을 실측 확인:
#   S-1F-GIRDER 1719세그 중 1F 도곽 내 84 / 타 대역 1635 (2026-07-02)
# → 시트 도곽(_in_sheet) 필터 = 인쇄 도면과 동일한 가시 콘텐츠 기준.
def collect_beams(doc, floor):
    """collect_floor_data의 beam_segs(PC거더 포함) + 브리지 연결선 사용."""
    data = collect_floor_data(doc, floor)
    segs = data.get("beam_segs", []) + data.get("bridge_segs", [])
    return segs, len(data.get("bridge_segs", []))


# [AUTO] 순수 기하 연산 — 외피 근접 기준 테두리보/일반보 구분
def classify_edge_beams(beam_segs, wall_segs):
    """건물 외피(벽+보 전체 convex hull 경계) 근접 세그먼트 = 테두리보."""
    all_pts = [p for s in beam_segs + wall_segs for p in s]
    if len(all_pts) < 3:
        return [], beam_segs
    hull = unary_union([LineString([a, b])
                        for a, b in beam_segs + wall_segs]).convex_hull
    boundary = hull.exterior
    edge, normal = [], []
    for (p0, p1) in beam_segs:
        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        from shapely.geometry import Point
        if boundary.distance(Point(mid)) <= EDGE_BAND_MM:
            edge.append((p0, p1))
        else:
            normal.append((p0, p1))
    return edge, normal


# [AUTO] 순수 기하 연산 — 벽+보 결합 사전 폐합 검증
def precheck_closure(wall_segs, beam_segs, snap_mm=5):
    """슬라브 경계 요소(벽 OR 보) 결합 폐합 가능성 사전 검증.

    반환: 폐합 face 수/면적, 개방 끝점(벽도 보도 안 닿는 곳) 좌표 목록.
    """
    segs = wall_segs + beam_segs
    if not segs:
        return None
    geoms = snap_segments(segs, snap_mm)
    merged = unary_union(geoms)
    faces = [f for f in polygonize(merged) if f.area > 0.5e6]
    deg = Counter()
    for g in geoms:
        c = list(g.coords)
        deg[(round(c[0][0]), round(c[0][1]))] += 1
        deg[(round(c[-1][0]), round(c[-1][1]))] += 1
    open_pts = [list(p) for p, n in deg.items() if n == 1]
    return {
        "closable_faces": len(faces),
        "closable_m2": round(sum(f.area for f in faces) / 1e6, 1),
        "open_endpoints": len(open_pts),
        "open_coords": open_pts[:500],
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    # Phase -1 완료 확인 (착수 조건)
    if not STATUS_PATH.exists() or "frame" not in json.loads(
            STATUS_PATH.read_text(encoding="utf-8")):
        raise SystemExit("Phase -1 미완료 — frame_parser.py 먼저 실행할 것")

    doc = ezdxf.readfile(str(DXF_S30_101))
    status = {"generated": datetime.now().isoformat(timespec="seconds"),
              "phase": "-0.5", "floors": {}}
    print("=== Phase -0.5 보 완전 파싱 + 경계 사전검증 ===")
    for fl in SHEETS:
        beam_segs, out_frame = collect_beams(doc, fl)
        if not beam_segs:
            if fl == "B2F":
                # [AUTO] 규칙 판정 — 기초 레벨은 별도 보 블록 없음.
                # 기초보/푸팅 외곽이 base 블록(벽 소스)에 포함되어 경계 충족.
                status["floors"][fl] = {
                    "beam": "COMPLETE",
                    "beam_segments": 0,
                    "detail": "기초 레벨 — 기초보가 S-B1F-101-BASE 블록에 "
                              "포함(Phase -1 벽 소스), 별도 보 블록 없음"}
                print(f"  [{fl:4}] 보 0세그 — 기초 레벨 (base 블록이 경계 담당)")
            else:
                status["floors"][fl] = {
                    "beam": "MISSING",
                    "detail": "보 블록 없음 — 세대부 S20 조합 필요"}
                print(f"  [{fl:4}] 보 MISSING (S20 조합 필요)")
            continue
        data = collect_floor_data(doc, fl)
        edge, normal = classify_edge_beams(beam_segs, data["wall_segs"])
        pre = precheck_closure(data["wall_segs"], beam_segs)
        status["floors"][fl] = {
            "beam": "COMPLETE",
            "beam_segments": len(beam_segs),
            "edge_beam_segments": len(edge),
            "normal_beam_segments": len(normal),
            "bridge_segments": out_frame,
            "bridge_note": "보 끊김 공선 연결선 (bridge_collinear) — 감사용 분리",
            "beam_expected": "미확정 — 평면 배치 총수 독립 소스 없음 "
                             "(일람표는 타입 수록)",
            "precheck": pre,
        }
        print(f"  [{fl:4}] 보 {len(beam_segs)}세그 "
              f"(테두리 {len(edge)} / 일반 {len(normal)}) / "
              f"결합폐합 {pre['closable_faces']}face {pre['closable_m2']}㎡ / "
              f"경계 개방점 {pre['open_endpoints']}개")

    existing = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    existing["beam"] = status
    STATUS_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"phase-0.5_beam_{ts}.json"
    out.write_text(json.dumps(status, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"  상태 저장: {STATUS_PATH}")
    print(f"  리포트: {out}")
    return status


if __name__ == "__main__":
    main()
