"""
claude_track_probe.py — 끌로드 팀 트랙 데이터 카탈로그 작성

방부장 원칙: 추측 배제. 데이터와 도면에 의존. 모든 답은 도면에 있다.

목적:
  1. PKG 도면 EV 코어 텍스트 존재 확인 (박제 #3 EV 직독 가능성)
  2. PKG 시트/Layout 구조 파악 (시트별 좌표 origin 직독)
  3. PKG 모델공간 좌표 분포 파악 (1.4km X축 분산 사실 확인)
  4. SLAB 라벨 시스템 데이터 비교 (일람표 vs 평면도)

출력: output/claude_track_data_catalog.json
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf

# ─────────────────────────────────────────────────────────────
# 경로 (extract_coords.py와 동일)
# ─────────────────────────────────────────────────────────────
DXF_DONG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
DXF_PKG  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'
DXF_SLAB = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S40-121~124 지하주차장 슬래브 리스트.dxf'

OUT_PATH = Path('d:/Git/FreeCAD_4TH/output/claude_track_data_catalog.json')

# ─────────────────────────────────────────────────────────────
# 패턴 (ev_detector.py와 동일)
# ─────────────────────────────────────────────────────────────
EV_TEXT = re.compile(
    r'E/?V\b|ELEV|승강기|엘리베이터|ELEVATOR|LIFT|계단실|STAIR\s*HALL|코어|CORE',
    re.IGNORECASE,
)
EV_LAYER = re.compile(
    r'A[-_]?EV|EV[-_]CORE|S[-_]?CORE|승강|STAIR|ELEV|E_V|CORE|코어',
    re.IGNORECASE,
)
SLAB_LABEL = re.compile(r'^S\d+|^[A-Z]\b|SLAB|슬래브', re.IGNORECASE)


def probe_dxf(path: str, encoding: str = 'cp949') -> dict:
    """단일 DXF 파일 직독."""
    print(f'\n=== {path} ===', flush=True)
    t0 = time.time()
    try:
        doc = ezdxf.readfile(path, encoding=encoding)
    except Exception as e:
        return {'error': str(e), 'path': path}
    msp = doc.modelspace()
    load_t = time.time() - t0
    print(f'  로드 {load_t:.1f}s', flush=True)

    # 1. Layout 구조
    layouts = []
    for name in doc.layout_names():
        try:
            lay = doc.layouts.get(name)
            count = sum(1 for _ in lay)
            layouts.append({'name': name, 'entity_count': count})
        except Exception as e:
            layouts.append({'name': name, 'error': str(e)})

    # 2. 모델공간 직독
    ev_texts = []  # (x, y, text, layer)
    ev_layers = set()
    grid_x_labels: dict = defaultdict(list)
    grid_y_labels: dict = defaultdict(list)
    slab_labels: list = []
    layer_counter: Counter = Counter()
    type_counter: Counter = Counter()
    xs_all = []
    ys_all = []
    text_total = 0

    grid_x_pat = re.compile(r'^X\s*(\d+)$|^([A-Z])\s*$', re.IGNORECASE)
    grid_y_pat = re.compile(r'^Y\s*(\d+)$|^(\d+)\s*$', re.IGNORECASE)

    for e in msp:
        t = e.dxftype()
        type_counter[t] += 1
        try:
            layer_counter[e.dxf.layer] += 1
        except Exception:
            pass

        if t in ('TEXT', 'MTEXT'):
            text_total += 1
            try:
                txt = (e.dxf.text if t == 'TEXT' else e.text).strip()
                pos = e.dxf.insert
                xs_all.append(pos.x)
                ys_all.append(pos.y)
                if EV_TEXT.search(txt):
                    ev_texts.append({
                        'x': round(pos.x, 1),
                        'y': round(pos.y, 1),
                        'text': txt[:50],
                        'layer': e.dxf.layer,
                    })
                if SLAB_LABEL.match(txt) and len(txt) <= 8:
                    slab_labels.append({
                        'text': txt,
                        'x': round(pos.x, 1),
                        'y': round(pos.y, 1),
                        'layer': e.dxf.layer,
                    })
                mx = grid_x_pat.match(txt)
                if mx:
                    grid_x_labels[txt].append(round(pos.x, 1))
                my = grid_y_pat.match(txt)
                if my:
                    grid_y_labels[txt].append(round(pos.y, 1))
            except Exception:
                pass

        try:
            if t == 'INSERT' and EV_LAYER.search(e.dxf.layer):
                ev_layers.add(e.dxf.layer)
            elif EV_LAYER.search(getattr(e.dxf, 'layer', '')):
                ev_layers.add(e.dxf.layer)
        except Exception:
            pass

    # 3. 좌표 분포
    coord_stats = {}
    if xs_all:
        xs_sorted = sorted(xs_all)
        ys_sorted = sorted(ys_all)
        n = len(xs_all)
        coord_stats = {
            'text_count': n,
            'x_min': round(xs_sorted[0], 1),
            'x_max': round(xs_sorted[-1], 1),
            'x_p10': round(xs_sorted[n // 10], 1),
            'x_p50': round(xs_sorted[n // 2], 1),
            'x_p90': round(xs_sorted[n * 9 // 10], 1),
            'y_min': round(ys_sorted[0], 1),
            'y_max': round(ys_sorted[-1], 1),
            'x_span_mm': round(xs_sorted[-1] - xs_sorted[0], 1),
            'y_span_mm': round(ys_sorted[-1] - ys_sorted[0], 1),
        }

    parse_t = time.time() - t0 - load_t
    print(f'  파싱 {parse_t:.1f}s', flush=True)
    print(f'  엔티티: {sum(type_counter.values())}, TEXT/MTEXT: {text_total}', flush=True)
    print(f'  EV 텍스트: {len(ev_texts)}건, EV 레이어: {len(ev_layers)}', flush=True)
    print(f'  격자 X 라벨: {len(grid_x_labels)}, Y 라벨: {len(grid_y_labels)}', flush=True)
    print(f'  X span: {coord_stats.get("x_span_mm", 0):,.0f}mm', flush=True)

    return {
        'path': path,
        'load_seconds': round(load_t, 2),
        'parse_seconds': round(parse_t, 2),
        'layouts': layouts,
        'entity_total': sum(type_counter.values()),
        'type_top10': type_counter.most_common(10),
        'layer_top20': layer_counter.most_common(20),
        'text_total': text_total,
        'ev_texts': ev_texts[:50],  # 샘플 50개
        'ev_text_count': len(ev_texts),
        'ev_layers': sorted(ev_layers),
        'grid_x_label_count': len(grid_x_labels),
        'grid_y_label_count': len(grid_y_labels),
        'grid_x_sample': dict(list(grid_x_labels.items())[:10]),
        'grid_y_sample': dict(list(grid_y_labels.items())[:10]),
        'slab_label_sample': slab_labels[:30],
        'slab_label_count': len(slab_labels),
        'coord_stats': coord_stats,
    }


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results = {}

    targets = [
        ('PKG', DXF_PKG),
        ('DONG_101', DXF_DONG),
        ('SLAB_LIST', DXF_SLAB),
    ]

    for name, path in targets:
        try:
            results[name] = probe_dxf(path)
        except Exception as e:
            results[name] = {'fatal': str(e), 'path': path}
            print(f'  FATAL {name}: {e}', flush=True)

    payload = json.dumps(results, ensure_ascii=False, indent=2)
    # surrogates 안전 인코딩
    OUT_PATH.write_bytes(payload.encode('utf-8', errors='replace'))
    print(f'\n저장: {OUT_PATH}', flush=True)


if __name__ == '__main__':
    main()
