"""
claude_track_probe4_slab.py — SLAB 일람표 진짜 매칭 키 직독

[발견 — probe3]
PKG 평면도: S1~S13 (52 unique, 1197건)
SLAB 일람표: D, C, 200, 150, 300, 13, 10 등 (22 unique, 공통 0개)

[가설 검증]
일람표는 단면 ID와 두께/철근 두 시스템이 섞여있음.
일람표 안에 S1, S2 텍스트가 있는데 짧은 텍스트 필터(len<=6)에 걸려서 누락됐을 수도.
또는 일람표는 그림으로만 라벨이 있고 텍스트는 두께값만 있을 수도.

[직독 전략]
1. SLAB 일람표의 모든 TEXT/MTEXT를 길이 제한 없이 수집
2. 'S' 시작 패턴 검색 (S1, S2, ... S13, SL1, etc.)
3. 일람표 내 큰 폰트(text height) = 단면 제목 가능성 → 폰트 크기별 분포
4. INSERT 블록 내부 ATTRIB도 수집 (label이 ATTRIB일 수 있음)
"""
from __future__ import annotations
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ezdxf
from core.dxf_parser.safe_reader import safe_readfile

DXF_SLAB_LIST = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S40-121~124 지하주차장 슬래브 리스트.dxf'
OUT_PATH = Path('d:/Git/FreeCAD_4TH/output/claude_track_slab_list_deep.json')


def deep_text_walk(doc, max_depth: int = 8):
    """전수 TEXT 수집 — 길이 제한 없음, INSERT 블록 재귀."""
    msp = doc.modelspace()
    results = []  # (text, x, y, height, layer, source)

    def emit(e, source: str, ox: float = 0, oy: float = 0):
        try:
            t = e.dxftype()
            if t in ('TEXT', 'ATTRIB'):
                content = e.dxf.text
            elif t in ('MTEXT',):
                content = e.plain_text() if hasattr(e, 'plain_text') else e.text
            else:
                return
            content = (content or '').strip()
            if not content:
                return
            try:
                ip = e.dxf.insert if hasattr(e.dxf, 'insert') else e.dxf.location
                x, y = float(ip.x) + ox, float(ip.y) + oy
            except Exception:
                x, y = ox, oy
            try:
                height = float(getattr(e.dxf, 'height', 0))
            except Exception:
                height = 0
            try:
                layer = e.dxf.layer
            except Exception:
                layer = ''
            results.append({
                'text': content,
                'x': round(x, 1),
                'y': round(y, 1),
                'height': height,
                'layer': layer,
                'source': source,
            })
        except Exception:
            pass

    def walk(e, depth: int, ox: float, oy: float):
        et = e.dxftype()
        if et in ('TEXT', 'MTEXT', 'ATTRIB', 'ATTDEF'):
            emit(e, 'modelspace', ox, oy)
            return
        if et == 'INSERT':
            try:
                for attrib in e.attribs:
                    emit(attrib, 'attrib', ox, oy)
            except Exception:
                pass
            if depth >= max_depth:
                return
            try:
                ix = float(e.dxf.insert.x) + ox
                iy = float(e.dxf.insert.y) + oy
                block_name = e.dxf.name
                block = doc.blocks.get(block_name)
                if block is None:
                    return
                for child in block:
                    walk(child, depth + 1, ix, iy)
            except Exception:
                pass

    for e in msp:
        walk(e, 0, 0, 0)

    return results


def main():
    print('SLAB_LIST 로드...', flush=True)
    t = time.time()
    doc = safe_readfile(DXF_SLAB_LIST)
    print(f'  {time.time()-t:.1f}s')

    print('전수 TEXT walk (블록 재귀 포함)...', flush=True)
    t = time.time()
    texts = deep_text_walk(doc)
    print(f'  {time.time()-t:.1f}s, 총 {len(texts)}건')

    # 패턴별 분류
    s_pat = re.compile(r'^S\d+[A-Za-z]?$', re.IGNORECASE)
    sl_pat = re.compile(r'^SL\d+', re.IGNORECASE)
    has_s = [t for t in texts if s_pat.match(t['text'])]
    has_sl = [t for t in texts if sl_pat.match(t['text'])]
    label_like = [t for t in texts if re.match(r'^[A-Z]\d{1,3}[A-Za-z]?$', t['text'], re.IGNORECASE)]

    print(f'\n[패턴 매칭]')
    print(f'  S\\d+ (S1, S13...): {len(has_s)}건')
    if has_s:
        cnt = Counter(t['text'] for t in has_s)
        print(f'    종류: {sorted(cnt)[:30]}')
    print(f'  SL\\d+ (SL1...): {len(has_sl)}건')
    print(f'  알파벳+숫자 일반: {len(label_like)}건')
    if label_like:
        cnt = Counter(t['text'] for t in label_like)
        print(f'    TOP 20: {cnt.most_common(20)}')

    # 폰트 크기 분포 (단면 제목 vs 일반)
    height_counter: Counter = Counter()
    for t in texts:
        h = t['height']
        if h > 0:
            bin_h = round(h / 50) * 50  # 50 단위 binning
            height_counter[bin_h] += 1
    print(f'\n[텍스트 height 분포 (top 10)]')
    for h, c in height_counter.most_common(10):
        print(f'  height ~{h}: {c}건')

    # 큰 폰트 텍스트 (단면 제목 후보)
    if texts:
        max_h = max(t['height'] for t in texts)
        big_threshold = max_h * 0.5
        big_texts = [t for t in texts if t['height'] >= big_threshold and t['height'] > 0]
        print(f'\n[큰 폰트 (>={big_threshold:.0f}) 텍스트: {len(big_texts)}건]')
        big_cnt = Counter(t['text'] for t in big_texts)
        for txt, c in big_cnt.most_common(30):
            print(f'  ({c}x) "{txt}"')

    # source 분포
    src_counter = Counter(t['source'] for t in texts)
    print(f'\n[source 분포]: {dict(src_counter)}')

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        'total_texts': len(texts),
        's_pattern_count': len(has_s),
        's_pattern_unique': sorted(set(t['text'] for t in has_s)),
        'label_like_count': len(label_like),
        'label_like_top20': Counter(t['text'] for t in label_like).most_common(20),
        'height_distribution': dict(height_counter),
        'big_text_top30': big_cnt.most_common(30) if texts else [],
        'source_distribution': dict(src_counter),
        'first_500_samples': texts[:500],
    }
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    OUT_PATH.write_bytes(payload.encode('utf-8', errors='replace'))
    print(f'\n저장: {OUT_PATH}')


if __name__ == '__main__':
    main()
