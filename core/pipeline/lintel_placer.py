"""lintel_placer — Phase 6: 인방보/역보 배치 확정 (Phase 4+5 결합).

작업지시서 2026-07-02 Phase 6:
  Phase 4(보일람표)의 LB1/RB 데이터와 Phase 5(창호기호)의 개구부 위치를
  결합하여 인방보·역보 배치 목록을 생성한다.

배치 규칙 (추정값 0 준수):
  - 인방보: 확정 개구부(일람표 매칭 성공) 상단에 LB1 배치.
    길이 = 개구부 폭 (좌우 걸침(bearing)은 일람표에 수치 없음 → 미확정 기록)
    단면 = LB1 250×565 (깊이는 '개구부 상단~슬라브 하단' 변동 — 표기값 기록)
  - 역보(RB): 평면이 치수 직접표기 방식이라 RB 위치 마크가 평면에 없음
    → 위치 확정 불가, 31개 마크 전량 미확정 보고 (임의 배치 금지)
  - 좌표계: 개구부 좌표는 A40 평면도 modelspace 기준.
    S30 구조평면 좌표계와의 정합은 Phase 7 교차검증 항목.
"""

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "output" / "reports"

# 인방보가 필요한 개구부 타입 (창/문 — RC벽 관통)
LINTEL_TYPES = {"PW", "AW", "SW", "PD", "SD", "AD", "WD", "FSD", "HD", "AG"}


def _latest(pattern):
    hits = sorted(REPORT_DIR.glob(pattern))
    return hits[-1] if hits else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p4 = _latest("phase4_beam_schedule_*.json")
    p5 = _latest("phase5_windows_*.json")
    if not (p4 and p5):
        print("선행 리포트 없음 — Phase 4/5 먼저 실행")
        return None
    r4 = json.loads(p4.read_text(encoding="utf-8"))
    r5 = json.loads(p5.read_text(encoding="utf-8"))

    lb1 = r4["schedule_table"].get("LB1")
    rb_marks = r4["rb_inverted_beams"]

    lintels, skipped = [], []
    for w in r5["matched_detail"]:
        typ = "".join(c for c in (w["symbol"] or "") if c.isalpha())
        if typ not in LINTEL_TYPES:
            skipped.append(w)
            continue
        width = w.get("plan_w_mm") or w.get("w_mm")
        lintels.append({
            "floor": w["floor"],
            "opening_symbol": w["symbol"],
            "x": w["x"], "y": w["y"],
            "coord_system": "A40 평면도 modelspace",
            "length_mm": width,
            "bearing": "미확정 — 일람표에 걸침 수치 없음",
            "section": {
                "mark": "LB1",
                "width_mm": lb1["width"] if lb1 else None,
                "height_note": lb1["height_note"] if lb1 else None,
            },
            "size_check": w.get("size_check"),
        })

    unresolved_openings = r5["unresolved_list"]
    by_floor = Counter(l["floor"] for l in lintels)

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "inputs": {"phase4": p4.name, "phase5": p5.name},
        "lintels_placed": len(lintels),
        "lintels_by_floor": dict(by_floor),
        "inverted_beams_placed": 0,
        "inverted_beams_status": (
            f"미확정 {len(rb_marks)}건 전량 — 평면 치수 직접표기 방식으로 "
            f"RB 위치 마크 부재. 임의 배치 금지(추정값0). 마크: {rb_marks}"),
        "openings_before": len(r5["matched_detail"]) + len(unresolved_openings),
        "openings_resolved_by_lintel": len(lintels),
        "openings_unresolved": len(unresolved_openings) + len(skipped),
        "unresolved_detail": {
            "기호_미해독": unresolved_openings,
            "인방보_불필요_타입": [
                {k: s[k] for k in ("floor", "symbol", "x", "y")}
                for s in skipped],
        },
        "size_conflicts_carried": r5.get("size_conflicts", []),
        "lintel_list": lintels,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"phase6_lintel_{ts}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print("=== Phase 6 인방보/역보 배치 ===")
    print(f"  인방보 배치: {len(lintels)}개 (층별 {dict(by_floor)})")
    print(f"  역보 배치: 0개 — {report['inverted_beams_status'][:60]}...")
    print(f"  개구부 총 {report['openings_before']} → "
          f"인방보 해결 {len(lintels)} / "
          f"미해결 {report['openings_unresolved']}")
    print(f"  규격 불일치 이월: {len(report['size_conflicts_carried'])}건 "
          f"(Phase 7 교차검증 대상)")
    print(f"  리포트: {out}")
    return report


if __name__ == "__main__":
    main()
