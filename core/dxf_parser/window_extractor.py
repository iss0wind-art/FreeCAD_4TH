"""window_extractor — Phase 5: 창호일람표 + 평면 창호기호 파싱 (전 층 공통).

작업지시서 2026-07-02 Phase 5.

⚠ 입면도 부재 보고 (진행규칙 5):
  도면 세트 140매 전수 확인 결과 동별 입면도 시트가 존재하지 않음.
  (입면 관련: A01-034 입면적 산출근거, A30-101 발코니 평·입·단면 뿐)
  → 입면도 기반 좌표 검증은 "미확정", 대체 소스로 아래 2개를 교차 사용:
    1. A50-001~018/021 창호일람표 → 기호별 규격·형식 (원블록+근접텍스트 구조)
    2. A40-003~237 평면도 → 창호 기호 배치 위치 (창호부호 INSERT 460개)

기호 구조 (A50 해독 결과):
  '창호 부호' INSERT 1개 = 원+선 그래픽. 실제 정보는 근접 TEXT:
    거리 ~300  : 번호 ("6")
    거리 ~530  : 타입 문자 ("PW", "PD", "SD", "AG", "FSD", ...)
    거리 ~570  : 규격 "0.40×1.15" (m 단위 W×H)
    거리 ~800+ : 프레임/형태/유리 사양
"""

import json
import math
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import ezdxf

ROOT = Path(__file__).resolve().parents[2]
_DRAW = next((p for p in [ROOT / "input_drawings",
                          Path(r"D:\Git\FreeCAD_4TH\input_drawings")]
              if p.exists()), None)
DXF_SCHED_UNIT = _DRAW / "A50-001~018 단위세대 창호일람표.dxf"
DXF_SCHED_COMMON = _DRAW / "A50-021 아파트 공통 창호일람표.dxf"
DXF_PLAN_A40 = _DRAW / "A40-003~237 101동~108동 평면도.dxf"
REPORT_DIR = ROOT / "output" / "reports"

TYPE_RE = re.compile(r"^(AW|PW|SW|AG|WD|SD|PD|AD|FSD|HD)$")
SIZE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*[×xX]\s*(\d+(?:\.\d+)?)$")
NUM_RE = re.compile(r"^\d{1,3}$")

TYPE_NAME = {
    "PW": "플라스틱창", "AW": "알루미늄창", "SW": "강재창", "AG": "알루미늄그릴",
    "PD": "플라스틱문", "SD": "철재문", "AD": "알루미늄문", "WD": "목재문",
    "FSD": "방화문", "HD": "행거도어",
}


def _texts(msp):
    out = []
    for e in msp:
        if e.dxftype() == "TEXT":
            out.append((e.dxf.text.strip(), e.dxf.insert.x, e.dxf.insert.y))
    return out


def _near(texts, x, y, radius):
    hits = [(t, math.hypot(tx - x, ty - y)) for t, tx, ty in texts
            if math.hypot(tx - x, ty - y) < radius]
    hits.sort(key=lambda r: r[1])
    return hits


# ── 일람표 파싱 ───────────────────────────────────────────────────────────────

