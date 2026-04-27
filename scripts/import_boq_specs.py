"""
BOQ 1163 부재 스펙 임포터 — Phase 1 Track B

입력:  BOQ_SPECS_JSON 환경변수 또는 기본 경로
출력:  output/boq.db  member_specs 테이블
실행:  python scripts/import_boq_specs.py [--path <json_path>] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import api.database as db

_DEFAULT_JSON_PATH = Path(
    os.getenv("BOQ_SPECS_JSON", "D:/Git/BOQ_2/boq_member_specs.json")
)

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

_EDGE_BEAM_KEYWORDS = ("테두리", "edge")


def _detect_subtype(symbol: str, remark: str) -> str | None:
    combined = (symbol + " " + remark).lower()
    if any(k in combined for k in _EDGE_BEAM_KEYWORDS):
        return "edge_beam"
    return None


def _build_spec(rec: dict) -> dict | None:
    symbol: str = rec.get("symbol", "").strip()
    if not symbol:
        return None
    member_kr: str = rec.get("member", "").strip()
    member_type = _TYPE_MAP.get(member_kr)
    if not member_type:
        return None
    remark = str(rec.get("remark") or "")
    return {
        "symbol": symbol,
        "project_scope": "global",
        "member_type": member_type,
        "subtype": _detect_subtype(symbol, remark),
        "width": float(rec.get("width") or 0),
        "height": float(rec.get("height") or 0),
        "depth": float(rec.get("depth") or 0),
        "thickness": float(rec.get("thickness") or 0),
        "length": float(rec.get("length") or 0),
        "wall_thickness": float(rec.get("wallThk") or 0),
        "remark": remark or None,
        "source": "BOQ_IMPORT",
    }


def _process_records(
    records: list[dict], dry_run: bool
) -> tuple[int, int, int, list[str], list[str]]:
    imported = skipped = errors = 0
    skip_log: list[str] = []
    error_log: list[str] = []

    for rec in records:
        spec = _build_spec(rec)
        if spec is None:
            symbol = rec.get("symbol", "")
            member_kr = rec.get("member", "")
            skip_log.append(f"SKIP symbol={symbol!r} member={member_kr!r}")
            skipped += 1
            continue

        if dry_run:
            imported += 1
            continue

        try:
            db.upsert_member_spec(spec)
            imported += 1
        except Exception as exc:
            error_log.append(f"ERROR symbol={spec['symbol']!r}: {exc}")
            errors += 1

    return imported, skipped, errors, skip_log, error_log


def _print_summary(
    total: int, imported: int, skipped: int, errors: int,
    skip_log: list[str], error_log: list[str], dry_run: bool,
) -> None:
    prefix = "[DRY-RUN] " if dry_run else ""
    print(f"\n{prefix}임포트 결과:")
    print(f"  전체: {total} / 임포트: {imported} / 스킵: {skipped} / 오류: {errors}")
    print(f"  오류율: {errors / total:.1%}" if total else "  오류율: N/A")
    if skip_log:
        print("\n--- 스킵 목록 (상위 10건) ---")
        for line in skip_log[:10]:
            print(" ", line)
    if error_log:
        print("\n--- 오류 목록 ---")
        for line in error_log:
            print(" ", line)
    if total and errors / total > 0.05:
        print(f"\n⚠️  WARN: 오류율 {errors / total:.1%} > 5% 허용 기준")


def run_import(json_path: Path, dry_run: bool = False) -> dict:
    if not json_path.exists():
        raise FileNotFoundError(f"BOQ specs JSON 없음: {json_path}")

    with open(json_path, encoding="utf-8") as f:
        records: list[dict] = json.load(f)

    total = len(records)
    if not dry_run:
        db.init_db()

    imported, skipped, errors, skip_log, error_log = _process_records(records, dry_run)
    _print_summary(total, imported, skipped, errors, skip_log, error_log, dry_run)

    return {
        "total": total,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "error_rate": errors / total if total else 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BOQ 부재 스펙 임포터")
    parser.add_argument("--path", type=Path, default=_DEFAULT_JSON_PATH,
                        help="boq_member_specs.json 경로 (또는 BOQ_SPECS_JSON 환경변수)")
    parser.add_argument("--dry-run", action="store_true",
                        help="DB 쓰기 없이 검증만 실행")
    args = parser.parse_args()

    result = run_import(args.path, dry_run=args.dry_run)
    sys.exit(0 if result["error_rate"] <= 0.05 else 1)
