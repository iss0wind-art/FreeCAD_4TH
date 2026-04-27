"""
BOQ 1163 부재 스펙 임포터 — Phase 1 Track B

입력:  D:\\Git\\BOQ_2\\boq_member_specs.json  (1163 레코드)
출력:  output/boq.db  member_specs 테이블
실행:  python scripts/import_boq_specs.py [--path <json_path>] [--dry-run]

매핑 (HANDOFF_TO_ICHEON.md Track B 기준):
  보         → BEAM
  기둥       → COLUMN
  슬라브/슬래브 → SLAB
  벽체/옹벽  → WALL
  기초/파일/매트기초 → FOUNDATION
  기타       → 스킵 + 로그
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import api.database as db

# ─────────────────────────────────────────────────────────────
DEFAULT_JSON = Path("D:/Git/BOQ_2/boq_member_specs.json")

_TYPE_MAP: dict[str, str] = {
    "보": "BEAM",
    "기둥": "COLUMN",
    "슬라브": "SLAB",
    "슬래브": "SLAB",
    "벽체": "WALL",
    "옹벽": "WALL",
    "기초": "FOUNDATION",
    "파일": "FOUNDATION",
    "매트기초": "FOUNDATION",
}

_EDGE_BEAM_KEYWORDS = ("테두리", "edge", "Edge")


def _detect_subtype(symbol: str, remark: str) -> str | None:
    combined = (symbol + " " + remark).lower()
    if any(k.lower() in combined for k in _EDGE_BEAM_KEYWORDS):
        return "edge_beam"
    return None


def run_import(json_path: Path, dry_run: bool = False) -> dict:
    if not json_path.exists():
        raise FileNotFoundError(f"BOQ specs JSON 없음: {json_path}")

    with open(json_path, encoding="utf-8") as f:
        records: list[dict] = json.load(f)

    total = len(records)
    imported = skipped = errors = 0
    skip_log: list[str] = []
    error_log: list[str] = []

    if not dry_run:
        db.init_db()

    for rec in records:
        symbol: str = rec.get("symbol", "").strip()
        member_kr: str = rec.get("member", "").strip()
        member_type = _TYPE_MAP.get(member_kr)

        if not member_type:
            skip_log.append(f"SKIP symbol={symbol!r} member={member_kr!r}")
            skipped += 1
            continue

        remark = str(rec.get("remark") or "")
        subtype = _detect_subtype(symbol, remark)

        spec = {
            "symbol": symbol,
            "project_scope": "global",
            "member_type": member_type,
            "subtype": subtype,
            "width": float(rec.get("width") or 0),
            "height": float(rec.get("height") or 0),
            "depth": float(rec.get("depth") or 0),
            "thickness": float(rec.get("thickness") or 0),
            "length": float(rec.get("length") or 0),
            "wall_thickness": float(rec.get("wallThk") or 0),
            "remark": remark or None,
            "source": "BOQ_IMPORT",
        }

        if dry_run:
            imported += 1
            continue

        try:
            db.upsert_member_spec(spec)
            imported += 1
        except Exception as exc:
            error_log.append(f"ERROR symbol={symbol!r}: {exc}")
            errors += 1

    result = {
        "total": total,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "error_rate": errors / total if total else 0,
    }

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}임포트 결과:")
    print(f"  전체: {total} / 임포트: {imported} / 스킵: {skipped} / 오류: {errors}")
    print(f"  오류율: {result['error_rate']:.1%}")

    if skip_log:
        print(f"\n--- 스킵 목록 (상위 10건) ---")
        for line in skip_log[:10]:
            print(" ", line)

    if error_log:
        print(f"\n--- 오류 목록 ---")
        for line in error_log:
            print(" ", line)

    if result["error_rate"] > 0.05:
        print(f"\n⚠️  WARN: 오류율 {result['error_rate']:.1%} > 5% 허용 기준")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BOQ 부재 스펙 임포터")
    parser.add_argument("--path", type=Path, default=DEFAULT_JSON,
                        help="boq_member_specs.json 경로")
    parser.add_argument("--dry-run", action="store_true",
                        help="DB 쓰기 없이 검증만 실행")
    args = parser.parse_args()

    result = run_import(args.path, dry_run=args.dry_run)
    sys.exit(0 if result["error_rate"] <= 0.05 else 1)
