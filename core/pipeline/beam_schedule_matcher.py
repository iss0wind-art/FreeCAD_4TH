"""beam_schedule_matcher — Phase 4: 보일람표 파싱 + 평면 마크 매칭.

작업지시서 2026-07-02 Phase 4:
  평면도 단독으로 구분 불가한 인방보/역보/테두리보를 일람표 텍스트로 식별하고
  101동 구조평면(S30) 거더/보 블록의 마크 텍스트와 매칭한다.

소스:
  - S30-561 주동 인방보 및 테두리보 리스트.dxf → EB/LB/SB 마크·단면
  - S30-521~525 101~116동 저층부 보 리스트.dxf → 일반보 마크·단면 (역보 RB 포함)
  - S30-001~010-101동 구조평면도.dxf → 평면 배치 마크 (S-Defpoints 텍스트)

원칙: 매칭 실패는 "미확정" 목록으로 보고 (추정값 0).
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
DXF_LINTEL = _DRAW / "S30-561 주동 인방보 및 테두리보 리스트.dxf"
DXF_LOWBEAM = _DRAW / "S30-521~525 101~116동 저층부 보 리스트.dxf"
DXF_TRANSFER = _DRAW / "S30-531~551 주동 전이보 리스트.dxf"
DXF_PARKING = _DRAW / "S40-151~156 지하주차장 보 리스트_260202 이오스 수정.dxf"
DXF_PLAN101 = _DRAW / "S30-001~010-101동 구조평면도.dxf"
REPORT_DIR = ROOT / "output" / "reports"

# 보 마크 패턴: (층프리픽스)(타입)(번호)(서픽스) 예: 1AG10A, -1AWG1, RB50, EB1
MARK_RE = re.compile(r"^-?\d{0,2}(AWG|AG|TG|RB|EB|LB|SB|WG|G|B)\d{1,3}[A-D]?$")

BEAM_TYPE = {
    "LB": "인방보", "EB": "테두리보", "SB": "새시보(추정 금지—일람표 원문 확인)",
    "RB": "역보", "TG": "전이보", "AWG": "벽식거더", "AG": "거더",
    "WG": "벽거더", "G": "거더", "B": "보",
}


def _mark_type(mark):
    m = re.match(r"^-?\d{0,2}(AWG|AG|TG|RB|EB|LB|SB|WG|G|B)", mark)
    return m.group(1) if m else None


# ── 일람표 파싱 ───────────────────────────────────────────────────────────────

# [AUTO] 텍스트 규칙 연산 — 정규식 마크 + DIMENSION 매칭
def parse_lintel_schedule():
    """S30-561: 부호 행(EB1/LB1/SB1) + 열별 DIMENSION → 마크 사전."""
    doc = ezdxf.readfile(str(DXF_LINTEL))
    msp = doc.modelspace()
    marks, dims, notes = {}, [], []
    for e in msp:
        if e.dxftype() == "TEXT":
            t = e.dxf.text.strip()
            x = e.dxf.insert.x
            if MARK_RE.match(t):
                marks[t] = {"x": x, "w": None, "h": None}
            elif "변경" in t or "->" in t:
                notes.append(t)
        elif e.dxftype() == "DIMENSION":
            try:
                dims.append((e.get_measurement(), e.dxf.defpoint.x,
                             e.dxf.defpoint.y))
            except Exception:
                pass
    # 열 매칭: 마크 x와 가장 가까운 치수. y>7500 = 폭(상단), 이하 = 깊이
    for mk, rec in marks.items():
        best_w = best_h = None
        for val, dx, dy in dims:
            if abs(dx - rec["x"]) < 3000:
                if dy > 7500:
                    best_w = val
                else:
                    best_h = val
        rec["w"], rec["h"] = best_w, best_h
    out = {}
    for mk, rec in marks.items():
        out[mk] = {
            "type": BEAM_TYPE.get(_mark_type(mk), "?"),
            "width": rec["w"],
            "height": rec["h"],
            "height_note": "일람표 표기값 — 실깊이는 개구부 상단~슬라브 하단 (변동)",
            "source": DXF_LINTEL.name,
        }
    return out, notes


_SIZE_TXT = re.compile(r"^(\d{3,4})\s*[xX×]\s*(\d{3,4})$")


# [AUTO] 텍스트 규칙 연산 — 마크·치수 TEXT 근접 페어링
def parse_text_schedule(dxf_path):
    """마크 TEXT ↔ 최근접 치수 TEXT(500X600) 페어링 일람표 파서.

    저층부/전이보/주차장 리스트 공통 — DIMENSION 없이 치수를 TEXT로 표기.
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    marks, sizes = [], []
    for e in msp:
        if e.dxftype() != "TEXT":
            continue
        t = e.dxf.text.strip()
        pos = (e.dxf.insert.x, e.dxf.insert.y)
        if MARK_RE.match(t):
            marks.append((t, pos))
        else:
            m = _SIZE_TXT.match(t)
            if m:
                sizes.append((int(m.group(1)), int(m.group(2)), pos))
    out = {}
    for mk, (mx, my) in marks:
        rec = out.setdefault(mk, {
            "type": BEAM_TYPE.get(_mark_type(mk), "?"),
            "width": None, "height": None,
            "source": Path(dxf_path).name,
        })
        if rec["width"] is not None:
            continue
        best = min(sizes, default=None,
                   key=lambda s: math.hypot(s[2][0] - mx, s[2][1] - my))
        if best and math.hypot(best[2][0] - mx, best[2][1] - my) < 5000:
            rec["width"], rec["height"] = best[0], best[1]
    return out


