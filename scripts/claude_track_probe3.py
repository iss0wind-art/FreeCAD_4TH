"""
claude_track_probe3.py — 박제 #2(SLAB 라벨), PKG 격자 재검토, 박제 #4(DONG XR 인코딩)

방부장 원칙: 추측 배제. 데이터와 도면에 의존.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf

DXF_PKG  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'
DXF_SLAB_LIST = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S40-121~124 지하주차장 슬래브 리스트.dxf'
DXF_DONG_101 = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'

OUT_PATH = Path('d:/Git/FreeCAD_4TH/output/claude_track_probe3.json')


# ─────────────────────────────────────────────────────────────
# 1) PKG 격자 라벨 재검토 — 모든 짧은 텍스트 패턴 수집
# ─────────────────────────────────────────────────────────────
def probe_pkg_grid_labels(doc) -> dict:
    """PKG의 모든 짧은 TEXT를 정규식 없이 패턴별 카운트.

    - 레이어가 GRID/AXIS/축 관련인 것
    - 1~5자 짧은 텍스트
    - 숫자 only / 알파벳 only / 혼합
    """
    msp = doc.modelspace()
    grid_layer_pat = re.compile(r'GRID|AXIS|축|기준선|XY', re.IGNORECASE)
    short_texts: list = []
    grid_layer_texts: list = []
    layer_short_text_counter: dict = defaultdict(Counter)

    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            layer = e.dxf.layer
            pos = e.dxf.insert
            if not txt or len(txt) > 5:
                continue
            entry = {
                'text': txt,
                'layer': layer,
                'x': round(pos.x, 0),
                'y': round(pos.y, 0),
            }
            short_texts.append(entry)
            layer_short_text_counter[layer][txt] += 1
            if grid_layer_pat.search(layer):
                grid_layer_texts.append(entry)
        except Exception:
            pass

    # 레이어별 short text 종류 수
    layer_summary = []
    for ly, cnt in layer_short_text_counter.items():
        layer_summary.append({
            'layer': ly,
            'unique_short_texts': len(cnt),
            'total_short_texts': sum(cnt.values()),
            'top_5': cnt.most_common(5),
        })
    layer_summary.sort(key=lambda x: -x['total_short_texts'])

    # 패턴별 카운트
    pat_alpha_single = re.compile(r'^[A-Za-z]$')
    pat_alpha_multi = re.compile(r'^[A-Za-z]{2,4}$')
    pat_digit = re.compile(r'^\d{1,3}$')
    pat_alpha_digit = re.compile(r'^[A-Za-z]\d{1,3}$|^\d[A-Za-z]$')

    pattern_counter = Counter({
        'alpha_single': sum(1 for s in short_texts if pat_alpha_single.match(s['text'])),
        'alpha_multi': sum(1 for s in short_texts if pat_alpha_multi.match(s['text'])),
        'digit_only': sum(1 for s in short_texts if pat_digit.match(s['text'])),
        'alpha_digit': sum(1 for s in short_texts if pat_alpha_digit.match(s['text'])),
    })

    # 가장 흔한 short text 50개
    top_texts = Counter(s['text'] for s in short_texts).most_common(50)

    return {
        'total_short_text_count': len(short_texts),
        'pattern_counter': dict(pattern_counter),
        'top_50_short_texts': top_texts,
        'grid_layer_text_count': len(grid_layer_texts),
        'grid_layer_text_sample': grid_layer_texts[:30],
        'layer_summary_top10': layer_summary[:10],
    }


# ─────────────────────────────────────────────────────────────
# 2) SLAB 일람표 vs PKG 평면도 라벨 시스템 비교
# ─────────────────────────────────────────────────────────────
def probe_slab_labels(doc, name: str) -> dict:
    """SLAB 라벨 후보 텍스트 추출."""
    msp = doc.modelspace()
    # SLAB 일람표 패턴: S1, S2, ..., 또는 일람표 번호
    slab_label_pat = re.compile(r'^S\d{1,3}[A-Za-z]?$|^[A-Z]\d{0,2}$|^\d{1,3}$', re.IGNORECASE)
    candidates = []
    layer_counter: Counter = Counter()

    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            layer = e.dxf.layer
            if not txt or len(txt) > 6:
                continue
            if slab_label_pat.match(txt):
                candidates.append({
                    'text': txt,
                    'layer': layer,
                    'x': round(e.dxf.insert.x, 0),
                    'y': round(e.dxf.insert.y, 0),
                })
                layer_counter[layer] += 1
        except Exception:
            pass

    # 라벨 종류 카운트
    text_counter = Counter(c['text'] for c in candidates)
    return {
        'name': name,
        'candidate_count': len(candidates),
        'unique_labels': len(text_counter),
        'top_30_labels': text_counter.most_common(30),
        'layer_distribution': layer_counter.most_common(10),
        'sample_5': candidates[:5],
    }


# ─────────────────────────────────────────────────────────────
# 3) DONG XR 인코딩 진단
# ─────────────────────────────────────────────────────────────
def probe_dong_encoding(path: str) -> dict:
    """DONG 도면을 cp949/utf-8로 각각 시도 → 레이어명 비교."""
    results = {}
    for enc in ['cp949', 'utf-8', 'utf-8-sig', 'mbcs']:
        try:
            doc = ezdxf.readfile(path, encoding=enc)
            layers = []
            unknown = 0
            for layer in doc.layers:
                name = layer.dxf.name
                # surrogates / replacement char 검출
                has_surrogate = any(0xDC00 <= ord(c) <= 0xDFFF or 0xD800 <= ord(c) <= 0xDBFF for c in name)
                broken = has_surrogate or '�' in name or '?' in name
                if broken:
                    unknown += 1
                layers.append({'name': name[:50], 'broken': broken})
            results[enc] = {
                'success': True,
                'layer_count': len(layers),
                'broken_count': unknown,
                'broken_pct': round(unknown / max(1, len(layers)) * 100, 1),
                'sample_broken': [l['name'] for l in layers if l['broken']][:10],
                'sample_good': [l['name'] for l in layers if not l['broken'] and not l['name'].startswith(('0', 'A-', 'S-'))][:5],
            }
        except Exception as e:
            results[enc] = {'success': False, 'error': str(e)[:100]}
    return results


# ─────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────
def main():
    out = {}

    print('=== 1) PKG 격자 라벨 재검토 ===')
    t = time.time()
    doc_pkg = ezdxf.readfile(DXF_PKG, encoding='cp949')
    print(f'  로드 {time.time()-t:.1f}s')
    pkg_grid = probe_pkg_grid_labels(doc_pkg)
    out['pkg_grid_relook'] = pkg_grid
    print(f'  짧은 텍스트 {pkg_grid["total_short_text_count"]}건')
    print(f'  패턴: {pkg_grid["pattern_counter"]}')
    print(f'  GRID 레이어 텍스트: {pkg_grid["grid_layer_text_count"]}건')
    print('  TOP 20 short text:')
    for txt, ct in pkg_grid['top_50_short_texts'][:20]:
        print(f'    {ct:5d}  "{txt}"')
    print('  레이어별 short text TOP 5:')
    for ly in pkg_grid['layer_summary_top10'][:5]:
        print(f'    {ly["total_short_texts"]:5d} ({ly["unique_short_texts"]} unique)  {ly["layer"]}')

    print('\n=== 2) SLAB 라벨 시스템 비교 ===')
    pkg_slab = probe_slab_labels(doc_pkg, 'PKG_평면도')
    out['slab_labels_pkg'] = pkg_slab
    print(f'  PKG 평면도: {pkg_slab["candidate_count"]}건, {pkg_slab["unique_labels"]} unique')
    print(f'  TOP 10: {pkg_slab["top_30_labels"][:10]}')

    print('\n  SLAB_LIST 일람표 로드...')
    t = time.time()
    doc_sl = ezdxf.readfile(DXF_SLAB_LIST, encoding='cp949')
    print(f'  로드 {time.time()-t:.1f}s')
    sl_labels = probe_slab_labels(doc_sl, 'SLAB_일람표')
    out['slab_labels_list'] = sl_labels
    print(f'  SLAB 일람표: {sl_labels["candidate_count"]}건, {sl_labels["unique_labels"]} unique')
    print(f'  TOP 10: {sl_labels["top_30_labels"][:10]}')

    # 라벨 매칭 가능성
    pkg_set = set(t for t, _ in pkg_slab['top_30_labels'])
    sl_set = set(t for t, _ in sl_labels['top_30_labels'])
    common = pkg_set & sl_set
    print(f'\n  공통 라벨 (TOP30 기준): {len(common)}개 — {sorted(common)[:20]}')
    out['slab_label_match_top30'] = {
        'pkg_top30': sorted(pkg_set),
        'list_top30': sorted(sl_set),
        'common': sorted(common),
        'pkg_only': sorted(pkg_set - sl_set),
        'list_only': sorted(sl_set - pkg_set),
    }

    print('\n=== 3) DONG_101 인코딩 진단 ===')
    enc_result = probe_dong_encoding(DXF_DONG_101)
    out['dong_encoding'] = enc_result
    for enc, info in enc_result.items():
        if info.get('success'):
            print(f'  {enc}: 레이어 {info["layer_count"]}, 깨짐 {info["broken_count"]} ({info["broken_pct"]}%)')
            if info['sample_broken']:
                print(f'    깨짐 sample: {info["sample_broken"][:3]}')
            if info['sample_good']:
                print(f'    한국어 sample: {info["sample_good"][:3]}')
        else:
            print(f'  {enc}: FAIL — {info.get("error", "")[:60]}')

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(out, ensure_ascii=False, indent=2)
    OUT_PATH.write_bytes(payload.encode('utf-8', errors='replace'))
    print(f'\n저장: {OUT_PATH}')


if __name__ == '__main__':
    main()
