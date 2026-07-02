"""cross_validator — Phase 7: 소스 간 교차검증 리포트 자동 생성.

작업지시서 2026-07-02 Phase 7:
  평면도-일람표-구조평면 간 판정 불일치를 좌표와 함께 자동 리스트업.
  불일치는 임의 해소하지 않고 "미확정"으로 사람 확인 대상에 올린다.

수집 소스 (각 Phase 최신 리포트):
  phase0_*  — S30 구조평면 슬라브/개구부 (층별)
  phase4_*  — 보일람표 vs 평면 규격 매칭
  phase5_*  — 창호일람표 vs A40 평면 기호
  phase6_*  — 인방보/역보 배치
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "output" / "reports"


def _latest(pattern):
    hits = sorted(REPORT_DIR.glob(pattern))
    return hits[-1] if hits else None


def _load(pattern):
    p = _latest(pattern)
    return (json.loads(p.read_text(encoding="utf-8")), p.name) if p else (None, None)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    items = []          # 불일치/미확정 통합 목록
    checked = 0         # 검증 대상 총수

    # ── 1. Phase 0: 층별 슬라브 데이터 상태 (S30 자체 완결성)
    for fl in ("B2F", "B1F", "1F", "2F", "TYP", "16F"):
        r, _ = _load(f"phase0_{fl}_*.json")
        if not r:
            continue
        checked += 1
        if r["status"] != "OK":
            items.append({
                "category": "슬라브 데이터",
                "floor": fl, "coord": None,
                "sources": {"S30 구조평면": "세대부 없음",
                            "필요 소스": "S20 단위세대구조평면도"},
                "verdict": "미확정",
                "detail": r["status"],
            })
        if r.get("cut_consistency") == "불일치":
            items.append({
                "category": "절삭 정합성",
                "floor": fl, "coord": None,
                "sources": {"절삭전후차": r.get("area_cut_m2"),
                            "개구부합계": None},
                "verdict": "불일치",
                "detail": "절삭 면적과 개구부 합계 불일치",
            })

    # ── 2. Phase 4: 평면 보 규격 vs 보일람표
    r4, n4 = _load("phase4_beam_schedule_*.json")
    if r4:
        checked += r4["plan_labels_total"]
        for u in r4["unmatched_list"]:
            items.append({
                "category": "보 규격",
                "floor": u.get("floor"),
                "coord": (u.get("x"), u.get("y")),
                "sources": {"평면 표기": f"{u.get('w')}x{u.get('h')}",
                            "보일람표": "해당 규격 없음"},
                "verdict": "미확정",
                "detail": "일람표 4매에 없는 단면 규격",
            })

    # ── 3. Phase 5: 창호 평면 기호 vs 창호일람표
    r5, n5 = _load("phase5_windows_*.json")
    if r5:
        checked += r5["plan_placements"]
        for c in r5.get("size_conflicts", []):
            items.append({
                "category": "창호 규격",
                "floor": c["floor"], "coord": None,
                "sources": {"A40 평면 표기": f"{c['plan']}",
                            "A50 창호일람표": f"{c['schedule']}"},
                "verdict": "불일치",
                "detail": f"{c['symbol']} 규격 상이 — 사람 확인 필요",
            })
        for u in r5.get("unresolved_list", []):
            items.append({
                "category": "창호 기호",
                "floor": u.get("floor"),
                "coord": (u.get("x"), u.get("y")),
                "sources": {"A40 평면": u.get("symbol") or "기호 해독 실패",
                            "A50 일람표": "매칭 없음"},
                "verdict": "미확정",
                "detail": "일람표 미수록 기호 또는 텍스트 미해독",
            })
        items.append({
            "category": "입면도",
            "floor": "전층", "coord": None,
            "sources": {"도면 세트": "동별 입면도 0매"},
            "verdict": "미확정",
            "detail": r5["elevation_status"],
        })

    # ── 4. Phase 6: 역보 위치 + 좌표계 정합
    r6, n6 = _load("phase6_lintel_*.json")
    if r6:
        checked += r6["lintels_placed"]
        items.append({
            "category": "역보 배치",
            "floor": "전층", "coord": None,
            "sources": {"보일람표": "RB 31마크",
                        "S30 평면": "위치 마크 없음(치수 직접표기)"},
            "verdict": "미확정",
            "detail": r6["inverted_beams_status"][:120],
        })
        items.append({
            "category": "좌표계 정합",
            "floor": "전층", "coord": None,
            "sources": {"A40 평면도": "창호/인방보 좌표계",
                        "S30 구조평면": "슬라브/벽 좌표계"},
            "verdict": "미확정",
            "detail": "두 도면 modelspace 원점 상이 — EV코어 앵커 정합 필요 "
                      "(core/dxf_parser/ev_detector.py 재사용 가능)",
        })

    agree = checked - len(items)
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "inputs": [n for n in (n4, n5, n6) if n],
        "total_checked": checked,
        "agree": agree,
        "flagged": len(items),
        "by_category": {},
        "items": items,
    }
    from collections import Counter
    report["by_category"] = dict(Counter(i["category"] for i in items))

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"phase7_crosscheck_{ts}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print("=== Phase 7 교차검증 리포트 ===")
    print(f"  검증 대상: {checked}건")
    print(f"  일치: {agree}건 / 불일치·미확정: {len(items)}건")
    print(f"  범주별: {report['by_category']}")
    print("  주요 항목:")
    for i in items[:12]:
        loc = f" @{i['coord']}" if i.get("coord") else ""
        print(f"    [{i['verdict']}] {i['category']} ({i['floor']}){loc} — "
              f"{i['detail'][:60]}")
    print(f"  리포트: {out}")
    return report


if __name__ == "__main__":
    main()
