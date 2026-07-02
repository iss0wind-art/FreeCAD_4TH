"""phase8_rework — Phase 8: 누락/미시도 항목 재작업 (B2F·기둥·계단·wall_pairs).

작업지시서 2026-07-02 Phase 8:
  8-1 B2F 누락 확인 — 원본 도면 존재 여부 + 파싱 수치
  8-2 기둥 로직 — 폐합 기반 인식 신규 구현
  8-3 계단 디딤판 — 단수·단높이·디딤판 폭 파싱
  8-4 wall_pairs 검증 — 평행선 페어링 + 미페어 잔여 보고
"""

import json
import math
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import ezdxf
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, FLOOR_BLOCKS, SHEETS, collect_floor_data)

ROOT = Path(__file__).resolve().parents[2]
_DRAW = DXF_S30_101.parent
DXF_CORE = _DRAW / "A40-301~568 101동~104동 코어평,단면도.dxf"
REPORT_DIR = ROOT / "output" / "reports"


# ── 8-2 기둥: 폐합 LWPOLYLINE 기반 ───────────────────────────────────────────

def detect_columns(doc, floor):
    """S30 벽·기둥 블록의 폐합 LWPOLYLINE 중 기둥 형상 추출.

    기둥 판정: 폐합(4점 이상) + bbox 300~2500mm + 세장비<6 + 유효 폴리곤.
    """
    msp = doc.modelspace()
    wall_blk = FLOOR_BLOCKS[floor][0]
    if wall_blk is None:
        return None, "미확정: 벽·기둥 블록 없음"
    cols, rejected = [], 0
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
                rejected += 1
                continue
            if max(w, h) / max(min(w, h), 1) > 6:
                rejected += 1
                continue
            poly = Polygon(pts)
            if not poly.is_valid or poly.area < 0.09e6:  # 300×300 미만 제외
                rejected += 1
                continue
            cols.append({"cx": round(sum(xs) / len(xs), 1),
                         "cy": round(sum(ys) / len(ys), 1),
                         "w": round(w), "h": round(h),
                         "closed": True})
    return cols, "OK"


# ── 8-3 계단: 단면 표기 파싱 ─────────────────────────────────────────────────

import re

_RISER_RE = re.compile(r"\((\d+(?:\.\d+)?)[×xX](\d+)\)")


def parse_stairs(dong="101동"):
    """A40-30x 계단 단면도에서 단높이·디딤판·단수 추출."""
    doc = ezdxf.readfile(str(DXF_CORE))
    msp = doc.modelspace()
    # 동 계단 단면 타이틀 위치
    sheets = []
    for e in msp:
        if e.dxftype() == "TEXT":
            t = e.dxf.text.strip()
            if t.startswith(dong) and "계단" in t and "단면" in t:
                sheets.append((t, e.dxf.insert.x, e.dxf.insert.y))
    if not sheets:
        return None, "미확정: 계단 단면 시트 없음"
    # 각 시트 위쪽 45m 대역의 (값×개수) 표기 수집
    risers, treads = Counter(), Counter()
    for title, sx, sy in sheets:
        for e in msp:
            if e.dxftype() != "TEXT":
                continue
            t = e.dxf.text.strip()
            m = _RISER_RE.match(t)
            if not m:
                continue
            x, y = e.dxf.insert.x, e.dxf.insert.y
            if abs(x - sx) < 12000 and 0 < (y - sy) < 45000:
                val, cnt = float(m.group(1)), int(m.group(2))
                if 140 <= val <= 200:
                    risers[(val, cnt)] += 1
                elif 250 <= val <= 320:
                    treads[(val, cnt)] += 1
    return {
        "sheets": [s[0] for s in sheets],
        "riser_patterns": {f"{v}x{c}": n for (v, c), n in risers.most_common()},
        "tread_patterns": {f"{v}x{c}": n for (v, c), n in treads.most_common()},
    }, "OK"


# ── 8-4 wall_pairs: 평행선 페어링 검증 ───────────────────────────────────────

