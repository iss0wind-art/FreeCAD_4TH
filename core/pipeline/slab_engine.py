"""slab_engine — 101동 슬라브 정밀 절삭 엔진 (Phase 0~3).

작업지시서 2026-07-02 기준:
  Phase 0: 색칠 트릭 제거 — 실제 Boolean 절삭 (Shapely difference)
  Phase 1: 내측 페이스 기준 폐합 (벽체 잉크 슬리버 제외 = 내측면 경계)
  Phase 2: 갭 방어 — 끝점 스냅 5→10→20mm 단계 시도
  Phase 3: 오픈구(X표시) 처리 순서 고정
           ① 전체 폐합 탐색 → ② 내부 X마크 검사 → ③ 서브영역 제외

원칙:
  - 추정값 0: 데이터 없으면 "미확정" 플래그, 임의 보정 금지
  - 완료 증거: 절삭 전/후 면적 수치를 콘솔 + output/reports/*.json 이중 기록
"""

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import ezdxf
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

ROOT = Path(__file__).resolve().parents[2]
# 입력 도면은 원본 저장소에만 존재 (워크트리 미포함 대용량)
_DRAWING_ROOTS = [ROOT / "input_drawings",
                  Path(r"D:\Git\FreeCAD_4TH\input_drawings")]
DXF_S30_101 = next(
    (r / "S30-001~010-101동 구조평면도.dxf" for r in _DRAWING_ROOTS
     if (r / "S30-001~010-101동 구조평면도.dxf").exists()),
    _DRAWING_ROOTS[-1] / "S30-001~010-101동 구조평면도.dxf")
REPORT_DIR = ROOT / "output" / "reports"

# 시트 X구역 (modelspace). 시트 피치 = 정확히 126000mm (EV마크 간격으로 검증).
SHEET_PITCH = 126000
SHEETS = {
    "B2F": (30000, 155000),
    "B1F": (155000, 281000),
    "1F": (281000, 407000),
    "2F": (407000, 533000),
    "TYP": (533000, 659000),   # 기준층 (3F~15F)
    "16F": (659000, 785000),   # 최상층 슬라브
}
SHEET_Y = (2085000, 2142000)   # 건물 footprint Y대역

# 구조 부재 블록 (시트별 INSERT 전수조사 결과, 2026-07-02)
# 값: (벽체 블록, 거더 블록, 보 블록) — 없으면 None
FLOOR_BLOCKS = {
    "B2F": ("S-B1F-101-BASE", None, None),
    "B1F": ("S-B2F-WALL COL-250523", "S-B1F GIRDER", "S-B2F-BEAM"),
    "1F": ("S-B1F-WALL COL-250523", "S-1F-GIRDER-1007", "S-1F BEAM-1007"),
    "2F": (None, None, None),     # 세대부 S20 참조 — 미확정
    "TYP": (None, None, None),    # 세대부 S20 참조 — 미확정
    "16F": (None, None, None),    # 세대부 S20 참조 — 미확정
}

SNAP_STEPS = [5, 10, 20]          # Phase 2 단계별 스냅 거리 (mm)
WALL_SLIVER_ERODE = 150           # 침식 후 소멸 → 벽 슬리버 판정 (벽두께≥180 기준)
MIN_PANEL_AREA_MM2 = 0.5e6        # 0.5㎡ 미만 face는 노이즈

STATUS_PATH = ROOT / "output" / "parse_status.json"


class PreconditionError(RuntimeError):
    """Phase -1/-0.5 미완료 층의 슬라브 처리 시도 시 발생."""


# [AUTO] 순수 규칙 연산 — 사전조건 검사, 모델 추론 없음. 우회 금지 (개정 규칙 6).
def get_parse_status(floor: str, member: str) -> str:
    """parse_status.json 에서 층·부재 파싱 상태 조회."""
    if not STATUS_PATH.exists():
        return "NOT_RUN"
    st = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    section = {"wall": "frame", "column": "frame", "beam": "beam"}[member]
    if section not in st:
        return "NOT_RUN"
    rec = st[section]["floors"].get(floor, {})
    return rec.get(member, "MISSING")


