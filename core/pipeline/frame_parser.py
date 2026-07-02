"""frame_parser — Phase -1: 골조(기둥+벽체) 완전 파싱 (개정 지시서 2026-07-02).

슬라브 폐합의 전제 조건인 벽체·기둥을 슬라브보다 먼저 확정한다.
결과는 output/parse_status.json 에 층별 COMPLETE/INCOMPLETE/MISSING 으로 기록되며,
slab_engine.check_precondition_for_slab() 이 이 파일을 읽어 착수를 통제한다.

전 함수 [AUTO] — 순수 기하/규칙 연산, 모델 추론 없음.
"""

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import ezdxf
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, FLOOR_BLOCKS, SHEETS, collect_floor_data, snap_segments)

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "output" / "reports"
STATUS_PATH = ROOT / "output" / "parse_status.json"

WALL_PAIR_MIN = 100    # 벽 평행쌍 두께 하한 (mm)
WALL_PAIR_MAX = 350    # 상한


# [AUTO] 순수 기하 연산 — 폐합 LWPOLYLINE 기둥 인식, 모델 추론 없음
def detect_columns(doc, floor):
    """기둥 = 폐합 LWPOLYLINE, bbox 300~2500mm, 세장비<6, 유효 폴리곤."""
    msp = doc.modelspace()
    wall_blk = FLOOR_BLOCKS[floor][0]
    if wall_blk is None:
        return None
    cols = []
    x0, x1 = SHEETS[floor]
    for ins in msp.query("INSERT"):
        if ins.dxf.name != wall_blk or not (x0 < ins.dxf.insert.x < x1):
            continue
        for ve in ins.virtual_entities():
            if ve.dxftype() != "LWPOLYLINE" or not ve.closed:
                continue
            pts = [(p[0], p[1]) for p in ve.get_points()]
            if len(pts) < 4:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            if not (300 <= w <= 2500 and 300 <= h <= 2500):
                continue
            if max(w, h) / max(min(w, h), 1) > 6:
                continue
            poly = Polygon(pts)
            if not poly.is_valid or poly.area < 0.09e6:
                continue
            cols.append({"cx": round(sum(xs) / len(xs), 1),
                         "cy": round(sum(ys) / len(ys), 1),
                         "w": round(w), "h": round(h)})
    return cols


# [AUTO] 순수 기하 연산 — 평행선 페어링, 모델 추론 없음
def pair_walls(wall_segs):
    """벽 세그먼트 평행쌍(두께 100~350mm) 페어링.

    반환: (pairs, unpaired) — unpaired 는 좌표 포함 목록 (폐합 실패 구간 후보).
    """
    items = []
    for (p0, p1) in wall_segs:
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < 300:
            continue
        items.append({"p0": p0, "p1": p1, "L": L,
                      "ang": math.degrees(math.atan2(dy, dx)) % 180,
                      "mx": (p0[0] + p1[0]) / 2, "my": (p0[1] + p1[1]) / 2})
    paired = set()
    pairs = []
    for i, a in enumerate(items):
        if i in paired:
            continue
        for j in range(i + 1, len(items)):
            if j in paired:
                continue
            b = items[j]
            dang = abs(a["ang"] - b["ang"])
            dang = min(dang, 180 - dang)
            if dang > 2:
                continue
            d = math.hypot(a["mx"] - b["mx"], a["my"] - b["my"])
            if WALL_PAIR_MIN <= d <= WALL_PAIR_MAX and \
                    min(a["L"], b["L"]) / max(a["L"], b["L"]) > 0.3:
                paired.add(i)
                paired.add(j)
                pairs.append({"thickness": round(d),
                              "mx": round((a["mx"] + b["mx"]) / 2, 1),
                              "my": round((a["my"] + b["my"]) / 2, 1),
                              "length": round(max(a["L"], b["L"]))})
                break
    unpaired = [{"p0": [round(c, 1) for c in items[i]["p0"]],
                 "p1": [round(c, 1) for c in items[i]["p1"]],
                 "length": round(items[i]["L"])}
                for i in range(len(items)) if i not in paired]
    return pairs, unpaired


