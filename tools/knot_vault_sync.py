#!/usr/bin/env python3
"""
knot-vault 동기화 도구
역할: output/build_XXX동.json → .knot-vault/wiki/buildings/XXX동.md
실행: python tools/knot_vault_sync.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
WIKI_DIR = ROOT / ".knot-vault" / "wiki" / "buildings"


def load_build(dong: str) -> dict | None:
    path = OUTPUT_DIR / f"build_{dong}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def render_dong_md(data: dict) -> str:
    dong = data["dong"]
    levels = data.get("levels", {})
    beams = data.get("beams", [])
    columns = data.get("columns", [])
    walls = data.get("walls", [])
    slabs = data.get("slabs", [])
    slab_types = data.get("slab_types", {})
    level_changes = data.get("level_changes", [])
    pit_openings = data.get("pit_openings", 0)
    grid = data.get("grid", {})
    elapsed = data.get("elapsed_sec", 0)
    errors = data.get("errors", [])

    trust = "[빨간 원] 재파싱 필요" if errors else ("검토 필요" if len(beams) > 6000 else "OK")

    lines = [
        f"# {dong} — BOQ 파싱 결과",
        "",
        f"> 신뢰도: {trust} | 파싱 시간: {elapsed:.0f}s",
        "",
        "## 층고 (FL-SL)",
        "",
        "| 층 | SL (mm) |",
        "|:--|:--|",
    ]

    for fl, sl in sorted(levels.items()):
        lines.append(f"| {fl} | {sl:+,} |")

    lines += [
        "",
        "## 구조 부재 수량",
        "",
        "| 부재 | 수량 |",
        "|:--|:--|",
        f"| 보 (Beam) | {len(beams):,} |",
        f"| 기둥 (Column) | {len(columns):,} | ← [빨간 원] 기둥리스트 별도 파싱 필요 |",
        f"| 벽 (Wall) | {len(walls):,} |",
        f"| 슬라브 외곽 (Slab outline) | {len(slabs):,} |",
        f"| 층단차 변경 | {len(level_changes)} |",
        f"| PIT 개구부 | {pit_openings} |",
        "",
        "## 슬라브 두께",
        "",
    ]

    if slab_types:
        lines += ["| 종류 | 두께 (mm) |", "|:--|:--|"]
        for k, v in sorted(slab_types.items()):
            lines.append(f"| {k} | {v} |")
    else:
        lines.append("_(데이터 없음)_")

    if grid:
        x_coords = grid.get("x_coords", [])
        y_coords = grid.get("y_coords", [])
        rot = grid.get("rotation_deg", 0)
        lines += [
            "",
            "## 구조 격자",
            "",
            f"- X 격자선: {len(x_coords)}개",
            f"- Y 격자선: {len(y_coords)}개",
            f"- 회전각: {rot:.2f}도",
        ]

    if errors:
        lines += ["", "## 에러", ""]
        for e in errors:
            lines.append(f"- [빨간 원] `{e}`")

    lines += ["", "---", f"_[[건물 목록|돌아가기]] | 현재: {dong}_"]

    return "\n".join(lines)


def sync_all(dongs=None):
    WIKI_DIR.mkdir(parents=True, exist_ok=True)

    if dongs is None:
        dongs = [f"{i}동" for i in range(101, 117)]

    results = {}
    for dong in dongs:
        data = load_build(dong)
        if data is None:
            print(f"  SKIP {dong}: output JSON 없음")
            results[dong] = "skip"
            continue

        md = render_dong_md(data)
        out_path = WIKI_DIR / f"{dong}.md"
        out_path.write_text(md, encoding="utf-8")
        errors = data.get("errors", [])
        tag = "[ERROR]" if errors else "[OK]"
        print(f"  {tag} {dong}: beams={len(data.get('beams', []))} walls={len(data.get('walls', []))} -> {out_path.name}")
        results[dong] = "ok" if not errors else "error"

    _update_readme(results, dongs)
    return results


def _update_readme(results, dongs):
    readme = WIKI_DIR / "README.md"
    lines = [
        "# 아파트 동별 BOQ 파싱 결과",
        "",
        "| 동 | 신뢰도 | 보 | 기둥 | 벽 |",
        "|:--|:--|:--|:--|:--|",
    ]

    for dong in sorted(dongs):
        data = load_build(dong)
        if data is None:
            lines.append(f"| [[{dong}]] | 파일없음 | - | - | - |")
            continue
        errors = data.get("errors", [])
        beams = len(data.get("beams", []))
        cols = len(data.get("columns", []))
        walls = len(data.get("walls", []))
        trust = "[빨간 원]" if errors else ("검토" if beams > 6000 else "OK")
        lines.append(f"| [[{dong}]] | {trust} | {beams:,} | {cols:,} | {walls:,} |")

    readme.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n  README 업데이트: {readme}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    dongs = sys.argv[1:] if len(sys.argv) > 1 else None
    print("knot-vault 동기화 시작...")
    results = sync_all(dongs)
    ok = sum(1 for v in results.values() if v == "ok")
    err = sum(1 for v in results.values() if v == "error")
    skip = sum(1 for v in results.values() if v == "skip")
    print(f"\n완료: OK={ok} 에러={err} 스킵={skip}")
