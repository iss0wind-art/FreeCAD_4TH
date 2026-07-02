"""sketchup_prep — 스케치업 빌드용 정규화 지오메트리 생성.

[AUTO] 순수 좌표 연산 — 시트별 modelspace 좌표를 층 겹침 좌표계로 정규화
(x' = x - 시트 x0, 시트 피치 126000mm 실측 검증). 모델 추론 없음.

출력: output/sketchup_build_101동.json
  { floors: { B2F: {z, storey_h, slab_thk, slab_thk_source,
                    slabs[], wall_faces[], columns[], openings[]} } }
"""

import json
import sys
from pathlib import Path

import ezdxf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, FLOOR_ANCHOR)
from core.pipeline.frame_parser import detect_columns  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
GEO_PATH = ROOT / "output" / "slab_precise_101동.json"
OUT_PATH = ROOT / "output" / "sketchup_build_101동.json"

# 레벨: build_101동.json levels (S30 SL 표기 실측). 기준층 피치 2830.
LEVELS = {"B2F": -9050, "B1F": -5600, "1F": 370, "2F": 3300,
          "3F": 6130, "4F": 8960, "5F": 11790, "6F": 14620, "7F": 17450,
          "8F": 20280, "9F": 23110, "10F": 25940, "11F": 28770,
          "12F": 31600, "13F": 34430, "14F": 37260, "15F": 40090,
          "PH": 43020}
TYP_PITCH = 2830
# 벽 수직 구간 관례 (방부장 교본):
#  - S-하부벽체(파랑) 블록 = 슬라브를 받치는 아래층 벽: SL(N-1)~SL(N)
#  - XR 노란 골조선 = 해당층에 서는 벽: SL(N)~SL(N+1)
WALL_SPAN = {
    "B2F": (None, -9050),      # 기초: 하단 미확정 (발자국만, 붉은플래그)
    "B1F": (-9050, -5600),     # B2F 벽 (하부벽체 블록)
    "1F": (-5600, 370),        # B1F 벽 (하부벽체 블록)
    "2F": (3300, 6130),        # 2F 골조선 벽 — 해당층 기립
    "TYP": None,               # 3F~15F 반복 배치에서 층별 산정
    "16F": (None, 43020),      # 지붕 슬라브 — 벽 데이터 미확정(옥탑 별도)
}
# 기준층 반복 대상: 3F~15F (TYP 지오메트리 재사용)
TYP_FLOORS = ["3F", "4F", "5F", "6F", "7F", "8F", "9F", "10F",
              "11F", "12F", "13F", "14F", "15F"]
# 슬라브 두께: beam_slab_floor_parsed.json 층별 최빈값 (실측 파싱 소스 명기)
SLAB_THK = {
    "B2F": (250, "beam_slab_floor_parsed.json B2F 최빈 250(16/22)"),
    "B1F": (150, "beam_slab_floor_parsed.json B1F 최빈 150(17/18)"),
    "1F": (210, "beam_slab_floor_parsed.json 1F 최빈 210(3/4)"),
    "2F": (210, "build_101동.json slab_types.unit_standard 210"),
    "TYP": (210, "build_101동.json slab_types.unit_standard 210"),
    "16F": (200, "build_101동.json slab_types.roof 200"),
}


# 수직 정합: 층별 EV코어 앵커 기준 (시트원점 방식은 B2F 1000mm 오차 유발했음)
def _shift(coords, anchor):
    ax, ay = anchor
    return [[round(x - ax, 1), round(y - ay, 1)] for x, y in coords]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    geo = json.loads(GEO_PATH.read_text(encoding="utf-8"))
    doc = ezdxf.readfile(str(DXF_S30_101))
    build = {"floors": {}}
    for fl in ("B2F", "B1F", "1F", "2F", "TYP", "16F"):
        g = geo.get(fl)
        if not g or not g.get("slab_panels"):
            continue
        anc = FLOOR_ANCHOR[fl]      # EV코어 앵커 정합 → 층 겹침
        cols = detect_columns(doc, fl) or []
        thk, thk_src = SLAB_THK[fl]
        if fl == "TYP":
            # 기준층: 3F~15F 반복 배치. 골조선 벽 = 해당층 기립(+2830)
            z_sl = None
            wz0, wz1 = None, None
            repeat = [{"floor": tf, "z_sl": LEVELS[tf],
                       "wall_z0": LEVELS[tf], "wall_z1": LEVELS[tf] + TYP_PITCH}
                      for tf in TYP_FLOORS]
        else:
            z_sl = LEVELS.get(fl, LEVELS["PH"] if fl == "16F" else None)
            wz0, wz1 = WALL_SPAN[fl]
            repeat = None
        build["floors"][fl] = {
            "z_sl": z_sl,
            "repeat": repeat,
            "wall_z0": wz0,          # None = 기초(하단 미확정, 발자국만)
            "wall_z1": wz1,
            "wall_note": ("아래층 벽 (구조평면 관례: N층 시트=N-1층 벽)"
                          if wz0 is not None else
                          "기초 발자국 — 깊이 미확정, 붉은 플래그"),
            "slab_thk": thk,
            "slab_thk_source": thk_src,
            "slabs": [{"exterior": _shift(p["exterior"], anc),
                       "holes": [_shift(h, anc) for h in p["holes"]]}
                      for p in g["slab_panels"]],
            "wall_faces": [_shift(w, anc) for w in g.get("wall_faces", [])],
            "columns": [{"cx": round(c["cx"] - anc[0], 1),
                         "cy": round(c["cy"] - anc[1], 1),
                         "w": c["w"], "h": c["h"]} for c in cols],
            "openings": [{"type": o["type"],
                          "poly": _shift(o["poly"], anc)}
                         for o in g.get("openings", [])],
        }
        f = build["floors"][fl]
        ztxt = f['z_sl'] if f['z_sl'] is not None else f"반복{len(f['repeat'] or [])}개층"
        print(f"[{fl}] z={ztxt} 슬라브 {len(f['slabs'])} / "
              f"벽면 {len(f['wall_faces'])} / 기둥 {len(f['columns'])} / "
              f"개구부 {len(f['openings'])}")
    OUT_PATH.write_text(json.dumps(build, ensure_ascii=False),
                        encoding="utf-8")
    print(f"저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