# [AUTO] 규칙 연산 — 기호블록+근접텍스트 페어링 (스케일 비례 반경)
def parse_schedule(dxf_path):
    """창호일람표 1매 → {기호: {w_mm, h_mm, type, type_name, spec}}."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    texts = _texts(msp)
    table = {}
    for e in msp:
        if e.dxftype() != "INSERT" or e.dxf.name != "창호 부호":
            continue
        x, y = e.dxf.insert.x, e.dxf.insert.y
        s = abs(e.dxf.xscale) or 1.0   # 블록 스케일 비례 탐색 반경
        near = _near(texts, x, y, 650 * s + 250)
        num = typ = size = None
        spec = []
        for t, d in near:
            if num is None and NUM_RE.match(t) and d < 200 * s + 150:
                num = t
            elif typ is None and TYPE_RE.match(t) and d < 400 * s + 250:
                typ = t
            elif size is None and SIZE_RE.match(t):
                m = SIZE_RE.match(t)
                size = (float(m.group(1)), float(m.group(2)))
            elif d > 700 and len(t) > 3:
                spec.append(t)
        if num and typ:
            sym = f"{typ}{num}"
            if sym not in table:
                table[sym] = {
                    "type": typ,
                    "type_name": TYPE_NAME.get(typ, "?"),
                    "w_mm": round(size[0] * 1000) if size else None,
                    "h_mm": round(size[1] * 1000) if size else None,
                    "spec": spec[:3],
                    "source": Path(dxf_path).name,
                }
    return table


# ── 평면 기호 추출 (101동) ────────────────────────────────────────────────────

def _sheet_titles(msp, dong="101동"):
    """도면타이틀 텍스트 → [(층라벨, x, y)]."""
    titles = []
    for e in msp:
        if e.dxftype() == "TEXT" and e.dxf.layer == "51-도면타이틀":
            t = e.dxf.text.strip()
            if t.startswith(dong) and "평면도" in t:
                fl = t.replace(dong, "").replace("평면도", "").strip()
                titles.append((fl, e.dxf.insert.x, e.dxf.insert.y))
    return titles


# [AUTO] 규칙 연산 — 기호 배치 추출 + 최근접 타이틀 층 판정
def extract_plan_symbols(dong="101동"):
    """A40 평면도에서 dong 창호 기호 배치 추출. 층 = 최근접 도면타이틀."""
    doc = ezdxf.readfile(str(DXF_PLAN_A40))
    msp = doc.modelspace()
    titles = _sheet_titles(msp, dong)
    texts = _texts(msp)
    placements = []
    for e in msp:
        if e.dxftype() != "INSERT" or e.dxf.name != "창호 부호":
            continue
        x, y = e.dxf.insert.x, e.dxf.insert.y
        # 층 판정: 최근접 타이틀 (시트 대각 반경 이내)
        best = min(titles, default=None,
                   key=lambda t: math.hypot(t[1] - x, t[2] - y))
        if best is None or math.hypot(best[1] - x, best[2] - y) > 90000:
            continue
        s = abs(e.dxf.xscale) or 1.0
        near = _near(texts, x, y, 650 * s + 250)
        num = typ = size = None
        for t, d in near:
            if num is None and NUM_RE.match(t) and d < 200 * s + 150:
                num = t
            elif typ is None and TYPE_RE.match(t) and d < 400 * s + 250:
                typ = t
            elif size is None and SIZE_RE.match(t):
                m = SIZE_RE.match(t)
                size = (float(m.group(1)), float(m.group(2)))
        placements.append({
            "floor": best[0],
            "symbol": f"{typ}{num}" if (typ and num) else None,
            "plan_w_mm": round(size[0] * 1000) if size else None,
            "plan_h_mm": round(size[1] * 1000) if size else None,
            "x": round(x, 1), "y": round(y, 1),
        })
    return placements


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    # 1) 일람표 (기호→규격)
    table = parse_schedule(DXF_SCHED_UNIT)
    for sym, rec in parse_schedule(DXF_SCHED_COMMON).items():
        table.setdefault(sym, rec)

    # 2) 평면 기호 배치 (101동 전층)
    placements = extract_plan_symbols("101동")
    by_floor = Counter(p["floor"] for p in placements)

    # 3) 매칭 + 규격 교차검증 (평면 표기 규격 vs 일람표 규격)
    matched, unresolved, size_conflicts = [], [], []
    for p in placements:
        if p["symbol"] and p["symbol"] in table:
            rec = table[p["symbol"]]
            row = {**p, **{k: rec[k] for k in ("w_mm", "h_mm", "type_name")}}
            if (p["plan_w_mm"] and rec["w_mm"]
                    and abs(p["plan_w_mm"] - rec["w_mm"]) > 10):
                row["size_check"] = "불일치"
                size_conflicts.append({
                    "symbol": p["symbol"], "floor": p["floor"],
                    "plan": (p["plan_w_mm"], p["plan_h_mm"]),
                    "schedule": (rec["w_mm"], rec["h_mm"])})
            else:
                row["size_check"] = "일치" if p["plan_w_mm"] else "평면규격없음"
            matched.append(row)
        else:
            unresolved.append(p)

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "elevation_status": "미확정 — 도면 세트(140매)에 동별 입면도 시트 부재. "
                            "입면 관련은 A01-034 입면적 산출근거, "
                            "A30-101 발코니 평·입·단면뿐. "
                            "대체 소스(A50 일람표 + A40 평면 기호)로 수행.",
        "schedule_sheets": [DXF_SCHED_UNIT.name, DXF_SCHED_COMMON.name],
        "schedule_symbols": len(table),
        "schedule_by_type": dict(Counter(v["type"] for v in table.values())),
        "plan_sheet": DXF_PLAN_A40.name,
        "plan_placements": len(placements),
        "plan_by_floor": dict(by_floor),
        "matched": len(matched),
        "unresolved": len(unresolved),
        "size_conflicts": size_conflicts,
        "unresolved_list": unresolved[:50],
        "symbol_table": table,
        "matched_detail": matched,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"phase5_windows_{ts}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print("=== Phase 5 창호 파싱 (101동) ===")
    print(f"  [입면도] {report['elevation_status']}")
    print(f"  일람표 기호: {len(table)}개 — 타입별 {report['schedule_by_type']}")
    print(f"  평면 배치 기호: {len(placements)}개 (층별 {dict(by_floor)})")
    print(f"  일람표 매칭 성공: {len(matched)} / {len(placements)}")
    print(f"  규격 교차검증 불일치: {len(size_conflicts)}건")
    for c in size_conflicts[:5]:
        print(f"    ! [{c['floor']}] {c['symbol']} 평면{c['plan']} ↔ "
              f"일람표{c['schedule']}")
    print(f"  미확정: {len(unresolved)}건")
    for u in unresolved[:8]:
        print(f"    - [{u['floor']}] {u['symbol']} @({u['x']},{u['y']})")
    print(f"  리포트: {out}")
    return report


if __name__ == "__main__":
    main()