# ── 평면 마크 추출 ────────────────────────────────────────────────────────────

PLAN_SHEETS = {
    "B1F": ((155000, 281000), ["S-B1F GIRDER", "S-B2F-BEAM"]),
    "1F": ((281000, 407000), ["S-1F-GIRDER-1007", "S-1F BEAM-1007"]),
}


SIZE_RE = re.compile(r"^(\d{3,4})[xX](\d{3,4})$")
# 복합 표기: "rwg1-500x900/rawg1-500x600" → 마크-치수 쌍 여러 개
COMPO_RE = re.compile(r"([a-zA-Z]{1,4}\d{1,3}[a-dA-D]?)-(\d{3,4})[xX](\d{3,4})")


# [AUTO] 텍스트 규칙 연산 — 정규식 라벨 추출
def extract_plan_labels():
    """101동 구조평면 거더/보 블록의 라벨 추출.

    이 도면은 마크 대신 치수 직접표기(500X900) 방식 — 규격 기반 매칭으로 전환.
    복합 표기(rwg1-500x900)에서만 마크 추출 가능.
    """
    doc = ezdxf.readfile(str(DXF_PLAN101))
    msp = doc.modelspace()
    plan = {fl: {"sizes": [], "marks": []} for fl in PLAN_SHEETS}
    for ins in msp.query("INSERT"):
        for fl, ((x0, x1), blocks) in PLAN_SHEETS.items():
            if ins.dxf.name in blocks and x0 < ins.dxf.insert.x < x1:
                for ve in ins.virtual_entities():
                    if ve.dxftype() != "TEXT":
                        continue
                    t = ve.dxf.text.strip()
                    pos = (round(ve.dxf.insert.x, 1), round(ve.dxf.insert.y, 1))
                    m = SIZE_RE.match(t)
                    if m:
                        plan[fl]["sizes"].append({
                            "w": int(m.group(1)), "h": int(m.group(2)),
                            "x": pos[0], "y": pos[1]})
                        continue
                    for mk, w, h in COMPO_RE.findall(t):
                        plan[fl]["marks"].append({
                            "mark": mk.upper(), "w": int(w), "h": int(h),
                            "x": pos[0], "y": pos[1]})
    return plan


