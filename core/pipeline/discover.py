"""discover — 도면 자동탐지: 어떤 구조평면 DXF가 와도 config 자동 생성.

101동 하드코딩(SHEETS/FLOOR_BLOCKS)을 일반화하는 자동탐지기.
  1. 도면타이틀 레이어(51-도면타이틀/BORD-TEXT)에서 "…층 구조평면도" 텍스트
     → 시트 X구역 자동 산정 (타이틀 간격의 중앙 분할)
  2. 시트별 INSERT 블록명 패턴 매칭:
     WALL/COL/BASE → 벽·기둥, GIRDER → 거더, BEAM → 보
  3. 결과를 output/pipeline_config_{동}.json 으로 저장
     → slab_engine 등이 이 config를 읽으면 타 동·타 현장 도면에 재사용 가능

전 함수 [AUTO] — 텍스트/기하 규칙 연산. 모델 추론 없음.
블록명이 패턴과 전혀 다른 도면에서만 [INFER] (사람/모델 확인) 필요 —
그 경우 unmatched_blocks 목록을 config에 남긴다.
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import ezdxf

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "output"

TITLE_LAYERS = ("51-도면타이틀", "BORD-TEXT")
TITLE_RE = re.compile(r"(?P<dong>\d{3}동)?\s*(?P<floor>[^\s]+)\s*구조평면도")

# 층 라벨 정규화: 지하2층→B2F, 지상1층→1F, 기준층→TYP, 지상16층→16F …
def _norm_floor(label):
    label = label.strip()
    m = re.match(r"지하(\d+)층", label)
    if m:
        return f"B{m.group(1)}F"
    m = re.match(r"지상(\d+)층", label)
    if m:
        return f"{m.group(1)}F"
    if "기준" in label:
        return "TYP"
    if "옥탑" in label or "옥상" in label:
        return "ROOF"
    if "PILE" in label.upper() or "기초" in label:
        return "PILE"
    return label


# [AUTO] 텍스트 규칙 — 시트 타이틀 수집
def find_sheet_titles(msp, dong=None):
    titles = []
    for e in msp:
        if e.dxftype() != "TEXT" or e.dxf.layer not in TITLE_LAYERS:
            continue
        t = e.dxf.text.strip()
        m = TITLE_RE.search(t)
        if not m:
            continue
        if dong and m.group("dong") and m.group("dong") != dong:
            continue
        fl = _norm_floor(m.group("floor"))
        titles.append({"floor": fl, "x": e.dxf.insert.x, "y": e.dxf.insert.y,
                       "raw": t})
    return titles


# [AUTO] 기하 규칙 — 타이틀 X좌표로 시트 구역 분할
def zones_from_titles(titles):
    """같은 Y대역 타이틀들의 X를 정렬해 중앙 분할선으로 구역 생성."""
    if not titles:
        return {}
    # 주요 Y대역(타이틀 최빈 y ±3000) 필터
    ys = sorted(t["y"] for t in titles)
    y_med = ys[len(ys) // 2]
    band = [t for t in titles if abs(t["y"] - y_med) < 3000]
    seen = {}
    for t in sorted(band, key=lambda r: r["x"]):
        seen.setdefault(t["floor"], t["x"])
    floors = sorted(seen.items(), key=lambda kv: kv[1])
    zones = {}
    for i, (fl, x) in enumerate(floors):
        left = (floors[i - 1][1] + x) / 2 if i > 0 else x - 63000
        right = (x + floors[i + 1][1]) / 2 if i < len(floors) - 1 else x + 63000
        zones[fl] = (round(left), round(right))
    return zones


# [AUTO] 텍스트 규칙 — 시트별 구조 블록 자동 분류
BLOCK_PATTERNS = [
    (re.compile(r"WALL|COL|BASE", re.I), "wall"),
    (re.compile(r"GIRDER", re.I), "girder"),
    (re.compile(r"BEAM", re.I), "beam"),
]


def classify_blocks(msp, zones):
    floor_blocks = defaultdict(lambda: {"wall": None, "girder": None,
                                        "beam": None})
    unmatched = []
    for ins in msp.query("INSERT"):
        name = ins.dxf.name
        if not name.upper().startswith("S-"):
            continue
        x = ins.dxf.insert.x
        floor = next((fl for fl, (x0, x1) in zones.items() if x0 < x < x1),
                     None)
        if floor is None:
            continue
        kind = next((k for pat, k in BLOCK_PATTERNS if pat.search(name)), None)
        if kind is None:
            unmatched.append({"block": name, "floor": floor,
                              "note": "[INFER 필요] 패턴 불일치 — 사람/모델 확인"})
            continue
        if floor_blocks[floor][kind] is None:
            floor_blocks[floor][kind] = name
    return dict(floor_blocks), unmatched


def discover(dxf_path, dong=None):
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    titles = find_sheet_titles(msp, dong)
    zones = zones_from_titles(titles)
    blocks, unmatched = classify_blocks(msp, zones)
    config = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "source_dxf": Path(dxf_path).name,
        "dong": dong,
        "sheets": {fl: list(z) for fl, z in zones.items()},
        "floor_blocks": blocks,
        "unmatched_blocks": unmatched,
    }
    return config


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    dxf = argv[0] if argv else str(
        Path(r"D:\Git\FreeCAD_4TH\input_drawings") /
        "S30-001~010-101동 구조평면도.dxf")
    dong = argv[1] if len(argv) > 1 else "101동"
    cfg = discover(dxf, dong)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"pipeline_config_{dong or 'auto'}.json"
    out.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"=== 도면 자동탐지: {Path(dxf).name} ===")
    print(f"  시트 구역: {cfg['sheets']}")
    for fl, b in cfg["floor_blocks"].items():
        print(f"  [{fl}] wall={b['wall']} girder={b['girder']} beam={b['beam']}")
    if cfg["unmatched_blocks"]:
        print(f"  [INFER 필요] 미분류 블록 {len(cfg['unmatched_blocks'])}건:")
        for u in cfg["unmatched_blocks"]:
            print(f"    - {u['block']} @{u['floor']}")
    print(f"  config: {out}")
    return cfg


if __name__ == "__main__":
    main(sys.argv[1:])
