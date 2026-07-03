"""self_check — 자가진단기: 파싱 부족·문제점을 파이썬이 스스로 검출.

방부장 지시 2026-07-03: "너가 스스로 부족하거나 문제인 점을 알아내어야 한다."
[AUTO] 전 검사 — 도면·리포트 실측 대조. 추론 없음.

검사 항목:
  1. 코어 수 대조 — 계단클러스터 vs A40 코어 시트 수(3)
  2. 개구 경계 품질 — face(내벽) vs bbox폴백 비율
  3. 슬라브 커버리지 — 외곽 폐합선(도면 실측) 대비 파싱 면적
  4. 창 오픈 적용률 — 창구간 브리지 수 vs 공제 수
  5. 슬라브 단차(SL±) 적용 — 도면 단차 텍스트 수 vs 적용 수
  6. 층변화(옥상·옥탑) — 소스 시트 수 vs 파싱 수
"""

import json
import re
import sys
from pathlib import Path

import ezdxf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, SHEETS, SHEET_Y)

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "output" / "reports"

CORE_COUNT_FROM_A40 = 3   # A40-301 실측: 코아#1/#2/#3


def _latest(pattern):
    hits = sorted(REPORT_DIR.glob(pattern))
    return json.loads(hits[-1].read_text(encoding="utf-8")) if hits else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    doc = ezdxf.readfile(str(DXF_S30_101))
    msp = doc.modelspace()
    issues = []
    ok = []

    # 1+2. 층별 리포트 검사
    for fl in SHEETS:
        r = _latest(f"phase0_{fl}_*.json")
        if not r or "openings_found" in r and r.get("precondition") == "FAIL":
            continue
        of = r.get("openings_found", {})
        if of.get("stair_clusters", 0) != CORE_COUNT_FROM_A40:
            issues.append(f"[{fl}] 계단클러스터 {of.get('stair_clusters')} ≠ "
                          f"코어 {CORE_COUNT_FROM_A40} (A40 실측)")
        else:
            ok.append(f"[{fl}] 계단 3개소 = 코어 수 일치")
        ob = r.get("opening_boundary", {})
        fb = ob.get("bbox_폴백", 0)
        if fb:
            issues.append(f"[{fl}] 개구 bbox폴백 {fb}건 — 샤프트 벽 미폐합, "
                          f"내벽 face 승격 필요")

    # 3. 슬라브 커버리지 — B2F 외곽 폐합선 실측 대비
    for e in msp:
        if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "00_SLAB END + ETC" \
                and e.closed:
            pts = [(p[0], p[1]) for p in e.get_points()]
            xs = [p[0] for p in pts]
            if SHEETS["B2F"][0] < sum(xs)/len(xs) < SHEETS["B2F"][1]:
                from shapely.geometry import Polygon
                outline = Polygon(pts).area / 1e6
                if outline < 500:      # 동 외곽 규모만 (소형 폐합 제외)
                    continue
                r = _latest("phase0_B2F_*.json")
                parsed = r["area_before_m2"] if r else 0
                gap = outline - parsed
                if abs(gap) > 30:
                    issues.append(f"[B2F] 외곽 폐합선 {outline:.1f}㎡ vs "
                                  f"파싱 {parsed:.1f}㎡ — 갭 {gap:+.1f}㎡")
                else:
                    ok.append(f"[B2F] 외곽 대비 커버리지 갭 {gap:+.1f}㎡ (1% 내)")

    # 4. 창 오픈 적용률 (build json의 window_openings vs 브리지)
    build_p = ROOT / "output" / "sketchup_build_101동.json"
    if build_p.exists():
        b = json.loads(build_p.read_text(encoding="utf-8"))
        for fl, f in b["floors"].items():
            nb = f.get("window_bridge_count", None)
            nw = len(f.get("window_openings", []))
            if nb is None:
                continue
            if nw == 0 and nb > 0:
                issues.append(f"[{fl}] 창구간 {nb}곳 검출됐으나 공제 0 — 미적용")
            elif nb:
                ok.append(f"[{fl}] 창 공제 {nw}/{nb}")

    # 5. 슬라브 단차 텍스트 (SL+/-) — 적용 여부
    sl_pat = re.compile(r"SL\s*[+\-±]\s*\d")
    n_sl = 0
    for e in msp:
        if e.dxftype() == "TEXT" and sl_pat.search(e.dxf.text):
            x, y = e.dxf.insert.x, e.dxf.insert.y
            if SHEET_Y[0] < y < SHEET_Y[1] and any(
                    x0 < x < x1 for x0, x1 in SHEETS.values()):
                n_sl += 1
    if n_sl:
        issues.append(f"[전층] 슬라브 단차 텍스트 {n_sl}건 검출 — 적용 0건 "
                      f"(step_zone 모듈 미연결)")

    # 6. 층변화·옥탑 — 옥상 시트 존재 vs 파싱
    roof_sheets = 0
    for e in msp:
        if e.dxftype() == "TEXT" and "101동" in e.dxf.text \
                and ("옥상" in e.dxf.text or "옥탑" in e.dxf.text) \
                and "구조평면도" in e.dxf.text:
            roof_sheets += 1
    if roof_sheets:
        issues.append(f"[옥탑] 옥상·옥탑 구조평면 {roof_sheets}시트 존재 — "
                      f"파싱 0 (층변화 15/16층 미적용)")

    # 7. 지하 XR 소스 — 지하 XR 도면의 벽(A-WALL) 세그가 벽 소스에 포함되는지
    #    (지하 부족 지적 — XR지하N층평면도는 건축 XR, 구조 벽 소스로 미사용 중)
    xr_base = sum(1 for i in msp.query("INSERT")
                  if i.dxf.name.startswith("XR지하"))
    if xr_base:
        issues.append(f"[지하] XR지하 도면 INSERT {xr_base}개 존재 — "
                      f"벽 소스로 미활용 (지하 정밀도 부족 원인 후보)")

    report = {"issues": issues, "ok": ok}
    out = REPORT_DIR / "self_check_latest.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("=== 자가진단 (self_check) ===")
    print(f"  통과 {len(ok)} / 문제 {len(issues)}")
    for i in issues:
        print(f"  ✗ {i}")
    for o in ok[:6]:
        print(f"  ✓ {o}")
    print(f"  리포트: {out}")
    return report


if __name__ == "__main__":
    main()
