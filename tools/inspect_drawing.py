"""
tools/inspect_drawing.py — DXF 도면 완전 검사 도구
====================================================
다음 사람, 다음 도면에 즉시 사용.

사용법:
    python tools/inspect_drawing.py <DXF파일> [--clip xmin,ymin,xmax,ymax]
    python tools/inspect_drawing.py <DXF파일> --text-grep "SL|EL"
    python tools/inspect_drawing.py <DXF파일> --ev            # E/V 코어 검출
    python tools/inspect_drawing.py <DXF파일> --grid          # 격자 라벨 수집
    python tools/inspect_drawing.py <DXF파일> --slab-outline  # 슬라브 외곽 추출
    python tools/inspect_drawing.py <DXF파일> --all           # 전체 검사

출력:
    화면: 요약 보고서
    파일: output/inspect_<파일명>.json

목적:
    새 도면을 받았을 때 → 먼저 이 스크립트 실행
    → 레이어명, 블록명, 격자, E/V 위치 파악
    → 파싱 전략 결정
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf
from core.dxf_parser.entity_scanner import scan, quick_text_grep
from core.dxf_parser.ev_detector import TextLabelEVDetector, GridAnchorDetector
from core.dxf_parser.level_parser import parse_dxf as parse_levels
from core.dxf_parser.full_extractor import FullExtractor
from core.dxf_parser.step_zone import parse_step_zones


def parse_clip(s: str):
    parts = [float(x.strip()) for x in s.split(',')]
    if len(parts) != 4:
        raise ValueError('clip은 xmin,ymin,xmax,ymax 형식')
    return tuple(parts)


def main():
    parser = argparse.ArgumentParser(description='DXF 도면 완전 검사')
    parser.add_argument('dxf', help='DXF 파일 경로')
    parser.add_argument('--clip', help='영역 제한 xmin,ymin,xmax,ymax')
    parser.add_argument('--encoding', default='cp949')
    parser.add_argument('--text-grep', help='텍스트 검색 패턴 (정규식)')
    parser.add_argument('--ev', action='store_true', help='E/V 코어 검출')
    parser.add_argument('--grid', action='store_true', help='격자 라벨 수집')
    parser.add_argument('--slab-outline', action='store_true', help='슬라브 외곽 추출')
    parser.add_argument('--levels', action='store_true', help='표고·단차 파싱')
    parser.add_argument('--steps', action='store_true', help='단차 구역 파싱')
    parser.add_argument('--all', action='store_true', help='전체 검사')
    parser.add_argument('--output-dir', default='output')
    args = parser.parse_args()

    dxf_path = args.dxf
    clip = parse_clip(args.clip) if args.clip else None
    encoding = args.encoding

    print(f'\n{"="*60}')
    print(f'DXF 도면 검사: {Path(dxf_path).name}')
    if clip:
        print(f'  clip: {clip}')
    print(f'{"="*60}')

    do_all = args.all
    report = {'dxf': dxf_path, 'clip': clip, 'sections': {}}

    # ── 1. 기본 스캔 (항상 실행) ──────────────────────────────
    t0 = time.time()
    print('\n[1] 전수 엔티티 스캔...')
    result = scan(dxf_path, encoding=encoding, clip=clip)
    print(result.report())
    report['sections']['entity_scan'] = {
        'total': result.total_entities,
        'by_type': result.by_type,
        'top_layers': {
            name: {'total': ls.total, 'dominant': ls.dominant_type()}
            for name, ls in sorted(result.by_layer.items(),
                                   key=lambda x: -x[1].total)[:20]
        },
        'block_names_top30': list({n: None for n in result.block_names[:100]}.keys())[:30],
    }
    print(f'  소요: {time.time()-t0:.1f}s')

    # ── 2. 텍스트 검색 ──────────────────────────────────────
    if args.text_grep or do_all:
        pattern = args.text_grep or r'SL|EL|표고|B[123]F|층고|단차'
        print(f'\n[2] 텍스트 검색: "{pattern}"')
        hits = quick_text_grep(dxf_path, pattern, encoding)
        hits_sorted = sorted(hits, key=lambda x: -x[2])[:50]
        for txt, x, y in hits_sorted:
            print(f'  ({x:.0f},{y:.0f})  {txt[:60]}')
        report['sections']['text_grep'] = [
            {'text': txt, 'x': x, 'y': y} for txt, x, y in hits_sorted
        ]
        print(f'  {len(hits)}건 발견 (상위 50 표시)')

    # ── 3. E/V 코어 검출 ────────────────────────────────────
    if args.ev or do_all:
        print('\n[3] E/V 코어 기준점 검출...')
        doc = ezdxf.readfile(dxf_path, encoding=encoding)
        detector = TextLabelEVDetector(dong_clip=clip)
        anchor = detector.detect(doc, dong='', floor=0, sheet_id='')
        if anchor:
            print(f'  EV 앵커: SW=({anchor.sw_corner[0]:.0f},{anchor.sw_corner[1]:.0f}) '
                  f'신뢰도={anchor.confidence:.2f}')
            print(f'  EV BBox: {tuple(round(v) for v in anchor.ev_box)}')
            report['sections']['ev_anchor'] = {
                'sw_corner': list(anchor.sw_corner),
                'ev_box': list(anchor.ev_box),
                'confidence': anchor.confidence,
            }
        else:
            print('  E/V 코어 미검출 — 격자 앵커 시도')
            doc2 = ezdxf.readfile(dxf_path, encoding=encoding)
            grid_det = GridAnchorDetector(dong_clip=clip)
            grid_anchor = grid_det.detect(doc2)
            if grid_anchor:
                print(f'  격자 앵커: ({grid_anchor.x:.0f},{grid_anchor.y:.0f}) '
                      f'신뢰도={grid_anchor.confidence:.2f}')
                report['sections']['ev_anchor'] = {
                    'sw_corner': [grid_anchor.x, grid_anchor.y],
                    'strategy': grid_anchor.strategy,
                    'confidence': grid_anchor.confidence,
                }
            else:
                print('  격자 앵커도 미검출 — 수동 지정 필요')
                report['sections']['ev_anchor'] = None

    # ── 4. 격자 라벨 ────────────────────────────────────────
    if args.grid or do_all:
        print('\n[4] 격자 라벨 수집...')
        doc = ezdxf.readfile(dxf_path, encoding=encoding)
        grid_det = GridAnchorDetector(dong_clip=clip)
        grid_info = grid_det.detect_all_grid_labels(doc)
        print(f'  X 격자: {sorted(grid_info["x"].keys())}')
        print(f'  Y 격자: {sorted(grid_info["y"].keys())}')
        report['sections']['grid_labels'] = {
            'x': {k: v[:3] for k, v in grid_info['x'].items()},
            'y': {k: v[:3] for k, v in grid_info['y'].items()},
        }

    # ── 5. 표고·단차 파싱 ───────────────────────────────────
    if args.levels or do_all:
        print('\n[5] 표고·단차 파싱...')
        ls = parse_levels(dxf_path, encoding=encoding, clip=clip)
        print(ls.summary())
        print('  층 SL:')
        for floor, sl in sorted(ls.floor_sl.items()):
            print(f'    {floor}: SL={sl:.0f}mm')
        print(f'  단차 {len(ls.steps)}건:')
        for s in ls.steps[:10]:
            print(f'    ({s.x:.0f},{s.y:.0f}) "{s.text[:50]}"')
        report['sections']['levels'] = {
            'floor_sl': ls.floor_sl,
            'step_count': len(ls.steps),
            'pit_count': len(ls.pits),
            'steps_top10': [
                {'text': s.text, 'x': s.x, 'y': s.y, 'value_mm': s.value_mm}
                for s in ls.steps[:10]
            ],
        }

    # ── 6. 슬라브 외곽 ──────────────────────────────────────
    if args.slab_outline or do_all:
        print('\n[6] 슬라브 외곽 LWPOLYLINE 추출...')
        doc = ezdxf.readfile(dxf_path, encoding=encoding)
        extractor = FullExtractor(min_slab_area_m2=50.0)
        ext_result = extractor.extract(doc, clip=clip)
        print(f'  {len(ext_result.slab_outlines)}개 외곽 발견:')
        for i, so in enumerate(ext_result.slab_outlines[:5]):
            print(f'    [{i}] {so.area_m2:.0f} m²  {len(so.pts)}점  레이어={so.layer}')
            if i == 0:
                bbox = so.bbox()
                print(f'       BBox: ({bbox[0]:.0f},{bbox[1]:.0f}) ~ '
                      f'({bbox[2]:.0f},{bbox[3]:.0f})')
        print(f'\n  기둥: {len(ext_result.columns)}개')
        for src, cnt in ext_result.column_count_by_source().items():
            print(f'    {src}: {cnt}개')
        report['sections']['slab_outline'] = {
            'count': len(ext_result.slab_outlines),
            'top3': [
                {'area_m2': s.area_m2, 'pts_count': len(s.pts),
                 'layer': s.layer, 'bbox': list(s.bbox())}
                for s in ext_result.slab_outlines[:3]
            ],
            'column_count': len(ext_result.columns),
        }

    # ── 7. 단차 구역 ─────────────────────────────────────────
    if args.steps or do_all:
        print('\n[7] 단차 구역 파싱...')
        zone_map = parse_step_zones(dxf_path, encoding=encoding, clip=clip)
        print(zone_map.summary())
        if zone_map.zones:
            print('  단차 상위 10:')
            for z in zone_map.zones[:10]:
                abs_sl = z.absolute_sl(zone_map.base_sl)
                print(f'    ({z.x:.0f},{z.y:.0f}) {z.floor_label} delta={z.delta_mm:.0f}mm '
                      f'abs={abs_sl:.0f}mm  "{z.text[:40]}"')
        report['sections']['step_zones'] = {
            'count': len(zone_map.zones),
            'zones': [
                {'x': z.x, 'y': z.y, 'floor': z.floor_label,
                 'delta_mm': z.delta_mm, 'text': z.text[:60]}
                for z in zone_map.zones[:20]
            ],
        }

    # ── 저장 ────────────────────────────────────────────────
    os.makedirs(args.output_dir, exist_ok=True)
    stem = Path(dxf_path).stem[:40]
    out_path = os.path.join(args.output_dir, f'inspect_{stem}.json')
    with open(out_path, 'w', encoding='utf-8', errors='replace') as f:
        # surrogate 문자 제거 후 직렬화
        clean = _clean_json(report)
        json.dump(clean, f, ensure_ascii=False, indent=2)

    print(f'\n[완료] {time.time()-t0:.1f}s → {out_path}')


def _clean_json(obj):
    """surrogate 문자 포함 문자열 정제 — JSON 직렬화 실패 방지."""
    if isinstance(obj, str):
        return obj.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
    elif isinstance(obj, dict):
        return {_clean_json(k): _clean_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_clean_json(v) for v in obj]
    return obj


if __name__ == '__main__':
    main()