# [AUTO] 개정 지시서 2026-07-02 §2.4 — Phase 0 착수 조건 강제.
def check_precondition_for_slab(floor: str) -> bool:
    """Phase 0(slab_engine) 실행 전 필수 사전조건 검사.

    벽체·보 파싱이 완료되지 않은 층은 슬라브 처리를 거부한다.
    이 검사를 우회하는 플래그·스킵 코드를 추가하지 않는다 (진행규칙 6).
    """
    wall_status = get_parse_status(floor, "wall")
    beam_status = get_parse_status(floor, "beam")
    if wall_status != "COMPLETE" or beam_status != "COMPLETE":
        raise PreconditionError(
            f"{floor}: 벽체({wall_status})/보({beam_status}) 파싱 미완료 — "
            f"슬라브 처리 거부. Phase -1, -0.5 먼저 완료할 것.")
    return True


# ── DXF 수집 ─────────────────────────────────────────────────────────────────

def _in_sheet(x, y, floor):
    x0, x1 = SHEETS[floor]
    return x0 < x < x1 and SHEET_Y[0] < y < SHEET_Y[1]


def _entity_lines(e):
    """LINE/LWPOLYLINE → [(p0, p1), ...] 세그먼트 목록."""
    if e.dxftype() == "LINE":
        s, t = e.dxf.start, e.dxf.end
        return [((s.x, s.y), (t.x, t.y))]
    if e.dxftype() == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in e.get_points()]
        if e.closed and len(pts) >= 3:
            pts = pts + [pts[0]]
        return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    return []


