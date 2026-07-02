"""slab_regression — Phase 9: 회귀 테스트셋.

작업지시서 2026-07-02 Phase 9:
  Phase 0~8 수정 작업 간 상호 회귀를 방지한다.
  기준값(BASELINE)은 2026-07-02 최초 통과 세션의 실측치 —
  output/reports/phase{0,4,5,6,8}_*.json 에서 고정.

실행:
  python tests/regression/slab_regression.py
  → 각 엔진 재실행 후 기준값 대비 증감 출력, 허용오차 초과 시 FAIL.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
REPORT_DIR = ROOT / "output" / "reports"
HISTORY = Path(__file__).parent / "accuracy_history.json"

# ── 기준값: 2026-07-02 세션 최초 통과 수치 (리포트 영구 저장본과 동일) ──────────
# 4차 개정 2026-07-02: 전소스 X마크(EV·샤프트) + 계단클러스터 명시 절삭
# — 'EV 슬라브 깔림/계단 누락' 수정. EV: B2F 2(피트 상부덮개 실존), B1F 4, 1F 3
BASELINE = {
    "phase0": {
        "B2F": {"slab_panels": 63, "area_after_m2": 1149.57,
                "ev_xmark": 2, "violations": 0},
        "B1F": {"slab_panels": 108, "area_after_m2": 1470.9,
                "ev_xmark": 4, "violations": 0},
        "1F": {"slab_panels": 131, "area_after_m2": 1448.25,
               "ev_xmark": 3, "violations": 0},
    },
    "phase4": {"schedule_marks": 222, "matched": 1544, "plan_total": 1586},
    "phase5": {"schedule_symbols": 38, "matched": 133, "placements": 145},
    "phase6": {"lintels": 133},
    # 기둥 수치 2026-07-02 2차 수정: 도곽 클리핑 추가 후 821→43
    # (스케치업 육안 검증에서 도곽 밖 주차장 잔재 발견 → detect_columns 수정)
    "phase8": {"columns_B1F": 41, "columns_1F": 43,
               "stair_riser_typ": "157.22x9", "stair_tread": "270.0x8"},
}
AREA_TOL_M2 = 1.0      # 슬라브 면적 허용오차
COUNT_TOL = 0          # 개수는 오차 불허


def run_all():
    """엔진 3종 재실행 → 현재값 수집."""
    import ezdxf
    from core.pipeline import slab_engine
    from core.pipeline import beam_schedule_matcher
    from core.dxf_parser import window_extractor

    cur = {"phase0": {}}
    doc = ezdxf.readfile(str(slab_engine.DXF_S30_101))
    for fl in ("B2F", "B1F", "1F"):
        r, _ = slab_engine.run_floor(fl, doc)
        cur["phase0"][fl] = {
            "slab_panels": r["slab_panels"],
            "area_after_m2": r["area_after_m2"],
            "ev_xmark": r["openings_found"]["EV_xmark"],
            "violations": r["overlap_check"]["violations"],
        }
    r4 = beam_schedule_matcher.main()
    cur["phase4"] = {"schedule_marks": r4["schedule_marks"],
                     "matched": r4["matched"],
                     "plan_total": r4["plan_labels_total"]}
    r5 = window_extractor.main()
    cur["phase5"] = {"schedule_symbols": r5["schedule_symbols"],
                     "matched": r5["matched"],
                     "placements": r5["plan_placements"]}
    return cur


def compare(cur):
    failures, checks = [], 0

    def chk(path, base, now, tol=COUNT_TOL):
        nonlocal checks
        checks += 1
        ok = abs(now - base) <= tol
        if not ok:
            failures.append(f"{path}: 기준 {base} → 현재 {now}")
        return ok

    for fl, b in BASELINE["phase0"].items():
        c = cur["phase0"][fl]
        chk(f"phase0.{fl}.slab_panels", b["slab_panels"], c["slab_panels"])
        chk(f"phase0.{fl}.area_after_m2", b["area_after_m2"],
            c["area_after_m2"], AREA_TOL_M2)
        chk(f"phase0.{fl}.ev_xmark", b["ev_xmark"], c["ev_xmark"])
        chk(f"phase0.{fl}.violations", b["violations"], c["violations"])
    for k in ("schedule_marks", "matched", "plan_total"):
        chk(f"phase4.{k}", BASELINE["phase4"][k], cur["phase4"][k])
    for k in ("schedule_symbols", "matched", "placements"):
        chk(f"phase5.{k}", BASELINE["phase5"][k], cur["phase5"][k])
    return checks, failures


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=== Phase 9 회귀 테스트 ===")
    cur = run_all()
    checks, failures = compare(cur)
    passed = checks - len(failures)
    accuracy = round(passed / checks * 100, 1)

    # 세션별 정확도 추이 기록
    hist = json.loads(HISTORY.read_text(encoding="utf-8")) \
        if HISTORY.exists() else []
    hist.append({"ts": datetime.now().isoformat(timespec="seconds"),
                 "checks": checks, "passed": passed, "accuracy": accuracy,
                 "failures": failures})
    HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=2),
                       encoding="utf-8")

    prev = hist[-2]["accuracy"] if len(hist) >= 2 else None
    print(f"\n  검사 {checks}건 — 통과 {passed} / 실패 {len(failures)}")
    print(f"  정확도: {accuracy}%"
          + (f" (이전 {prev}% 대비 {accuracy - prev:+.1f}%p)" if prev else ""))
    for f in failures:
        print(f"    FAIL {f}")
    print(f"  추이 기록: {HISTORY}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
