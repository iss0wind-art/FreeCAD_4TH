"""
지하주차장 격자 정밀화 진단 스크립트 — G5 게이트 통과 도전
=============================================================

임무: 방부장 명령 (2026-05-06) — 격자 정밀화 진단
목표: B1·B2 PoC에서 G5(격자 unique X·Y ≤ 15) 미통과 원인 채굴 + 정밀화 시도

실행:
    "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/probe_basement_grid_precision.py

산출물:
    output/basement_grid_precision.json
"""
import os, sys, re, json, time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
OUT_JSON = "output/basement_grid_precision.json"

# PoC에서 사용한 도엽 박스 (Defpoints 외부 경계)
SHEETS = {
    'B2': {'sw': (247250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0, 'floor': -2},
    'B1': {'sw': (877250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0, 'floor': -1},
}

# BORD-FORM 실제 콘텐츠 박스 (도면 테두리 내부)
BORD_BOXES = {
    'B2': {'sx': 276859.0, 'sy': -1360302.0, 'w': 585000.0, 'h': 414750.0},
    'B1': {'sx': 906859.0, 'sy': -1360302.0, 'w': 585000.0, 'h': 414750.0},
    'ROOF': {'sx': 1536859.0, 'sy': -1360302.0, 'w': 585000.0, 'h': 414750.0},
}


def iter_all(c, d=0, m=8):
    """DXF 엔티티 재귀 펼치기 (INSERT 포함)."""
    if d > m:
        return
    for e in c:
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_all(list(e.virtual_entities()), d + 1, m)
            except Exception:
                pass
        else:
            yield e


def collect_all_grid_labels(msp):
    """전체 모델스페이스에서 X*/Y* 패턴 텍스트 수집."""
    grid_pat = re.compile(r'^([XY])(\d{1,2}[A-Z]?)$')
    hits = []
    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            txt = (txt or '').strip()
            if not txt:
                continue
            m = grid_pat.match(txt)
            if not m:
                continue
            try:
                pos = e.dxf.insert
                px, py = pos.x, pos.y
            except Exception:
                continue
            try:
                h = e.dxf.height if e.dxftype() == 'TEXT' else e.dxf.char_height
            except Exception:
                h = 0
            ly = e.dxf.layer
            hits.append({
                'label': txt,
                'axis': m.group(1),
                'num': m.group(2),
                'x': px,
                'y': py,
                'height': h,
                'layer': ly,
            })
        except Exception:
            pass
    return hits


def analyze_label_distribution(all_labels):
    """라벨 분포 전체 분석 (레이어, 높이, 위치 범위)."""
    layer_cnt = Counter(r['layer'] for r in all_labels)
    height_cnt = Counter(round(r['height'], -1) for r in all_labels)
    xs = [r['x'] for r in all_labels]
    ys = [r['y'] for r in all_labels]
    return {
        'total': len(all_labels),
        'layer_distribution': dict(layer_cnt.most_common()),
        'height_distribution': {str(k): v for k, v in sorted(height_cnt.items())},
        'x_range': [min(xs), max(xs)],
        'y_range': [min(ys), max(ys)],
    }


def assign_to_sheet(label_rec, sheets):
    """라벨 좌표 → 도엽 매핑 (외부 박스 기준)."""
    px, py = label_rec['x'], label_rec['y']
    for sid, s in sheets.items():
        sx, sy = s['sw']
        if sx <= px <= sx + s['w'] and sy <= py <= sy + s['h']:
            return sid
    return '??'


def analyze_label_positions_per_sheet(all_labels, sheets):
    """도엽별 X/Y 라벨 위치 클러스터 분석."""
    results = {}
    for sid, s in sheets.items():
        sx, sy = s['sw']
        w, h = s['w'], s['h']

        # 도엽 내 라벨
        sheet_labels = [r for r in all_labels if sx <= r['x'] <= sx + w and sy <= r['y'] <= sy + h]

        x_labels = [r for r in sheet_labels if r['axis'] == 'X']
        y_labels = [r for r in sheet_labels if r['axis'] == 'Y']

        # X 라벨 — Y 좌표 클러스터 (같은 Y = 같은 행에 배치)
        x_y_clusters = Counter(round(r['y'], -3) for r in x_labels)

        # Y 라벨 — X 좌표 클러스터 (같은 X = 같은 열에 배치)
        y_x_clusters = Counter(round(r['x'], -3) for r in y_labels)

        # 유니크 라벨 번호
        unique_x = sorted(set(r['num'] for r in x_labels), key=lambda s: (len(s), s))
        unique_y = sorted(set(r['num'] for r in y_labels), key=lambda s: (len(s), s))

        # X 라벨 좌표 (도엽 기준)
        x_positions = {}
        for r in x_labels:
            num = r['num']
            rel_x = r['x'] - sx
            x_positions.setdefault(num, []).append(round(rel_x, 0))

        # Y 라벨 좌표 (도엽 기준)
        y_positions = {}
        for r in y_labels:
            num = r['num']
            rel_y = r['y'] - sy
            y_positions.setdefault(num, []).append(round(rel_y, 0))

        results[sid] = {
            'total_labels': len(sheet_labels),
            'unique_x': len(unique_x),
            'unique_y': len(unique_y),
            'x_labels': unique_x,
            'y_labels': unique_y,
            'x_y_position_clusters': {str(k): v for k, v in x_y_clusters.most_common()},
            'y_x_position_clusters': {str(k): v for k, v in y_x_clusters.most_common()},
            'x_positions_rel': {k: sorted(set(v)) for k, v in x_positions.items()},
            'y_positions_rel': {k: sorted(set(v)) for k, v in y_positions.items()},
        }
    return results


def analyze_grid_spacing(all_labels, sheets):
    """도엽별 격자 간격 분석 — 구역 경계 후보 탐지."""
    results = {}
    for sid, s in sheets.items():
        sx, sy = s['sw']
        w, h = s['w'], s['h']

        # 가장자리에 있는 X 라벨 (Y 좌표가 도엽 하단 10% 이내)
        bottom_y_thresh = sy + h * 0.15
        x_bottom = [r for r in all_labels
                    if r['axis'] == 'X' and sx <= r['x'] <= sx + w and sy <= r['y'] <= bottom_y_thresh]
        x_bottom.sort(key=lambda r: r['x'])

        # 가장자리에 있는 Y 라벨 (X 좌표 클러스터별)
        y_in_sheet = [r for r in all_labels
                      if r['axis'] == 'Y' and sx <= r['x'] <= sx + w and sy <= r['y'] <= sy + h]

        # X 클러스터 그룹화
        y_x_groups = defaultdict(list)
        for r in y_in_sheet:
            xc = round(r['x'], -4)  # 10m 단위 반올림
            y_x_groups[xc].append(r)

        # X 간격 분석
        x_gaps = []
        for i in range(1, len(x_bottom)):
            gap = x_bottom[i]['x'] - x_bottom[i - 1]['x']
            x_gaps.append({
                'from': x_bottom[i - 1]['num'],
                'to': x_bottom[i]['num'],
                'gap_mm': round(gap, 0),
            })

        # Y 간격 분석 (우측 클러스터 기준)
        rightmost_xc = max(y_x_groups.keys()) if y_x_groups else None
        y_gaps = []
        if rightmost_xc:
            right_labels = sorted(y_x_groups[rightmost_xc], key=lambda r: r['y'])
            for i in range(1, len(right_labels)):
                gap = right_labels[i]['y'] - right_labels[i - 1]['y']
                y_gaps.append({
                    'from': right_labels[i - 1]['num'],
                    'to': right_labels[i]['num'],
                    'gap_mm': round(gap, 0),
                })

        # 큰 갭 = 구역 경계 후보
        big_x_gaps = [g for g in x_gaps if g['gap_mm'] > 12000]
        big_y_gaps = [g for g in y_gaps if abs(g['gap_mm']) > 12000]

        results[sid] = {
            'x_gaps': x_gaps,
            'y_gaps': y_gaps,
            'big_x_gaps': big_x_gaps,
            'big_y_gaps': big_y_gaps,
        }
    return results


def subgrid_split(all_labels, sheets):
    """Sub-grid 분할 시도 — Y축 큰 갭 기반."""
    results = {}
    for sid, s in sheets.items():
        sx, sy = s['sw']
        w, h = s['w'], s['h']

        y_labels = [r for r in all_labels
                    if r['axis'] == 'Y' and sx <= r['x'] <= sx + w and sy <= r['y'] <= sy + h]
        x_labels = [r for r in all_labels
                    if r['axis'] == 'X' and sx <= r['x'] <= sx + w and sy <= r['y'] <= sy + h]

        # Y 좌표 기준 중간 갭 찾기
        y_nums_by_coord = sorted(set((r['y'], r['num']) for r in y_labels))
        y_gaps = []
        for i in range(1, len(y_nums_by_coord)):
            gap = y_nums_by_coord[i][0] - y_nums_by_coord[i - 1][0]
            y_gaps.append((abs(gap), y_nums_by_coord[i - 1][1], y_nums_by_coord[i][1],
                           y_nums_by_coord[i - 1][0], y_nums_by_coord[i][0]))

        # 가장 큰 갭 기반 분할
        y_gaps.sort(reverse=True)
        split_candidates = [g for g in y_gaps if g[0] > 20000]

        subgrids = []
        unique_x_nums = sorted(set(r['num'] for r in x_labels), key=lambda s: (len(s), s))

        if split_candidates:
            # 분할 경계
            _, from_lbl, to_lbl, y_split_from, y_split_to = split_candidates[0]
            y_thresh = (y_split_from + y_split_to) / 2

            y_part_a = [r for r in y_labels if r['y'] <= y_thresh]
            y_part_b = [r for r in y_labels if r['y'] > y_thresh]

            nums_a = sorted(set(r['num'] for r in y_part_a), key=lambda s: (len(s), s))
            nums_b = sorted(set(r['num'] for r in y_part_b), key=lambda s: (len(s), s))

            subgrids.append({
                'region': f'{sid}_YA',
                'y_range': f'Y1~{from_lbl}',
                'unique_x': len(unique_x_nums),
                'unique_y': len(nums_a),
                'x_labels': unique_x_nums,
                'y_labels': nums_a,
                'g5_pass': max(len(unique_x_nums), len(nums_a)) <= 15,
            })
            subgrids.append({
                'region': f'{sid}_YB',
                'y_range': f'{to_lbl}~end',
                'unique_x': len(unique_x_nums),
                'unique_y': len(nums_b),
                'x_labels': unique_x_nums,
                'y_labels': nums_b,
                'g5_pass': max(len(unique_x_nums), len(nums_b)) <= 15,
            })
        else:
            subgrids.append({
                'region': sid,
                'y_range': 'all',
                'unique_x': len(unique_x_nums),
                'unique_y': len(set(r['num'] for r in y_labels)),
                'x_labels': unique_x_nums,
                'y_labels': sorted(set(r['num'] for r in y_labels)),
                'g5_pass': False,
            })

        results[sid] = {
            'subgrids': subgrids,
            'largest_y_gap': y_gaps[0] if y_gaps else None,
        }
    return results


def check_noise_labels(all_labels, sheets):
    """잡음 라벨 검출 — 격자선 가장자리가 아닌 위치의 라벨."""
    noise_candidates = []
    for r in all_labels:
        px, py = r['x'], r['y']
        in_any_sheet = False
        edge_label = False

        for sid, s in sheets.items():
            sx, sy = s['sw']
            w, h = s['w'], s['h']
            if not (sx <= px <= sx + w and sy <= py <= sy + h):
                continue
            in_any_sheet = True

            # 가장자리 기준: 도엽 상하단 15%, 좌우단 15% 이내
            if r['axis'] == 'X':
                # X라벨은 도엽 하단 가장자리에 있어야
                if py <= sy + h * 0.15 or py >= sy + h * 0.85:
                    edge_label = True
            elif r['axis'] == 'Y':
                # Y라벨은 도엽 좌우 가장자리에 있어야
                if px <= sx + w * 0.20 or px >= sx + w * 0.75:
                    edge_label = True

        if in_any_sheet and not edge_label:
            noise_candidates.append({
                'label': r['label'],
                'x': round(r['x'], 0),
                'y': round(r['y'], 0),
                'layer': r['layer'],
                'reason': '격자선 가장자리 아닌 위치',
            })

    return noise_candidates


def main():
    t0 = time.time()
    print(f'[입력] {DXF}')
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    print(f'[로드] {time.time()-t0:.1f}s')

    # 1단계: 전체 X*/Y* 라벨 수집
    print('\n[1단계] X*/Y* 라벨 전체 수집')
    all_labels = collect_all_grid_labels(msp)
    print(f'  총 {len(all_labels)}건')

    # 2단계: 분포 분석
    print('\n[2단계] 분포 분석')
    dist = analyze_label_distribution(all_labels)
    print(f'  레이어 분포: {dict(list(dist["layer_distribution"].items())[:5])}')
    print(f'  높이 분포: {dist["height_distribution"]}')
    print(f'  X 범위: {dist["x_range"][0]:.0f} ~ {dist["x_range"][1]:.0f}')
    print(f'  Y 범위: {dist["y_range"][0]:.0f} ~ {dist["y_range"][1]:.0f}')

    # 3단계: 도엽별 위치 분석
    print('\n[3단계] 도엽별 라벨 위치 분석')
    per_sheet = analyze_label_positions_per_sheet(all_labels, SHEETS)
    for sid, r in per_sheet.items():
        print(f'  [{sid}] unique X={r["unique_x"]}  Y={r["unique_y"]}')
        print(f'    X라벨: {r["x_labels"]}')
        print(f'    Y라벨: {r["y_labels"]}')

    # 4단계: 잡음 라벨 검출
    print('\n[4단계] 잡음 라벨 검출 (격자 가장자리 아닌 위치)')
    noise = check_noise_labels(all_labels, SHEETS)
    print(f'  잡음 후보: {len(noise)}건')
    for n in noise[:10]:
        print(f'    {n["label"]} ({n["x"]:.0f}, {n["y"]:.0f}) — {n["reason"]}')

    # 5단계: 격자 간격 분석
    print('\n[5단계] 격자 간격 분석 — 구역 경계 탐지')
    spacing = analyze_grid_spacing(all_labels, SHEETS)
    for sid, r in spacing.items():
        print(f'  [{sid}]')
        if r['big_x_gaps']:
            print(f'    X 큰 갭(>12m): {r["big_x_gaps"]}')
        if r['big_y_gaps']:
            print(f'    Y 큰 갭(>12m): {r["big_y_gaps"]}')
        else:
            print(f'    Y 큰 갭: 없음 (단일 구역)')

    # 6단계: Sub-grid 분할 시도
    print('\n[6단계] Sub-grid 분할 시도')
    subgrid = subgrid_split(all_labels, SHEETS)
    for sid, r in subgrid.items():
        print(f'  [{sid}] 최대 Y 갭: {r["largest_y_gap"]}')
        for sg in r['subgrids']:
            g5 = '통과' if sg['g5_pass'] else '미통과'
            print(f'    구역 {sg["region"]} ({sg["y_range"]}): X={sg["unique_x"]}, Y={sg["unique_y"]} → G5 {g5}')

    # 7단계: G5 통과 가능성 최종 판단
    print('\n[7단계] G5 통과 가능성 최종 판단')
    g5_any_pass = False
    for sid, r in subgrid.items():
        for sg in r['subgrids']:
            if sg['g5_pass']:
                g5_any_pass = True
                print(f'  ✅ {sg["region"]}: G5 통과 가능 (X={sg["unique_x"]}, Y={sg["unique_y"]})')
    if not g5_any_pass:
        print('  ❌ 어떤 분할로도 G5(≤15) 통과 불가')
        print('  → 정직 박제 근거:')
        for sid, ps in per_sheet.items():
            print(f'    [{sid}] X={ps["unique_x"]}, Y={ps["unique_y"]} — 단지 통합 격자 체계')

    # 결과 박제
    elapsed = round(time.time() - t0, 1)
    result = {
        'purpose': '격자 정밀화 진단 — G5(unique X·Y ≤ 15) 통과 가능성',
        'timestamp': '2026-05-06',
        'elapsed_s': elapsed,
        'label_distribution': dist,
        'per_sheet_analysis': per_sheet,
        'noise_labels': noise,
        'grid_spacing': {sid: {
            'big_x_gaps': r['big_x_gaps'],
            'big_y_gaps': r['big_y_gaps'],
        } for sid, r in spacing.items()},
        'subgrid_split': {sid: {
            'largest_y_gap_mm': r['largest_y_gap'][0] if r['largest_y_gap'] else None,
            'split_point': f'{r["largest_y_gap"][1]}~{r["largest_y_gap"][2]}' if r['largest_y_gap'] else None,
            'subgrids': r['subgrids'],
        } for sid, r in subgrid.items()},
        'g5_verdict': {
            'can_pass': g5_any_pass,
            'verdict': 'PASS' if g5_any_pass else 'FAIL_HONEST_ARCHIVE',
            'reason': '단지 통합 지하주차장 도면 — 격자 29×34 (단순하지 않음)',
            'detail': {
                sid: {'unique_x': ps['unique_x'], 'unique_y': ps['unique_y']}
                for sid, ps in per_sheet.items()
            },
        },
    }

    os.makedirs('output', exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'\n[박제] {OUT_JSON}')
    print(f'[종결] {elapsed}s')


if __name__ == '__main__':
    main()
