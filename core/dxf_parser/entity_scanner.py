"""
entity_scanner.py — DXF 전수 엔티티 스캔
=========================================
INSERT 재귀 전개 포함. 레이어별·유형별 인벤토리.
"하나도 빠트리지 않는" 파싱의 첫 단계 — 무엇이 얼마나 있는가.

사용:
    from core.dxf_parser.entity_scanner import scan, iter_all
    result = scan("path/to/drawing.dxf")
    print(result.report())
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

import ezdxf

sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ─────────────────────────────────────────────────────────────
# 1. 전수 엔티티 순회 (INSERT 재귀 포함)
# ─────────────────────────────────────────────────────────────

def iter_all(container, depth: int = 0, max_depth: int = 8) -> Iterator:
    """모든 엔티티 재귀 순회 — INSERT 내부까지.

    한국 구조도면은 INSERT(블록 참조) 안에 INSERT가 중첩된다.
    max_depth=8로 충분히 깊이 파고든다.
    """
    if depth > max_depth:
        return
    for e in container:
        yield e
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_all(list(e.virtual_entities()), depth + 1, max_depth)
            except Exception:
                pass


def iter_clip(container, clip: Optional[Tuple[float,float,float,float]],
              depth: int = 0, max_depth: int = 8) -> Iterator:
    """클립 영역 안 엔티티만 순회."""
    if depth > max_depth:
        return
    for e in container:
        if clip is not None:
            try:
                pos = e.dxf.insert
                if not (clip[0] <= pos.x <= clip[2] and clip[1] <= pos.y <= clip[3]):
                    if e.dxftype() != 'INSERT':
                        continue
            except Exception:
                pass
        yield e
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_clip(list(e.virtual_entities()), clip,
                                     depth + 1, max_depth)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────
# 2. 스캔 결과 자료구조
# ─────────────────────────────────────────────────────────────

@dataclass
class LayerSummary:
    name: str
    counts: Dict[str, int] = field(default_factory=dict)
    total: int = 0

    def dominant_type(self) -> str:
        if not self.counts:
            return 'EMPTY'
        return max(self.counts, key=lambda k: self.counts[k])


@dataclass
class ScanResult:
    """DXF 전수 스캔 결과."""
    total_entities: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_layer: Dict[str, LayerSummary] = field(default_factory=dict)
    text_samples: List[str] = field(default_factory=list)
    block_names: List[str] = field(default_factory=list)  # INSERT 블록명 목록
    lwpoly_areas: List[float] = field(default_factory=list)  # 닫힌 LWPOLYLINE 면적

    def report(self, top_n: int = 30) -> str:
        lines = [
            f'전체 엔티티: {self.total_entities:,}',
            '',
            '유형별:',
        ]
        for t, cnt in sorted(self.by_type.items(), key=lambda x: -x[1])[:20]:
            lines.append(f'  {t:<22} {cnt:>8,}')

        lines += ['', f'레이어별 (상위 {top_n}):']
        sorted_layers = sorted(self.by_layer.items(),
                               key=lambda x: -x[1].total)[:top_n]
        for name, ls in sorted_layers:
            dominant = ls.dominant_type()
            lines.append(f'  {name:<42} {ls.total:>7,}  [{dominant}]')

        if self.block_names:
            lines += ['', f'INSERT 블록명 (상위 30):']
            seen: Dict[str, int] = defaultdict(int)
            for n in self.block_names:
                seen[n] += 1
            for name, cnt in sorted(seen.items(), key=lambda x: -x[1])[:30]:
                lines.append(f'  {name:<40} {cnt:>5}회')

        if self.lwpoly_areas:
            areas = sorted(self.lwpoly_areas, reverse=True)
            lines += ['', f'닫힌 LWPOLYLINE 면적 분포 (상위 10, m²):']
            for a in areas[:10]:
                lines.append(f'  {a/1e6:>12.1f} m²')

        return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────
# 3. 스캔 실행
# ─────────────────────────────────────────────────────────────

def scan(dxf_path: str, encoding: str = 'cp949',
         clip: Optional[Tuple[float,float,float,float]] = None) -> ScanResult:
    """DXF 전수 스캔. INSERT 재귀 포함.

    Args:
        dxf_path: DXF 파일 경로
        encoding: 인코딩 (한국 도면 = cp949)
        clip: (xmin,ymin,xmax,ymax) — 특정 영역만 집계 (None=전체)
    """
    doc = ezdxf.readfile(dxf_path, encoding=encoding)
    msp = doc.modelspace()

    result = ScanResult()
    by_type: Dict[str, int] = defaultdict(int)
    by_layer: Dict[str, LayerSummary] = {}

    for e in iter_all(msp):
        t = e.dxftype()

        # 클립 체크 (TEXT/INSERT 등 insert 속성 가진 것만)
        if clip is not None:
            try:
                pos = e.dxf.insert
                if not (clip[0] <= pos.x <= clip[2] and
                        clip[1] <= pos.y <= clip[3]):
                    continue
            except Exception:
                pass

        by_type[t] += 1
        result.total_entities += 1

        try:
            layer = e.dxf.layer
        except Exception:
            layer = '(none)'

        if layer not in by_layer:
            by_layer[layer] = LayerSummary(name=layer)
        ls = by_layer[layer]
        ls.counts[t] = ls.counts.get(t, 0) + 1
        ls.total += 1

        # INSERT 블록명 수집
        if t == 'INSERT':
            try:
                result.block_names.append(e.dxf.name)
            except Exception:
                pass

        # 닫힌 LWPOLYLINE 면적 수집
        elif t == 'LWPOLYLINE':
            try:
                flags = e.dxf.flags
                if flags & 1:  # LWPOLYLINE_CLOSED
                    pts = [(p[0], p[1]) for p in e.get_points()]
                    if len(pts) >= 3:
                        area = abs(sum(
                            pts[i][0] * pts[(i+1) % len(pts)][1] -
                            pts[(i+1) % len(pts)][0] * pts[i][1]
                            for i in range(len(pts))
                        ) / 2)
                        result.lwpoly_areas.append(area)
            except Exception:
                pass

        # 텍스트 샘플
        elif t in ('TEXT', 'MTEXT') and len(result.text_samples) < 300:
            try:
                txt = (e.dxf.text if t == 'TEXT' else e.text).strip()
                if txt:
                    result.text_samples.append(txt)
            except Exception:
                pass

    result.by_type = dict(by_type)
    result.by_layer = by_layer
    return result


def quick_text_grep(dxf_path: str, pattern: str,
                    encoding: str = 'cp949') -> List[Tuple[str, float, float]]:
    """DXF에서 특정 패턴 텍스트만 빠르게 검색.

    Returns:
        [(text, x, y), ...]
    """
    import re
    pat = re.compile(pattern, re.IGNORECASE)
    doc = ezdxf.readfile(dxf_path, encoding=encoding)
    msp = doc.modelspace()
    results = []

    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if pat.search(txt):
                pos = e.dxf.insert
                results.append((txt, pos.x, pos.y))
        except Exception:
            pass

    return results
