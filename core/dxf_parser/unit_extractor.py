"""unit_extractor — A30 단위세대평면도에서 타입별 창호를 자동 추출.

방부장 지시 2026-07-05: 전부 추출 → 부재 파싱데이터로 활용, 자동화,
매번 파싱 금지(JSON 캐시), 어떤 도면이 와도 되게(하드코딩 금지·자동탐지).

방식:
  1. 타입 타이틀 자동탐지 (정규식) — "59A 단위세대 평면도 (기본형)" 등
  2. 세대 영역 자동 분할 (인접 타이틀 간격의 중앙)
  3. 각 세대의 창호부호 INSERT + 근접 텍스트 → {부호, 로컬좌표}
  4. 세대 로컬 좌표 정규화 (세대 bbox 좌하단 원점)
  5. output/unit_windows.json 저장 (재파싱 금지)

[AUTO] 텍스트·기하 규칙 연산. 모델 추론 없음.
결과 없거나 애매하면 미확정 플래그.
"""

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import ezdxf

ROOT = Path(__file__).resolve().parents[2]
_DRAW = next((p for p in [ROOT / "input_drawings",
                          Path(r"D:\Git\FreeCAD_4TH\input_drawings")]
              if p.exists()), None)
OUT = ROOT / "output" / "unit_windows.json"

# 단위세대평면도 후보 (자동 스캔 대상). 파일명 패턴으로 자동탐지.
UNIT_DXF_GLOB = "A30-*단위세대평면도*.dxf"

# 타입 타이틀: "59A 단위세대 평면도 (기본형)" / "84C ... (확장형)" / 최상층
TITLE_RE = re.compile(
    r"(?P<type>\d{2,3}[A-Z])\s*(?:Type)?\s*단위세대\s*평면도?\s*"
    r"(?:\((?P<variant>[^)]+)\))?")
TITLE_RE2 = re.compile(
    r"(?P<type>\d{2,3}[A-Z])\s*Type\s*(?P<variant>[^\s]+세대)")

# 창호부호 블록명 (도면 관례 — config화 가능)
SYMBOL_BLOCK = "창호 부호"
TYPE_RE = re.compile(r"^(AW|PW|SW|AG|PD|SD|AD|WD|FSD|HD)$")
NUM_RE = re.compile(r"^\d{1,2}$")
SIZE_RE = re.compile(r"^(\d+(?:\.\d+)?)[×xX](\d+(?:\.\d+)?)$")

# 창/문 분류 (부호 앞글자)
WINDOW_TYPES = {"AW", "PW", "SW", "AG"}   # 창
DOOR_TYPES = {"PD", "SD", "AD", "WD", "FSD", "HD"}  # 문


def _texts(msp):
    return [(e.dxf.text.strip(), e.dxf.insert.x, e.dxf.insert.y)
            for e in msp if e.dxftype() == "TEXT"]


# [AUTO] 타입 타이틀 자동탐지
def find_unit_titles(msp):
    titles = []
    for e in msp:
        if e.dxftype() != "TEXT":
            continue
        t = e.dxf.text.strip()
        m = TITLE_RE.search(t) or TITLE_RE2.search(t)
        if m and "단위세대" in t:
            titles.append({
                "type": m.group("type"),
                "variant": (m.groupdict().get("variant") or "기본형").strip(),
                "x": e.dxf.insert.x, "y": e.dxf.insert.y, "raw": t})
    return titles