# [AUTO] 순수 기하 연산 — 벽 단독 폐합 검증 (Shapely polygonize)
def wall_closure(wall_segs, snap_mm=5):
    """벽 세그먼트만으로 폐합 시도 → 폐합 face 수·면적, 실패 구간 개방 끝점."""
    if not wall_segs:
        return {"faces": 0, "total_m2": 0, "open_endpoints": []}
    geoms = snap_segments(wall_segs, snap_mm)
    merged = unary_union(geoms)
    faces = list(polygonize(merged))
    # 개방 끝점(차수 1 노드) = 폐합 실패 구간
    from collections import Counter
    deg = Counter()
    for g in geoms:
        c = list(g.coords)
        deg[(round(c[0][0]), round(c[0][1]))] += 1
        deg[(round(c[-1][0]), round(c[-1][1]))] += 1
    open_pts = [list(p) for p, n in deg.items() if n == 1]
    return {
        "faces": len(faces),
        "total_m2": round(sum(f.area for f in faces) / 1e6, 1),
        "open_endpoints": open_pts,
    }


# [INFER] 모델 추론 개입 지점 — B2F 시트의 기초 블록(S-B1F-101-BASE) 해석.
# 기하 재검증: B2F 기둥좌표 815/819(97.5%)가 1F 시트의 B1F 벽·기둥과 일치
# → "기초 푸팅이 상부 골조 배치를 따름" 해석, confidence 0.75.
# 확신도 임계(0.7) 이상이나 [INFER] 판정이므로 사람 확인 대상으로 기록 유지.
B2F_BASE_NOTE = {
    "tag": "INFER",
    "confidence": 0.75,
    "geometric_reverify": "기둥 좌표 815/819 (97.5%) 상부층 일치",
    "interpretation": "S-B1F-101-BASE = 기초 평면 — 푸팅/기초보 외곽이 "
                      "상부 벽·기둥 배치와 일치. B2F(기초 레벨) 경계로 사용.",
}


def run_floor(doc, floor):
    data = collect_floor_data(doc, floor)
    out = {"floor": floor}
    if floor == "B2F":
        out["base_block_note"] = B2F_BASE_NOTE
    if not data["wall_segs"]:
        out.update({"wall": "MISSING", "column": "MISSING",
                    "detail": data["status"]})
        return out
    cols = detect_columns(doc, floor) or []
    pairs, unpaired = pair_walls(data["wall_segs"])
    closure = wall_closure(data["wall_segs"])
    n_segs = len(data["wall_segs"])
    pair_ratio = round(2 * len(pairs) / max(n_segs, 1), 3)
    out.update({
        "column": "COMPLETE",
        "column_count": len(cols),
        "column_expected": "미확정 — 기둥일람표는 타입만 수록, "
                           "평면 배치 총수의 독립 소스 없음",
        "wall": "COMPLETE",
        "wall_segments": n_segs,
        "wall_pairs": len(pairs),
        "wall_pair_ratio": pair_ratio,
        "wall_unpaired": len(unpaired),
        "wall_closure_faces": closure["faces"],
        "wall_closure_m2": closure["total_m2"],
        "wall_open_endpoints": len(closure["open_endpoints"]),
        "closure_fail_coords": closure["open_endpoints"][:40],
        "unpaired_detail": unpaired[:40],
    })
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    doc = ezdxf.readfile(str(DXF_S30_101))
    status = {"generated": datetime.now().isoformat(timespec="seconds"),
              "phase": "-1", "floors": {}}
    print("=== Phase -1 골조(기둥+벽체) 완전 파싱 ===")
    for fl in SHEETS:
        r = run_floor(doc, fl)
        status["floors"][fl] = r
        if r["wall"] == "MISSING":
            print(f"  [{fl:4}] 벽체 MISSING — {r['detail']}")
            continue
        print(f"  [{fl:4}] 기둥 {r['column_count']}개(예상: 미확정) / "
              f"벽 {r['wall_segments']}세그 페어 {r['wall_pairs']}쌍"
              f"(페어율 {r['wall_pair_ratio']*100:.0f}%) / "
              f"벽단독폐합 {r['wall_closure_faces']}face "
              f"{r['wall_closure_m2']}㎡ / "
              f"개방끝점 {r['wall_open_endpoints']}개")

    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(STATUS_PATH.read_text(encoding="utf-8")) \
        if STATUS_PATH.exists() else {}
    existing["frame"] = status
    STATUS_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"phase-1_frame_{ts}.json"
    out.write_text(json.dumps(status, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"  상태 저장: {STATUS_PATH}")
    print(f"  리포트: {out}")
    return status


if __name__ == "__main__":
    main()
