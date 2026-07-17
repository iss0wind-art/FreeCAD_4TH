"""overlay_prep — 덧그림(습자지) 데이터 생성: 스케치업 층별 태그 보관용.

지시 원문 준수:
  "골조선·보·슬라브 파싱 시 습자지에 그리듯 별도 덧그림 — 휘발성 아님,
   스케치업 도면 태그에 층별 보관. 애매하거나 알 수 없는 곳은 별도 표기,
   모델에도 붉은색 표시. 그래야 어디가 잘못된 건지 파악 가능."

[AUTO] 전 함수 — 파싱 결과·리포트 좌표의 재배열만. 추론 없음.

출력: output/sketchup_overlay_101동.json
  floors.{fl}:
    trace_wall[]   — 벽 골조선 덧그림 (세그먼트)
    trace_beam[]   — 보 덧그림
    trace_slab[]   — 슬라브 경계 덧그림 (폐합 링)
    errors[]       — 붉은표시 대상 {kind, x, y, (x1,y1), note}
      · open_endpoint  벽 폐합 실패(개방 끝점) — Phase -1 실측
      · unpaired_wall  평행쌍 미형성 벽 세그먼트 — Phase -1 실측
      · boundary_open  벽+보 결합 후에도 열린 경계 — Phase -0.5 실측
      · pd_unattached  PD 개구부 자체폐합(슬라브 미교차) 위치
      · infer_zone     [INFER] 판정 구역 (B2F 기초 해석 confidence 0.75)
"""

import json
import sys
from pathlib import Path

import ezdxf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, FLOOR_ANCHOR, SHEETS, collect_floor_data)

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "output" / "reports"
GEO_PATH = ROOT / "output" / "slab_precise_101동.json"
OUT_PATH = ROOT / "output" / "sketchup_overlay_101동.json"

FLOORS = ("B2F", "B1F", "1F", "2F", "TYP", "16F")


def _latest(pattern):
    hits = sorted(REPORT_DIR.glob(pattern))
    return json.loads(hits[-1].read_text(encoding="utf-8")) if hits else None


def _seg_shift(segs, anc):
    ax, ay = anc
    return [[[round(a[0] - ax, 1), round(a[1] - ay, 1)],
             [round(b[0] - ax, 1), round(b[1] - ay, 1)]] for a, b in segs]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    doc = ezdxf.readfile(str(DXF_S30_101))
    geo = json.loads(GEO_PATH.read_text(encoding="utf-8"))
    frame = _latest("phase-1_frame_*.json")
    beam = _latest("phase-0.5_beam_*.json")

    out = {"floors": {}}
    for fl in FLOORS:
        anc = FLOOR_ANCHOR[fl]
        ax, ay = anc
        data = collect_floor_data(doc, fl)
        beam_segs = data.get("beam_segs", [])
        bridge_segs = data.get("bridge_segs", [])
        slab_end_segs = data.get("slab_end_segs", [])
        # 창구간 벽 브리지 = 파싱 추론선 (방부장 검수: 원본선과 색 구분 필수)
        window_bridges = data.get("window_bridges", [])
        g = geo.get(fl, {})
        errors = []

        # 1) 벽 폐합 실패 — 개방 끝점 (Phase -1)
        fr = frame["floors"].get(fl, {}) if frame else {}
        for p in fr.get("closure_fail_coords", []):
            errors.append({"kind": "open_endpoint",
                           "x": round(p[0] - ax, 1), "y": round(p[1] - ay, 1),
                           "note": "벽 폐합 실패(개방 끝점)"})
        # 2) 미페어 벽 세그먼트 (Phase -1)
        for u in fr.get("unpaired_detail", []):
            errors.append({"kind": "unpaired_wall",
                           "x": round((u["p0"][0] + u["p1"][0]) / 2 - ax, 1),
                           "y": round((u["p0"][1] + u["p1"][1]) / 2 - ay, 1),
                           "x1": round(u["p0"][0] - ax, 1),
                           "y1": round(u["p0"][1] - ay, 1),
                           "x2": round(u["p1"][0] - ax, 1),
                           "y2": round(u["p1"][1] - ay, 1),
                           "note": f"평행쌍 미형성 벽 (L={u['length']})"})
        # 3) 벽+보 결합 후 열린 경계 (Phase -0.5)
        br = beam["floors"].get(fl, {}) if beam else {}
        for p in (br.get("precheck") or {}).get("open_coords", []):
            errors.append({"kind": "boundary_open",
                           "x": round(p[0] - ax, 1), "y": round(p[1] - ay, 1),
                           "note": "벽+보 결합에도 열린 경계"})
        # 4) PD 자체폐합(슬라브 미교차) — 확인 표시
        for o in g.get("openings", []):
            if o["type"] == "PD":
                cx = sum(c[0] for c in o["poly"]) / len(o["poly"])
                cy = sum(c[1] for c in o["poly"]) / len(o["poly"])
                errors.append({"kind": "pd_unattached",
                               "x": round(cx - ax, 1), "y": round(cy - ay, 1),
                               "note": "PD 개구부(자체 폐합) 확인 지점"})
        # 5) [INFER] 구역 표기
        if fl == "B2F":
            errors.append({"kind": "infer_zone", "x": -40000, "y": -30000,
                           "note": "[INFER c=0.75] S-B1F-101-BASE 기초 해석 "
                                   "— 기둥좌표 97.5% 상부층 일치로 재검증"})

        out["floors"][fl] = {
            "trace_wall": _seg_shift(data["wall_segs"], anc),
            "trace_beam": _seg_shift(beam_segs, anc),
            "trace_bridge": _seg_shift(bridge_segs, anc),
            "trace_window_bridge": _seg_shift(window_bridges, anc),
            "trace_slab_end": _seg_shift(slab_end_segs, anc),
            "trace_slab": [
                [[round(x - ax, 1), round(y - ay, 1)]
                 for x, y in p["exterior"]]
                for p in g.get("slab_panels", [])],
            "errors": errors,
        }
        f = out["floors"][fl]
        print(f"[{fl}] 덧그림: 벽 {len(f['trace_wall'])} / 보 {len(f['trace_beam'])} / "
              f"연결선 {len(f['trace_bridge'])} / 창브리지 {len(f['trace_window_bridge'])} / "
              f"단부선 {len(f['trace_slab_end'])} / "
              f"슬라브링 {len(f['trace_slab'])} / 오류 {len(errors)}건")

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False),
                        encoding="utf-8")
    print(f"저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