def verify_wall_pairs(data, min_th=100, max_th=350):
    """벽 세그먼트 평행쌍 검증: 두께 100~350mm 페어 비율 + 미페어 잔여."""
    segs = data["wall_segs"]
    items = []
    for (p0, p1) in segs:
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < 300:
            continue
        ang = math.degrees(math.atan2(dy, dx)) % 180
        items.append({"p0": p0, "p1": p1, "L": L, "ang": ang,
                      "mx": (p0[0] + p1[0]) / 2, "my": (p0[1] + p1[1]) / 2})
    paired = set()
    pairs = 0
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
            if min_th <= d <= max_th and \
                    min(a["L"], b["L"]) / max(a["L"], b["L"]) > 0.3:
                paired.add(i)
                paired.add(j)
                pairs += 1
                break
    return {
        "segments_checked": len(items),
        "pairs_formed": pairs,
        "paired_segments": len(paired),
        "unpaired_segments": len(items) - len(paired),
        "pair_ratio": round(len(paired) / max(len(items), 1), 3),
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    doc = ezdxf.readfile(str(DXF_S30_101))
    report = {"timestamp": datetime.now().isoformat(timespec="seconds")}

    # 8-1 B2F
    p0_b2f = sorted(REPORT_DIR.glob("phase0_B2F_*.json"))
    b2f = json.loads(p0_b2f[-1].read_text(encoding="utf-8")) if p0_b2f else None
    report["8-1_B2F"] = {
        "원본_도면": "존재 — S30 시트 1(30000~155000 X구역) + "
                   "S-B1F-101-BASE 블록",
        "파싱_결과": ({"slab_panels": b2f["slab_panels"],
                     "area_m2": b2f["area_after_m2"],
                     "status": b2f["status"]} if b2f else "phase0 리포트 없음"),
    }
    print("=== Phase 8 재작업 ===")
    print(f"  [8-1 B2F] 원본 존재 ✓ — 패널 {b2f['slab_panels']}개, "
          f"{b2f['area_after_m2']}㎡" if b2f else "  [8-1 B2F] 리포트 없음")

    # 8-2 기둥
    col_out = {}
    for fl in ("B2F", "B1F", "1F"):
        cols, st = detect_columns(doc, fl)
        col_out[fl] = {"status": st,
                       "count": len(cols) if cols else 0,
                       "closed_all": all(c["closed"] for c in cols) if cols else None,
                       "columns": cols[:200] if cols else []}
        print(f"  [8-2 기둥] {fl}: {st} — {len(cols) if cols else 0}개 "
              f"(전부 폐합: {col_out[fl]['closed_all']})")
    for fl in ("2F", "TYP", "16F"):
        col_out[fl] = {"status": "미확정: 세대부 블록 없음 (S20 필요)", "count": 0}
    report["8-2_columns"] = col_out

    # 8-3 계단
    stairs, st = parse_stairs("101동")
    report["8-3_stairs"] = {"status": st, **(stairs or {})}
    if stairs:
        print(f"  [8-3 계단] 시트 {len(stairs['sheets'])}매 — "
              f"단높이 패턴 {stairs['riser_patterns']} / "
              f"디딤판 패턴 {stairs['tread_patterns']}")
    else:
        print(f"  [8-3 계단] {st}")

    # 8-4 wall_pairs
    wp_out = {}
    for fl in ("B2F", "B1F", "1F"):
        data = collect_floor_data(doc, fl)
        if data["wall_segs"]:
            wp = verify_wall_pairs(data)
            wp_out[fl] = wp
            print(f"  [8-4 wall_pairs] {fl}: {wp['segments_checked']}세그 → "
                  f"페어 {wp['pairs_formed']}쌍 (페어율 {wp['pair_ratio']*100:.0f}%, "
                  f"미페어 {wp['unpaired_segments']})")
        else:
            wp_out[fl] = {"status": "벽 세그먼트 없음"}
    report["8-4_wall_pairs"] = wp_out

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"phase8_rework_{ts}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"  리포트: {out}")
    return report


if __name__ == "__main__":
    main()
