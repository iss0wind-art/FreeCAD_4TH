#!/usr/bin/env python3
"""
BOQ EasyFrame — DXF 전처리 파서
역할: 날것 DXF → 4,000자 마크다운 엑기스
비용: $0 (로컬 전담)

3지국 파이프라인 연동 순서:
  StructuralExtractor / safe_reader → (1차 파싱 결과) → 이 파일 → @dxf-parser
"""

import sys
from pathlib import Path
from collections import defaultdict

try:
    import ezdxf
except ImportError:
    print("ezdxf 미설치. 실행: pip install ezdxf", file=sys.stderr)
    sys.exit(1)


def classify_entity(entity) -> str:
    layer = getattr(entity.dxf, "layer", "").upper()
    if any(k in layer for k in ["WALL", "SLAB", "BEAM", "COL", "벽", "슬라브", "보", "기둥"]):
        return "structural"
    elif any(k in layer for k in ["DOOR", "WIN", "STAIR", "문", "창", "계단"]):
        return "architectural"
    elif any(k in layer for k in ["ELEC", "MECH", "PLUMB", "전기", "기계", "배관"]):
        return "mep"
    return "unknown"


def parse_dxf(filepath: str) -> dict:
    path = Path(filepath)
    if not path.exists():
        return {"error": f"파일 없음: {filepath}"}

    try:
        doc = ezdxf.readfile(str(path))
    except Exception as e:
        return {"error": f"로드 실패: {e}"}

    msp = doc.modelspace()
    counts: dict = defaultdict(int)
    layers: dict = defaultdict(int)
    classified: dict = defaultdict(int)

    for entity in msp:
        etype = entity.dxftype()
        counts[etype] += 1
        layer = getattr(entity.dxf, "layer", "(none)")
        layers[layer] += 1
        classified[classify_entity(entity)] += 1

    return {
        "file": path.name,
        "entity_counts": dict(counts),
        "layer_counts": dict(sorted(layers.items(), key=lambda x: -x[1])[:20]),
        "classified": dict(classified),
        "total": sum(counts.values()),
    }


def to_markdown(stats: dict) -> str:
    if "error" in stats:
        return f"## 오류\n{stats['error']}"

    classified = stats.get("classified", {})
    total = stats.get("total", 0)
    structural = classified.get("structural", 0)
    unknown = classified.get("unknown", 0)

    red_circle = unknown > total * 0.3  # 미분류 30% 초과 시 빨간 원

    lines = [
        "## 파싱 결과 요약",
        f"- 처리 파일: {stats['file']}",
        f"- 전체 엔티티: {total:,}개",
        f"- 구조 부재(structural): {structural:,}개",
        f"- 미분류(unknown): {unknown:,}개"
        + ("  ← [빨간 원] 점검 필요" if red_circle else ""),
        "",
        "## 레이어 분포 (상위 20)",
    ]

    for layer, cnt in list(stats.get("layer_counts", {}).items())[:20]:
        lines.append(f"- `{layer}`: {cnt:,}개")

    lines += ["", "## 엔티티 유형"]
    for etype, cnt in sorted(
        stats.get("entity_counts", {}).items(), key=lambda x: -x[1]
    )[:10]:
        lines.append(f"- {etype}: {cnt:,}개")

    return "\n".join(lines)[:4000]  # 4,000자 제한


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python tools/dxf_parser.py [DXF파일경로]")
        sys.exit(1)
    stats = parse_dxf(sys.argv[1])
    print(to_markdown(stats))
