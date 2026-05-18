"""
claude_track_probe5_slab_blocks.py — SLAB 일람표 INSERT 블록 + LWPOLYLINE 직독

가설: 일람표는 단면을 INSERT 블록(이름이 S1, S2...) 또는 큰 LWPOLYLINE으로 그림.
"""
from __future__ import annotations
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ezdxf
from core.dxf_parser.safe_reader import safe_readfile

DXF_SLAB_LIST = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S40-121~124 지하주차장 슬래브 리스트.dxf'
OUT_PATH = Path('d:/Git/FreeCAD_4TH/output/claude_track_slab_blocks.json')


def main():
    print('SLAB_LIST 로드...', flush=True)
    doc = safe_readfile(DXF_SLAB_LIST)
    msp = doc.modelspace()

    # INSERT 블록 이름 분포
    insert_names: Counter = Counter()
    insert_positions: list = []
    for e in msp:
        if e.dxftype() == 'INSERT':
            try:
                name = e.dxf.name
                insert_names[name] += 1
                insert_positions.append({
                    'name': name,
                    'x': round(e.dxf.insert.x, 0),
                    'y': round(e.dxf.insert.y, 0),
                    'layer': e.dxf.layer,
                })
            except Exception:
                pass
    print(f'\n[INSERT 블록]: {sum(insert_names.values())}건, {len(insert_names)} unique')
    print('TOP 30:')
    for name, ct in insert_names.most_common(30):
        print(f'  {ct:5d}  "{name}"')

    # 모든 BLOCK 정의 이름
    all_blocks = []
    for blk in doc.blocks:
        all_blocks.append(blk.name)
    s_blocks = [b for b in all_blocks if re.match(r'^S\d', b, re.IGNORECASE)]
    print(f'\n[전체 BLOCK 정의]: {len(all_blocks)}개')
    print(f'  S 시작: {len(s_blocks)}개 — {s_blocks[:30]}')

    # LWPOLYLINE 분포 (단면 외곽)
    polylines = []
    for e in msp:
        if e.dxftype() == 'LWPOLYLINE':
            try:
                pts = list(e.get_points())
                if not pts:
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                w = max(xs) - min(xs)
                h = max(ys) - min(ys)
                polylines.append({
                    'cx': round((min(xs)+max(xs))/2, 0),
                    'cy': round((min(ys)+max(ys))/2, 0),
                    'w': round(w, 0),
                    'h': round(h, 0),
                    'pts': len(pts),
                    'layer': e.dxf.layer,
                    'closed': e.is_closed,
                })
            except Exception:
                pass

    print(f'\n[LWPOLYLINE]: {len(polylines)}개')
    # 큰 LWPOLYLINE만 (단면 외곽 후보)
    big_pls = [p for p in polylines if p['w'] > 1000 and p['h'] > 200]
    print(f'  큰 폴리라인 (w>1m, h>0.2m): {len(big_pls)}개')
    layer_counter = Counter(p['layer'] for p in big_pls)
    print(f'  레이어 분포: {layer_counter.most_common(5)}')

    # SLAB 일람표 단면별 텍스트 매칭 가능성
    # 큰 폴리라인의 중심 근처 텍스트 수집
    texts = []
    for e in msp:
        if e.dxftype() in ('TEXT', 'MTEXT'):
            try:
                txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
                if txt:
                    texts.append({
                        'text': txt,
                        'x': round(e.dxf.insert.x, 0),
                        'y': round(e.dxf.insert.y, 0),
                    })
            except Exception:
                pass
    print(f'\n[텍스트]: {len(texts)}개')

    # 각 큰 폴리라인에 가장 가까운 짧은 텍스트
    if big_pls and texts:
        sample = big_pls[:5]
        print(f'\n[샘플 단면 5개의 근접 텍스트]:')
        for i, pl in enumerate(sample):
            cx, cy = pl['cx'], pl['cy']
            # 250mm 반경 안의 짧은 텍스트
            nearby = [(t, abs(t['x']-cx) + abs(t['y']-cy))
                      for t in texts
                      if abs(t['x']-cx) < pl['w'] and abs(t['y']-cy) < pl['h'] * 2]
            nearby.sort(key=lambda x: x[1])
            print(f'  단면 {i} (cx={cx}, cy={cy}, w={pl["w"]}, h={pl["h"]}, layer={pl["layer"]}):')
            for t, d in nearby[:8]:
                print(f'    d={d:5.0f}  "{t["text"]}"')

    summary = {
        'insert_block_count': sum(insert_names.values()),
        'insert_unique_blocks': len(insert_names),
        'insert_top30': insert_names.most_common(30),
        'all_blocks_count': len(all_blocks),
        's_blocks': s_blocks,
        'polylines_count': len(polylines),
        'big_polylines_count': len(big_pls),
        'big_pl_layers': layer_counter.most_common(10),
        'sample_block_positions': insert_positions[:30],
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    OUT_PATH.write_bytes(payload.encode('utf-8', errors='replace'))
    print(f'\n저장: {OUT_PATH}')


if __name__ == '__main__':
    main()