# ── 매칭 ─────────────────────────────────────────────────────────────────────

# [AUTO] 규칙 연산 — 규격 키 매칭, 모델 추론 없음
def match_by_size(plan, schedule):
    """규격(W×H) 기반 매칭: 평면 치수 라벨 ↔ 일람표 단면.

    반환: (매칭 목록, 미확정 목록, 규격별 집계)
    """
    sched_sizes = {}
    for mk, rec in schedule.items():
        if rec["width"] and rec["height"]:
            sched_sizes.setdefault(
                (int(rec["width"]), int(rec["height"])), []).append(mk)
    matched, unmatched = [], []
    size_cnt = Counter()
    for fl, d in plan.items():
        for s in d["sizes"]:
            key = (s["w"], s["h"])
            size_cnt[(fl,) + key] += 1
            if key in sched_sizes:
                matched.append({**s, "floor": fl,
                                "schedule_marks": sched_sizes[key]})
            else:
                unmatched.append({**s, "floor": fl})
        for mrec in d["marks"]:
            mk = mrec["mark"]
            hit = schedule.get(mk) or schedule.get(mk.lstrip("-"))
            (matched if hit else unmatched).append(
                {**mrec, "floor": fl,
                 **({"schedule_marks": [mk]} if hit else {})})
    return matched, unmatched, size_cnt


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    lintel, notes = parse_lintel_schedule()
    schedule = {}
    for p in (DXF_LOWBEAM, DXF_TRANSFER, DXF_PARKING):
        if p.exists():
            for mk, rec in parse_text_schedule(p).items():
                schedule.setdefault(mk, rec)
    schedule.update(lintel)

    plan = extract_plan_labels()
    matched, unmatched, size_cnt = match_by_size(plan, schedule)

    n_plan = sum(len(d["sizes"]) + len(d["marks"]) for d in plan.values())
    rb_marks = [mk for mk in schedule if _mark_type(mk) == "RB"]

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "schedule_sheets": [DXF_LINTEL.name, DXF_LOWBEAM.name,
                            DXF_TRANSFER.name, DXF_PARKING.name],
        "plan_label_convention": "치수 직접표기(500X900) — 마크 미표기, 규격 매칭 적용",
        "schedule_marks": len(schedule),
        "schedule_by_type": dict(Counter(v["type"] for v in schedule.values())),
        "revision_notes": notes,
        "rb_inverted_beams": rb_marks,
        "plan_labels_total": n_plan,
        "plan_by_floor": {
            fl: {"sizes": len(d["sizes"]), "marks": len(d["marks"])}
            for fl, d in plan.items()},
        "matched": len(matched),
        "unmatched": len(unmatched),
        "unmatched_list": unmatched[:50],
        "schedule_table": schedule,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"phase4_beam_schedule_{ts}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print("=== Phase 4 보일람표 매칭 ===")
    print(f"  일람표 시트: {len(report['schedule_sheets'])}개 "
          f"{report['schedule_sheets']}")
    print(f"  일람표 마크: {len(schedule)}개 — 타입별 "
          f"{report['schedule_by_type']}")
    print(f"  개정 주기: {notes}")
    print(f"  역보(RB) 마크: {rb_marks if rb_marks else '0건'}")
    print(f"  평면 표기방식: {report['plan_label_convention']}")
    print(f"  평면 라벨: {n_plan}개 (층별 {report['plan_by_floor']})")
    print(f"  매칭 성공 {len(matched)} / 전체 {n_plan}")
    print(f"  미확정(일람표에 없는 규격): {len(unmatched)}건")
    miss_sizes = Counter((u.get('w'), u.get('h')) for u in unmatched)
    for (w, h), c in miss_sizes.most_common(10):
        print(f"    - {w}x{h}: {c}건")
    print(f"  리포트: {out}")
    return report


if __name__ == "__main__":
    main()