# [AUTO] 규칙 연산 — 레이어/블록 필터 수집, 모델 추론 없음
def collect_floor_data(doc, floor):
    """시트 1장에서 경계선·개구부 원시 데이터 수집."""
    msp = doc.modelspace()
    data = {
        "boundary_segs": [],   # 벽/거더/보/슬라브단부 — 폐합 경계 후보
        "ev_diagonals": [],    # A-HID-3 대각선 (X마크)
        "pd_polys": [],        # S-OPEN 개구부 폴리곤
        "stair_pts": [],       # A-STAIR 선 중점 (계단실 face 판정용)
        "wall_segs": [],       # 벽체만 (슬리버 잉크 판정용)
        "status": "OK",
    }

    # 1) 시트 원시 엔티티
    for e in msp:
        if e.dxftype() not in ("LINE", "LWPOLYLINE"):
            continue
        segs = _entity_lines(e)
        if not segs:
            continue
        mx = sum(s[0][0] + s[1][0] for s in segs) / (2 * len(segs))
        my = sum(s[0][1] + s[1][1] for s in segs) / (2 * len(segs))
        if not _in_sheet(mx, my, floor):
            continue
        layer = e.dxf.layer
        if layer == "00_SLAB END + ETC":
            data["boundary_segs"] += segs
        elif layer == "S-OPEN":
            pts = [(p[0], p[1]) for p in e.get_points()]
            if len(pts) >= 3:
                poly = Polygon(pts)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.geom_type == "MultiPolygon":
                    poly = max(poly.geoms, key=lambda g: g.area)
                if poly.area > 1e4:  # 100cm² 이상만
                    data["pd_polys"].append(poly)
            data["boundary_segs"] += segs
        elif layer == "A-HID-3":
            for (p0, p1) in segs:
                dx, dy = abs(p1[0] - p0[0]), abs(p1[1] - p0[1])
                if dx > 100 and dy > 100:
                    ang = math.degrees(math.atan2(dy, dx))
                    if 25 < ang < 65:
                        data["ev_diagonals"].append((p0, p1))
        elif layer == "A-STAIR":
            for (p0, p1) in segs:
                data["stair_pts"].append(((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2))

    # 2) 구조 블록 explode (벽·거더·보)
    wall_blk, girder_blk, beam_blk = FLOOR_BLOCKS[floor]
    if wall_blk is None:
        data["status"] = "미확정: 세대부 데이터 없음 — S20 단위세대구조평면도 조합 필요"
    for blk_name, kind in ((wall_blk, "wall"), (girder_blk, "girder"), (beam_blk, "beam")):
        if blk_name is None:
            continue
        found = False
        for ins in msp.query("INSERT"):
            if ins.dxf.name != blk_name:
                continue
            ix = ins.dxf.insert.x
            if not (SHEETS[floor][0] < ix < SHEETS[floor][1]):
                continue
            found = True
            for ve in ins.virtual_entities():
                if ve.dxftype() not in ("LINE", "LWPOLYLINE"):
                    continue
                segs = _entity_lines(ve)
                if not segs:
                    continue
                # 블록 내용도 시트 영역으로 클리핑 (범례·주기 등 원거리 요소 제외)
                mx = sum(s[0][0] + s[1][0] for s in segs) / (2 * len(segs))
                my = sum(s[0][1] + s[1][1] for s in segs) / (2 * len(segs))
                if not _in_sheet(mx, my, floor):
                    continue
                data["boundary_segs"] += segs
                if kind == "wall":
                    data["wall_segs"] += segs
        if not found:
            data["status"] = f"미확정: 블록 {blk_name} INSERT 미발견"
    return data


# ── Phase 2: 끝점 스냅 ────────────────────────────────────────────────────────

# [AUTO] 순수 기하 연산 — 끝점 그리드 스냅, 모델 추론 없음
def snap_segments(segs, tol):
    """끝점 그리드 클러스터링 스냅. 반환: LineString 목록."""
    grid = {}

    def canon(p):
        k = (round(p[0] / tol), round(p[1] / tol))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = grid.get((k[0] + dx, k[1] + dy))
                if q and math.hypot(p[0] - q[0], p[1] - q[1]) <= tol:
                    return q
        grid[k] = p
        return p

    out = []
    for p0, p1 in segs:
        a, b = canon(p0), canon(p1)
        if a != b:
            out.append(LineString([a, b]))
    return out


# [AUTO] 순수 기하 연산 — Shapely 폐합 통계
def closure_stats(segs, tol):
    """스냅 tol 적용 시 폐합 통계 (Phase 2 증거용)."""
    geoms = snap_segments(segs, tol) if tol > 0 else [
        LineString([p0, p1]) for p0, p1 in segs
    ]
    faces = list(polygonize(unary_union(geoms)))
    areas = [f.area for f in faces]
    return {
        "snap_mm": tol,
        "faces": len(faces),
        "max_face_m2": round(max(areas) / 1e6, 2) if areas else 0,
        "total_m2": round(sum(areas) / 1e6, 1),
    }, faces


# ── Phase 3: X마크 페어링 ─────────────────────────────────────────────────────

# [AUTO] 순수 기하 연산 — 대각선 교차쌍 판정
def pair_x_marks(diagonals):
    """교차 대각선 쌍 → 개구부 bbox 폴리곤. (순서 ②: 폐합 탐색 후 내부 검사에 사용)"""
    marks = []
    used = set()
    items = []
    for (p0, p1) in diagonals:
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        items.append({
            "mx": (p0[0] + p1[0]) / 2, "my": (p0[1] + p1[1]) / 2,
            "L": math.hypot(dx, dy), "sign": 1 if dy * dx > 0 else -1,
            "bbox": (min(p0[0], p1[0]), min(p0[1], p1[1]),
                     max(p0[0], p1[0]), max(p0[1], p1[1])),
        })
    for i, a in enumerate(items):
        if i in used:
            continue
        for j, b in enumerate(items):
            if j <= i or j in used or a["sign"] == b["sign"]:
                continue
            if math.hypot(a["mx"] - b["mx"], a["my"] - b["my"]) < 300 \
                    and abs(a["L"] - b["L"]) / max(a["L"], b["L"]) < 0.4:
                x0 = min(a["bbox"][0], b["bbox"][0])
                y0 = min(a["bbox"][1], b["bbox"][1])
                x1 = max(a["bbox"][2], b["bbox"][2])
                y1 = max(a["bbox"][3], b["bbox"][3])
                marks.append(Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
                used.add(i)
                used.add(j)
                break
    return marks


# ── Phase 0+1+3: face 분류와 절삭 ────────────────────────────────────────────

MAX_STAIR_FACE_M2 = 40e6      # 계단실 face 상한 (초과 시 미확정)
MAX_PANEL_M2 = 2000e6         # 단일 패널 상한 — 초과 face는 외곽 오폐합으로 간주


# [AUTO] 순수 기하 연산 — face 분류 (침식·잉크 판정)
def classify_faces(faces, stair_pts, wall_ink, envelope):
    """폐합 face 분류 (Phase 1 + Phase 3 ①②).

    - envelope(벽 bbox+여유) 밖 face → 도곽/치수선 오폐합, 제외
    - 계단선 ≥3 포함 & 40㎡ 이하 → 계단 개구부
    - 침식 소멸 or 벽잉크 60%+ → 벽 슬리버 (Phase 1 내측면 원칙)
    - 나머지 → 슬라브 패널
    """
    slab_faces, wall_slivers, stair_faces, rejected = [], [], [], []
    for f in faces:
        if f.area < MIN_PANEL_AREA_MM2 / 50:
            continue
        if envelope is not None and not envelope.contains(f.representative_point()):
            rejected.append(f)
            continue
        if f.area > MAX_PANEL_M2:
            rejected.append(f)
            continue
        n_stair = sum(1 for s in stair_pts if f.contains(Point(s)))
        if n_stair >= 3 and f.area <= MAX_STAIR_FACE_M2:
            stair_faces.append(f)
            continue
        eroded = f.buffer(-WALL_SLIVER_ERODE)
        if eroded.is_empty:
            wall_slivers.append(f)
            continue
        if wall_ink is not None and wall_ink.intersects(f) \
                and wall_ink.intersection(f).area > 0.6 * f.area:
            wall_slivers.append(f)
            continue
        if f.area >= MIN_PANEL_AREA_MM2:
            slab_faces.append(f)
        else:
            wall_slivers.append(f)
    return slab_faces, wall_slivers, stair_faces, rejected


# [AUTO] 순수 기하 연산 — Shapely difference 절삭
def boolean_cut(slab_faces, stair_faces, ev_marks, pd_polys):
    """Phase 0 + Phase 3 ③: 명시적 개구부 폴리곤을 실제 difference 절삭.

    반환: (절삭 후 패널 목록, 절삭 로그)
    로그의 removed_m2 = 슬라브와 개구부의 실제 교차 면적 (증거 수치).
    """
    log = []
    panels = list(slab_faces)

    def cut_poly(poly, otype):
        nonlocal panels
        removed = 0.0
        new_panels = []
        for p in panels:
            if p.intersects(poly):
                removed += p.intersection(poly).area
                diff = p.difference(poly)
                if diff.is_empty:
                    continue
                geoms = list(diff.geoms) if diff.geom_type == "MultiPolygon" else [diff]
                new_panels += [g for g in geoms if g.area > 1e4]
            else:
                new_panels.append(p)
        panels = new_panels
        if removed > 0.5 * poly.area:
            verdict = "성공"
        elif removed < 0.05 * poly.area:
            # 개구부가 자체 폐합 face로 이미 슬라브에서 분리된 상태 = 뚫려 있음
            verdict = "성공(자체 폐합으로 기제외)"
        else:
            verdict = "미확정(부분 교차)"
        log.append({
            "type": otype,
            "opening_m2": round(poly.area / 1e6, 2),
            "removed_m2": round(removed / 1e6, 2),
            "cut": verdict,
        })

    for m in ev_marks:
        cut_poly(m, "EV")
    for p in pd_polys:
        cut_poly(p, "PD")
    # 계단 face는 분류 단계에서 이미 제외됨 (지오메트리 제외 = 절삭)
    for f in stair_faces:
        log.append({
            "type": "STAIR",
            "opening_m2": round(f.area / 1e6, 2),
            "removed_m2": round(f.area / 1e6, 2),
            "cut": "성공(face 제외)",
        })
    return panels, log


# [AUTO] 순수 기하 연산 — 겹침 회귀 검증
def verify_no_overlap(panels, wall_slivers, tol_mm2=1.0):
    """Phase 1 회귀 검증: 슬라브 패널과 벽체 face의 겹침 면적 0 확인.

    polygonize 구조상 face는 서로소지만, 후속 로직 회귀를 수치로 잡는 안전망.
    반환: 위반 목록 [{panel_idx, sliver_idx, overlap_mm2}].
    """
    violations = []
    for i, p in enumerate(panels):
        for j, w in enumerate(wall_slivers):
            if p.intersects(w):
                a = p.intersection(w).area
                if a > tol_mm2:
                    violations.append({
                        "panel": i, "wall_face": j,
                        "overlap_mm2": round(a, 1),
                    })
    return violations


def run_floor(floor, doc=None):
    """층 1개 처리 → 리포트 dict.

    개정 규칙 6: check_precondition_for_slab() 통과 없이는 실행 불가.
    """
    check_precondition_for_slab(floor)   # PreconditionError 시 즉시 중단
    if doc is None:
        doc = ezdxf.readfile(str(DXF_S30_101))
    data = collect_floor_data(doc, floor)
    report = {
        "floor": floor,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "source": DXF_S30_101.name,
        "status": data["status"],
        # Phase 1 증거: 벽체 표기 방식 (양면 외곽선 = LINE쌍+폐합 LWPOLYLINE)
        "wall_style": {
            "wall_segments": len(data["wall_segs"]),
            "method": ("양면 외곽선(더블라인)" if data["wall_segs"] else "미확정"),
        },
        # Phase 3 증거: 처리 순서 구현 위치
        "phase3_order": "classify_faces(①폐합→②내부검사) → boolean_cut(③제외) "
                        "@ core/pipeline/slab_engine.py",
        "snap_evidence": [],
        "openings": [],
    }

    if not data["boundary_segs"]:
        report["status"] = "미확정: 경계선 0건"
        return report, None

    # Phase 2: 단계별 스냅 — 최대 face 면적이 뛰는 최소 tol 채택
    stats0, _ = closure_stats(data["boundary_segs"], 0)
    report["snap_evidence"].append(stats0)
    best_tol, best_faces = SNAP_STEPS[-1], None
    prev_total = stats0["total_m2"]
    for tol in SNAP_STEPS:
        st, faces = closure_stats(data["boundary_segs"], tol)
        report["snap_evidence"].append(st)
        if best_faces is None or st["total_m2"] > prev_total * 1.02:
            best_tol, best_faces = tol, faces
            prev_total = st["total_m2"]
    report["snap_mm_adopted"] = best_tol

    # 벽 잉크 + 건물 외피 (Phase 1 내측면 판정 · 도곽 오폐합 제거)
    wall_ink, envelope = None, None
    if data["wall_segs"]:
        wall_lines = [LineString([a, b]) for a, b in data["wall_segs"]]
        wall_ink = unary_union([ln.buffer(30, cap_style=2) for ln in wall_lines])
        xs = [c for a, b in data["wall_segs"] for c in (a[0], b[0])]
        ys = [c for a, b in data["wall_segs"] for c in (a[1], b[1])]
        envelope = Polygon([
            (min(xs) - 1000, min(ys) - 1000), (max(xs) + 1000, min(ys) - 1000),
            (max(xs) + 1000, max(ys) + 1000), (min(xs) - 1000, max(ys) + 1000)])

    # Phase 3 ① 폐합 → ② 내부 검사 → ③ 제외/절삭 (Phase 0)
    ev_marks = pair_x_marks(data["ev_diagonals"])
    slab_faces, slivers, stair_faces, rejected = classify_faces(
        best_faces, data["stair_pts"], wall_ink, envelope)

    area_before = sum(f.area for f in slab_faces) + sum(f.area for f in stair_faces)
    panels, cut_log = boolean_cut(slab_faces, stair_faces, ev_marks, data["pd_polys"])
    area_after = sum(p.area for p in panels)
    area_cut = area_before - area_after
    expected_cut = sum(o["removed_m2"] for o in cut_log) * 1e6

    # Phase 1 회귀 검증: 절삭 후 패널 ↔ 벽 face 겹침 0 확인
    overlap_violations = verify_no_overlap(panels, slivers)
    report["overlap_check"] = {
        "panels_checked": len(panels),
        "violations": len(overlap_violations),
        "detail": overlap_violations[:10],
    }

    report.update({
        "faces_total": len(best_faces),
        "slab_panels": len(panels),
        "wall_slivers": len(slivers),
        "rejected_outer_faces": len(rejected),
        "openings_found": {
            "EV_xmark": len(ev_marks),
            "PD_sopen": len(data["pd_polys"]),
            "stair_faces": len(stair_faces),
        },
        "openings": cut_log,
        "area_before_m2": round(area_before / 1e6, 2),
        "area_after_m2": round(area_after / 1e6, 2),
        "area_cut_m2": round(area_cut / 1e6, 2),
        "cut_consistency": "일치" if abs(area_cut - expected_cut) < 0.05e6 else "불일치",
    })

    # 미확정 층(세대부 없음)은 개구부 좌표만 유효 — 슬라브 지오메트리 출력 금지 (추정값0)
    if report["status"] != "OK":
        geo = {
            "floor": floor,
            "slab_panels": [],
            "slab_status": report["status"],
            "openings": (
                [{"type": "EV", "poly": list(m.exterior.coords)} for m in ev_marks]
                + [{"type": "PD", "poly": list(p.exterior.coords)}
                   for p in data["pd_polys"]]
            ),
        }
        return report, geo

    # 절삭 결과 지오메트리 (후속 Phase·FreeCAD·SketchUp용) — 구멍(interior) 포함
    geo = {
        "floor": floor,
        "slab_panels": [
            {"exterior": list(p.exterior.coords),
             "holes": [list(r.coords) for r in p.interiors]}
            for p in panels
        ],
        # 벽 슬리버 face = 실측 벽 발자국 (추정 없는 벽 솔리드 소스)
        "wall_faces": [
            list(w.exterior.coords) for w in slivers if w.area > 0.05e6
        ],
        "openings": (
            [{"type": "EV", "poly": list(m.exterior.coords)} for m in ev_marks]
            + [{"type": "PD", "poly": list(p.exterior.coords)} for p in data["pd_polys"]]
            + [{"type": "STAIR", "poly": list(f.exterior.coords)} for f in stair_faces]
        ),
    }
    return report, geo


def save_report(report, phase="0"):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"phase{phase}_{report['floor']}_{ts}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    floors = [a for a in argv if a in SHEETS] or list(SHEETS)
    doc = ezdxf.readfile(str(DXF_S30_101))
    geos = {}
    for fl in floors:
        try:
            check_precondition_for_slab(fl)
            print(f"\n=== {fl} === [사전조건 PASS]")
        except PreconditionError as e:
            print(f"\n=== {fl} === [사전조건 FAIL] {e}")
            save_report({
                "floor": fl,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "status": f"실행 거부 — {e}",
                "precondition": "FAIL",
            })
            continue
        report, geo = run_floor(fl, doc)
        report["precondition"] = "PASS"
        p = save_report(report)
        print(f"  상태: {report['status']}")
        if report.get("snap_evidence"):
            for st in report["snap_evidence"]:
                print(f"  스냅 {st['snap_mm']:2}mm: 폐합 {st['faces']}개, "
                      f"최대 {st['max_face_m2']}㎡, 총 {st['total_m2']}㎡")
        if "area_before_m2" in report:
            print(f"  채택 스냅: {report['snap_mm_adopted']}mm")
            print(f"  face 총 {report['faces_total']} = 슬라브패널 {report['slab_panels']}"
                  f" + 벽슬리버 {report['wall_slivers']}"
                  f" + 개구부 {len(report['openings'])}")
            print(f"  개구부 검출: EV(X마크) {report['openings_found']['EV_xmark']}, "
                  f"PD(S-OPEN) {report['openings_found']['PD_sopen']}, "
                  f"계단 {report['openings_found']['stair_faces']}")
            print(f"  절삭 전 {report['area_before_m2']}㎡ → 후 {report['area_after_m2']}㎡ "
                  f"(절삭 {report['area_cut_m2']}㎡, 정합성: {report['cut_consistency']})")
            oc = report.get("overlap_check", {})
            print(f"  [Phase1] 벽 방식: {report['wall_style']['method']} "
                  f"({report['wall_style']['wall_segments']}세그먼트) / "
                  f"침범검증 {oc.get('panels_checked', 0)}패널 중 "
                  f"위반 {oc.get('violations', '-')}건")
            for o in report["openings"]:
                print(f"    - {o['type']}: 개구부 {o['opening_m2']}㎡ / "
                      f"제거 {o['removed_m2']}㎡ [{o['cut']}]")
        print(f"  리포트: {p}")
        if geo:
            geos[fl] = geo
    if geos:
        out = ROOT / "output" / "slab_precise_101동.json"
        out.write_text(json.dumps(geos, ensure_ascii=False), encoding="utf-8")
        print(f"\n지오메트리 저장: {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