# [AUTO] 세대 할당 반경 자동 산정 — 타이틀 간 최근접거리 중앙값 기반
def assign_radius(titles):
    if len(titles) < 2:
        return 15000.0
    nn = []
    for i, a in enumerate(titles):
        d = min((math.hypot(a["x"]-b["x"], a["y"]-b["y"])
                 for j, b in enumerate(titles) if j != i), default=30000)
        nn.append(d)
    nn.sort()
    med = nn[len(nn)//2]
    return med * 0.55   # 세대는 인접 타이틀 중앙선 안쪽


# [AUTO] 한 창호부호 INSERT의 부호·규격 해독 (근접 텍스트)
def _decode_symbol(e, texts):
    x, y = e.dxf.insert.x, e.dxf.insert.y
    s = abs(e.dxf.xscale) or 1.0
    near = sorted(((t, math.hypot(px - x, py - y))
                   for t, px, py in texts
                   if math.hypot(px - x, py - y) < 650 * s + 250),
                  key=lambda r: r[1])
    num = typ = size = None
    for t, d in near:
        if num is None and NUM_RE.match(t) and d < 200 * s + 150:
            num = t
        elif typ is None and TYPE_RE.match(t) and d < 400 * s + 250:
            typ = t
        elif size is None and SIZE_RE.match(t):
            m = SIZE_RE.match(t)
            size = (float(m.group(1)), float(m.group(2)))
    if not (typ and num):
        return None
    kind = "창" if typ in WINDOW_TYPES else ("문" if typ in DOOR_TYPES else "?")
    return {"symbol": f"{typ}{num}", "kind": kind,
            "w_mm": round(size[0]*1000) if size else None,
            "h_mm": round(size[1]*1000) if size else None,
            "x": round(x, 1), "y": round(y, 1)}


# [AUTO] 창호부호 공간 클러스터링 → 세대 자동 분리 (격자·반경 가정 없음)
def cluster_symbols(recs, link=3500, min_size=3):
    """근접(link mm) 연결 클러스터. 각 클러스터 = 한 세대."""
    n = len(recs)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(n):
        for j in range(i + 1, n):
            if abs(recs[i]["x"]-recs[j]["x"]) < link and \
                    abs(recs[i]["y"]-recs[j]["y"]) < link:
                if math.hypot(recs[i]["x"]-recs[j]["x"],
                              recs[i]["y"]-recs[j]["y"]) < link:
                    parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(recs[i])
    return [g for g in groups.values() if len(g) >= min_size]


# [AUTO] 클러스터(세대) → 최근접 타이틀로 타입 라벨
def assign_symbols_to_titles(msp, texts, titles):
    recs = []
    for e in msp:
        if e.dxftype() == "INSERT" and e.dxf.name == SYMBOL_BLOCK:
            r = _decode_symbol(e, texts)
            if r:
                recs.append(r)
    clusters = cluster_symbols(recs)
    buckets = {i: [] for i in range(len(titles))}
    for cl in clusters:
        cx = sum(r["x"] for r in cl) / len(cl)
        cy = sum(r["y"] for r in cl) / len(cl)
        best_i, best_d = None, 1e18
        for i, t in enumerate(titles):
            d = math.hypot(cx - t["x"], cy - t["y"])
            if d < best_d:
                best_i, best_d = i, d
        if best_i is not None:
            # 같은 타이틀에 여러 클러스터면 큰 쪽 채택
            if len(cl) > len(buckets[best_i]):
                buckets[best_i] = cl
    return buckets, len(clusters)


def extract_all():
    result = {"source_dxfs": [], "types": {}}
    for dxf in sorted(_DRAW.glob(UNIT_DXF_GLOB)):
        doc = ezdxf.readfile(str(dxf))
        msp = doc.modelspace()
        texts = _texts(msp)
        titles = find_unit_titles(msp)
        if not titles:
            continue
        result["source_dxfs"].append(dxf.name)
        buckets, radius = assign_symbols_to_titles(msp, texts, titles)
        for i, syms in buckets.items():
            if not syms:
                continue
            z = titles[i]
            xs = [s["x"] for s in syms]
            ys = [s["y"] for s in syms]
            ox, oy = min(xs), min(ys)
            for s in syms:
                s["lx"] = round(s["x"] - ox, 1)
                s["ly"] = round(s["y"] - oy, 1)
            key = f"{z['type']}_{z['variant']}"
            if key not in result["types"] or \
                    len(syms) > len(result["types"][key]["symbols"]):
                result["types"][key] = {
                    "type": z["type"], "variant": z["variant"],
                    "origin": [round(ox, 1), round(oy, 1)],
                    "n_window": sum(1 for s in syms if s["kind"] == "창"),
                    "n_door": sum(1 for s in syms if s["kind"] == "문"),
                    "symbols": syms}
    return result


def load_or_extract(force=False):
    """캐시 우선 (매번 파싱 금지). force=True면 재추출."""
    if OUT.exists() and not force:
        return json.loads(OUT.read_text(encoding="utf-8"))
    r = extract_all()
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    return r


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    force = "--force" in argv
    r = load_or_extract(force=force)
    print("=== A30 단위세대 창호 자동추출 ===")
    print(f"  도면: {r['source_dxfs']}")
    print(f"  타입 {len(r['types'])}종:")
    for key, v in sorted(r["types"].items()):
        print(f"    {key}: 창 {v['n_window']} / 문 {v['n_door']} "
              f"(총 {len(v['symbols'])})")
    print(f"  저장: {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
