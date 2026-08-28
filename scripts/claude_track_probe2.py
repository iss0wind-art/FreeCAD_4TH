"""
claude_track_probe2.py — PKG 시트 경계 직독 (paperspace + 모델공간 클러스터링)

박제 #3 진단:
  - PKG layouts: ['Model', '배치2'] — paperspace에 viewport가 있다면
    각 viewport는 모델공간 영역 → 시트 경계 정확히 알 수 있음
  - 없으면 모델공간 좌표 클러스터링으로 영역 추정
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf

DXF_PKG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'
OUT_PATH = Path('d:/Git/FreeCAD_4TH/output/claude_track_pkg_sheets.json')


def probe_paperspace(doc) -> dict:
    """배치2 paperspace의 viewport 직독."""
    info = {}
    for layout_name in doc.layout_names():
        if layout_name.lower() in ('model', '*model_space'):
            continue
        try:
            psp = doc.layouts.get(layout_name)
            viewports = []
            for vp in psp.query('VIEWPORT'):
                try:
                    vp_data = {
                        'paper_center': [round(vp.dxf.center[0], 1),
                                         round(vp.dxf.center[1], 1)],
                        'paper_size': [round(vp.dxf.width, 1),
                                       round(vp.dxf.height, 1)],
                        'view_center': [round(vp.dxf.view_center_point[0], 1),
                                        round(vp.dxf.view_center_point[1], 1)],
                        'view_height': round(vp.dxf.view_height, 1),
                        'status': vp.dxf.get('status', None),
                    }
                    viewports.append(vp_data)
                except Exception as e:
                    viewports.append({'error': str(e)})
            entity_types = Counter(e.dxftype() for e in psp)
            info[layout_name] = {
                'entity_count': sum(entity_types.values()),
                'entity_types': dict(entity_types),
                'viewports': viewports,
                'viewport_count': len(viewports),
            }
        except Exception as e:
            info[layout_name] = {'error': str(e)}
    return info


def cluster_modelspace_x(doc, bin_width: float = 100_000.0) -> dict:
    """모델공간 X 좌표 히스토그램으로 시트 영역 분리."""
    msp = doc.modelspace()
    xs = []
    for e in msp:
        try:
            t = e.dxftype()
            if t == 'INSERT':
                xs.append(e.dxf.insert.x)
            elif t in ('TEXT', 'MTEXT'):
                xs.append(e.dxf.insert.x)
            elif t == 'LINE':
                xs.append(e.dxf.start.x)
                xs.append(e.dxf.end.x)
            elif t == 'LWPOLYLINE':
                pts = list(e.get_points())
                if pts:
                    xs.append(pts[0][0])
                    xs.append(pts[-1][0])
            elif t == 'CIRCLE':
                xs.append(e.dxf.center.x)
        except Exception:
            pass

    if not xs:
        return {'error': 'no x coords'}

    xmin, xmax = min(xs), max(xs)
    bins: Counter = Counter()
    for x in xs:
        bin_idx = int((x - xmin) // bin_width)
        bins[bin_idx] += 1

    # 빈 bin 사이의 gap 찾기 → 시트 경계
    sorted_bins = sorted(bins.keys())
    gaps = []
    for i in range(len(sorted_bins) - 1):
        cur = sorted_bins[i]
        nxt = sorted_bins[i + 1]
        if nxt - cur > 2:  # 2칸(200m) 이상 비어있으면 시트 경계
            gap_x = xmin + (cur + 1) * bin_width
            gap_end_x = xmin + nxt * bin_width
            gaps.append({
                'gap_start_x': round(gap_x, 0),
                'gap_end_x': round(gap_end_x, 0),
                'gap_width_mm': round(gap_end_x - gap_x, 0),
            })

    # 시트별 영역 추정
    sheets = []
    cur_start = sorted_bins[0]
    for i in range(len(sorted_bins) - 1):
        if sorted_bins[i + 1] - sorted_bins[i] > 2:
            sheets.append({
                'x_min': round(xmin + cur_start * bin_width, 0),
                'x_max': round(xmin + (sorted_bins[i] + 1) * bin_width, 0),
                'entity_count': sum(bins[b] for b in sorted_bins
                                    if cur_start <= b <= sorted_bins[i]),
            })
            cur_start = sorted_bins[i + 1]
    sheets.append({
        'x_min': round(xmin + cur_start * bin_width, 0),
        'x_max': round(xmin + (sorted_bins[-1] + 1) * bin_width, 0),
        'entity_count': sum(bins[b] for b in sorted_bins
                            if b >= cur_start),
    })

    return {
        'x_total_min': round(xmin, 0),
        'x_total_max': round(xmax, 0),
        'x_total_span_mm': round(xmax - xmin, 0),
        'bin_width_mm': bin_width,
        'bin_count': len(bins),
        'gaps': gaps,
        'sheet_count_estimated': len(sheets),
        'sheets': sheets,
        'sample_count': len(xs),
    }


def main():
    print('=== PKG Paperspace + Modelspace 직독 ===')
    t0 = time.time()
    doc = ezdxf.readfile(DXF_PKG, encoding='cp949')
    print(f'로드 {time.time() - t0:.1f}s')

    print('\n[Paperspace viewport]')
    psp_info = probe_paperspace(doc)
    for name, info in psp_info.items():
        print(f'  {name}: 엔티티 {info.get("entity_count", "?")}, '
              f'viewport {info.get("viewport_count", "?")}')
        for vp in info.get('viewports', [])[:5]:
            if 'error' not in vp:
                print(f'    VP center={vp.get("view_center")}, '
                      f'height={vp.get("view_height")}')

    print('\n[Modelspace X 클러스터링]')
    cluster = cluster_modelspace_x(doc, bin_width=50_000.0)
    print(f'  X 범위: {cluster.get("x_total_min"):,.0f} ~ '
          f'{cluster.get("x_total_max"):,.0f}')
    print(f'  X 분산: {cluster.get("x_total_span_mm"):,.0f}mm')
    print(f'  시트 추정: {cluster.get("sheet_count_estimated")}개')
    for i, s in enumerate(cluster.get('sheets', []), 1):
        print(f'    시트 {i}: X {s["x_min"]:,.0f} ~ {s["x_max"]:,.0f} '
              f'({s["entity_count"]}건)')

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({'paperspace': psp_info, 'modelspace_cluster': cluster},
                         ensure_ascii=False, indent=2)
    OUT_PATH.write_bytes(payload.encode('utf-8', errors='replace'))
    print(f'\n저장: {OUT_PATH}')


if __name__ == '__main__':
    main()
