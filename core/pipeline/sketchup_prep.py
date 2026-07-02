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
from core.pipeline.slab_engine import DXF_S30_101, SHEETS  # noqa: E402
from core.pipeline.frame_parser import detect_columns  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
GEO_PATH = ROOT / "output" / "slab_precise_101동.json"
OUT_PATH = ROOT / "output" / "sketchup_build_101동.json"

# 레벨: build_101동.json levels (S30 SL 표기 실측). 층고 = 다음 레벨 차.
LEVELS = {"B2F": -9050, "B1F": -5600, "1F": 370, "2F": 3300}
STOREY = {"B2F": 3450, "B1F": 5970, "1F": 2930}
# 슬라브 두께: beam_slab_floor_parsed.json 층별 최빈값 (실측 파싱 소스 명기)
SLAB_THK = {
    "B2F": (250, "beam_slab_floor_parsed.json B2F 최빈 250(16/22)"),
    "B1F": (150, "beam_slab_floor_parsed.json B1F 최빈 150(17/18)"),
    "1F": (210, "beam_slab_floor_parsed.json 1F 최빈 210(3/4)"),
}


def _shift(coords, dx):
    return [[round(x - dx, 1), round(y, 1)] for x, y in coords]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    geo = json.loads(GEO_PATH.read_text(encoding="utf-8"))
    doc = ezdxf.readfile(str(DXF_S30_101))
    build = {"floors": {}}
    for fl in ("B2F", "B1F", "1F"):
        g = geo.get(fl)
        if not g or not g.get("slab_panels"):
            continue
        dx = SHEETS[fl][0]          # 시트 원점 보정 → 층 겹침
        cols = detect_columns(doc, fl) or []
        thk, thk_src = SLAB_THK[fl]
        build["floors"][fl] = {
            "z_sl": LEVELS[fl],
            "storey_h": STOREY[fl],
            "slab_thk": thk,
            "slab_thk_source": thk_src,
            "slabs": [{"exterior": _shift(p["exterior"], dx),
                       "holes": [_shift(h, dx) for h in p["holes"]]}
                      for p in g["slab_panels"]],
            "wall_faces": [_shift(w, dx) for w in g.get("wall_faces", [])],
            "columns": [{"cx": round(c["cx"] - dx, 1), "cy": c["cy"],
                         "w": c["w"], "h": c["h"]} for c in cols],
            "openings": [{"type": o["type"],
                          "poly": _shift(o["poly"], dx)}
                         for o in g.get("openings", [])],
        }
        f = build["floors"][fl]
        print(f"[{fl}] z={f['z_sl']} 슬라브 {len(f['slabs'])} / "
              f"벽면 {len(f['wall_faces'])} / 기둥 {len(f['columns'])} / "
              f"개구부 {len(f['openings'])}")
    OUT_PATH.write_text(json.dumps(build, ensure_ascii=False),
                        encoding="utf-8")
    print(f"저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
