# -*- coding: utf-8 -*-
"""window_z_from_elevation — 창 z0/z1을 입면 실측 정본으로 재계산.

방부장 확정(2026-07-09, windows_elevation_101.json 입면 실측):
  전 창 HEAD = 2420 균일 (기준층 바닥 기준). 이전 규칙(상부슬라브-410,
  1200x450은 -1160 → head 1670)은 상부침범/불일치로 폐기.
  sill(폭 클래스별, A40 동입면도 A-WALL-ELE 실측):
    AG(950~1100)      → 210
    1220급(1100~1400) → 150
    PW(1500~3400)     → 400
  문(is_door)은 기존 값 유지 (바닥+200 규칙, 커밋 2fc895e 방부장 승인).

[AUTO] 순수 규칙 연산 — 위치·문 데이터는 기존 window_build_TYP.json 그대로,
z0/z1만 치환. 분류 불가 폭은 미확정 플래그 후 sill 400 안전값.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "output" / "window_build_TYP.json"

HEAD = 2420.0
SILL_CLASSES = [
    (950, 1100, 210.0, "AG"),
    (1100, 1400, 150.0, "1220급"),
    (1500, 3400, 400.0, "PW"),
]


def classify(width):
    for lo, hi, sill, name in SILL_CLASSES:
        if lo <= width < hi:
            return sill, name
    return None, None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    d = json.loads(PATH.read_text(encoding="utf-8"))
    stats = {"door_kept": 0, "window_set": 0, "unclassified": 0}
    for w in d["windows"]:
        if w.get("is_door"):
            stats["door_kept"] += 1
            continue
        width = math.hypot(w["x2"] - w["x1"], w["y2"] - w["y1"])
        sill, cls = classify(width)
        if sill is None:
            stats["unclassified"] += 1
            w["z0"], w["z1"] = 400.0, HEAD
            w["z_source"] = f"미확정(폭 {round(width)} 분류불가) — 안전값 sill 400"
            continue
        w["z0"], w["z1"] = sill, HEAD
        w["z_source"] = f"입면실측 {cls}: sill {sill:.0f} / head {HEAD:.0f}"
        stats["window_set"] += 1
    PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"창 {stats['window_set']}개 z 재설정 (HEAD {HEAD:.0f} 균일) / "
          f"문 {stats['door_kept']}개 유지 / 미분류 {stats['unclassified']}개")
    print(f"저장: {PATH}")


if __name__ == "__main__":
    main()
