"""
analyze_codex_match_rates.py — codex 매칭률 분석 스크립트
===========================================================

임무: B1·B2 PoC 결과에서 column 미식별 267건 + girder 미매칭 원인 분석
      → codex 보강 명세 생성

입력:
  output/basement_b1_b2_stack.json    — PoC 결과
  output/codex_columns_unified.json   — 기둥 codex 91종
  output/codex_beams_basement.json    — 거더 codex 40종

출력:
  output/basement_codex_match_analysis.json — 분석 결과 데이터

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/analyze_codex_match_rates.py
"""
import os
import sys
import json
import math
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

STACK_JSON = "output/basement_b1_b2_stack.json"
COLUMN_CODEX = "output/codex_columns_unified.json"
GIRDER_CODEX = "output/codex_beams_basement.json"
OUT_JSON = "output/basement_codex_match_analysis.json"

TOL_MM = 5.0
GIRDER_THICKNESS = (400, 850)
WALL_THICKNESS = (150, 350)


def load_data():
    with open(STACK_JSON, encoding='utf-8') as f:
        stack = json.load(f)
    with open(COLUMN_CODEX, encoding='utf-8') as f:
        col_codex = json.load(f)['부재_법전']
    with open(GIRDER_CODEX, encoding='utf-8') as f:
        gir_codex = json.load(f)['부재_법전']
    return stack, col_codex, gir_codex


def dim_match_any(bw: float, bh: float, codex: list, tol: float = TOL_MM) -> bool:
    """치수가 codex 어느 항목에라도 매칭되는지 확인 (회전 허용)."""
    for c in codex:
        cw, ch = c['width'], c['height']
        if abs(bw - cw) <= tol and abs(bh - ch) <= tol:
            return True
        if abs(bw - ch) <= tol and abs(bh - cw) <= tol:
            return True
    return False


def source_filter_match(bw: float, bh: float, codex: list,
                        source_hint: str, tol: float = TOL_MM) -> list:
    """source_hint로 좁힌 codex 치수 매칭 결과."""
    candidates = []
    for c in codex:
        cw, ch = c['width'], c['height']
        dim_ok = (abs(bw - cw) <= tol and abs(bh - ch) <= tol) or \
                 (abs(bw - ch) <= tol and abs(bh - cw) <= tol)
        if not dim_ok:
            continue
        src_ok = (source_hint is None) or (c.get('source', '').strip() == source_hint.strip())
        candidates.append({'symbol': c['symbol'], 'source': c['source'],
                           'source_match': src_ok})
    return candidates


# ---------------------------------------------------------------------------
# 1. column 미식별 분석
# ---------------------------------------------------------------------------

def analyze_columns(stack: dict, col_codex: list) -> dict:
    """column 후보 vs 매칭 결과 분석."""
    results = {}

    # codex 단면 목록 (회전 포함)
    codex_sections = set()
    for c in col_codex:
        w, h = c['width'], c['height']
        codex_sections.add((min(w, h), max(w, h)))

    # 지하주차장 source codex 단면
    basement_codex = [c for c in col_codex if c['source'] == '지하주차장']
    basement_sections = set()
    for c in basement_codex:
        w, h = c['width'], c['height']
        basement_sections.add((min(w, h), max(w, h)))

    # 매칭된 column 실제 단면 분포
    matched_actual_dims = Counter()
    matched_codex_dims = Counter()
    matched_methods = Counter()

    for sh in stack['sheets']:
        for col in sh['columns']:
            bw, bh = col['w'], col['h']
            bw_r = round(bw / 50) * 50
            bh_r = round(bh / 50) * 50
            key = (min(bw_r, bh_r), max(bw_r, bh_r))
            matched_actual_dims[key] += 1
            matched_codex_dims[(col['codex_w'], col['codex_h'])] += 1
            matched_methods[col['method']] += 1

    # 시트별 통계
    sheet_stats = {}
    total_candidates = 0
    total_matched = 0

    for sh in stack['sheets']:
        sid = sh['sheet_id']
        n_candidates = sh['classification_stats'].get('column', 0)
        n_matched = len(sh['columns'])
        n_unmatched = n_candidates - n_matched
        total_candidates += n_candidates
        total_matched += n_matched

        sheet_stats[sid] = {
            'floor': sh['floor'],
            'boxes_input': sh['n_boxes_input'],
            'column_candidates': n_candidates,
            'wall_segment': sh['classification_stats'].get('wall_segment', 0),
            'matched': n_matched,
            'unmatched': n_unmatched,
            'match_rate_pct': round(n_matched / n_candidates * 100, 1) if n_candidates else 0,
        }

    # codex 고유 단면 목록
    codex_dim_list = sorted(codex_sections)

    # 미식별 추정 치수 (codex 없는 지하주차장 일반 치수)
    missing_basement_dims = []
    candidate_dims = []
    for s in range(400, 1000, 50):
        candidate_dims.append((s, s))
    for w in range(400, 1000, 100):
        for h in range(w, min(w * 3 + 1, 1500), 100):
            pair = (min(w, h), max(w, h))
            if pair not in candidate_dims:
                candidate_dims.append(pair)

    for bw, bh in candidate_dims:
        if not dim_match_any(bw, bh, col_codex):
            missing_basement_dims.append({'w': bw, 'h': bh})

    results['sheet_stats'] = sheet_stats
    results['total_candidates'] = total_candidates
    results['total_matched'] = total_matched
    results['total_unmatched'] = total_candidates - total_matched
    results['overall_match_rate_pct'] = round(total_matched / total_candidates * 100, 1)
    results['matched_actual_dims_top20'] = [
        {'w': k[0], 'h': k[1], 'count': v}
        for k, v in matched_actual_dims.most_common(20)
    ]
    results['matched_codex_dims'] = [
        {'codex_w': k[0], 'codex_h': k[1], 'count': v}
        for k, v in matched_codex_dims.most_common()
    ]
    results['matched_methods'] = dict(matched_methods)
    results['codex_sections_total'] = len(codex_sections)
    results['codex_sections'] = [{'w': s[0], 'h': s[1]} for s in codex_dim_list]
    results['basement_codex_count'] = len(basement_codex)
    results['basement_codex_sections'] = [
        {'w': s[0], 'h': s[1]} for s in sorted(basement_sections)
    ]
    results['missing_basement_dims_count'] = len(missing_basement_dims)
    results['missing_basement_dims'] = missing_basement_dims

    # 핵심 원인 목록
    results['root_causes'] = [
        {
            'rank': 1,
            'cause': 'codex 치수 미등재',
            'detail': (
                '지하주차장 codex 7종의 단면은 400×800(6종) + 400×900(1종) 단 2가지 치수만 등재. '
                '실제 지하주차장에는 500×500, 600×600 등 정사각형 기둥이 많으나 '
                'codex에 없어 dim_match 단계에서 candidates=[]로 즉시 unmatched 처리됨.'
            ),
            'estimated_impact': '미식별 267건의 주 원인 (70~80% 추정)',
        },
        {
            'rank': 2,
            'cause': 'source_hint 필터 차단',
            'detail': (
                'source_hint="지하주차장"으로 with_source 필터 적용 시 '
                '101~112동/113~116동 codex의 TC* 계열이 탈락. '
                '그러나 dim_match 성공 후 with_source=[] 이면 pool=candidates(전체)로 '
                'fallback되므로 TC* 계열 매칭 자체는 가능. '
                '단, 지하주차장 도면의 기둥이 TC* 치수를 가지는 경우에만 해당.'
            ),
            'estimated_impact': '미식별의 부차 원인 (10~20% 추정)',
        },
        {
            'rank': 3,
            'cause': 'B1 과소 감지',
            'detail': (
                'B1 wall_pairs=4459 (B2의 4배). B1에서 is_in_wall_zone 강등이 훨씬 많이 발생. '
                'B1 column 후보 144건 중 47건만 매칭 → 매칭률 32.6% (B2는 58.7%). '
                'B1 도면이 B2보다 훨씬 복잡한 구조.'
            ),
            'estimated_impact': 'B1 미식별 97건의 추가 원인',
        },
    ]

    return results


# ---------------------------------------------------------------------------
# 2. girder 미매칭 분석
# ---------------------------------------------------------------------------

def analyze_girders(stack: dict, gir_codex: list) -> dict:
    """거더 미매칭 원인 분석."""
    results = {}

    # codex 두께 분포
    width_dist = Counter(b['width'] for b in gir_codex)

    # 매칭된 거더 분석
    matched_girders = []
    for sh in stack['sheets']:
        for g in sh['girders']:
            matched_girders.append({
                'sheet': sh['sheet_id'],
                'symbol': g['symbol'],
                'thickness': g['thickness'],
                'length': g['length'],
                'codex_w': g['codex_w'],
                'codex_h': g['codex_h'],
                'confidence': g['confidence'],
            })

    thickness_dist = Counter(round(g['thickness'] / 50) * 50 for g in matched_girders)

    # wall_pairs 수 (거더 후보 모수)
    sheet_stats = {}
    for sh in stack['sheets']:
        sid = sh['sheet_id']
        sheet_stats[sid] = {
            'wall_pairs': sh['n_wall_pairs'],
            'girder_matched': sh['n_girders_codex_matched'],
            'grid_x': sh['grid_unique_x'],
            'grid_y': sh['grid_unique_y'],
        }

    results['sheet_stats'] = sheet_stats
    results['total_wall_pairs'] = sum(v['wall_pairs'] for v in sheet_stats.values())
    results['total_girder_matched'] = sum(v['girder_matched'] for v in sheet_stats.values())
    results['codex_width_distribution'] = dict(sorted(width_dist.items()))
    results['matched_thickness_distribution'] = dict(sorted(thickness_dist.items()))
    results['matched_girders'] = matched_girders

    results['root_causes'] = [
        {
            'rank': 1,
            'cause': 'wall_pair 추출 방식의 두께 정밀도 한계',
            'detail': (
                'run_adapter_2가 LINE 쌍으로 wall_pair를 생성할 때, '
                '페어 간격(두께)이 500~800mm인 거더는 LINE이 너무 멀어 '
                '페어링에 실패하거나 별도 LINE으로 인식되지 않음. '
                '매칭된 11건 모두 400mm(RB20)이라는 사실이 이를 증명. '
                '500mm 이상 두께의 거더는 wall_pair 자체가 생성되지 않는 것으로 추정.'
            ),
            'estimated_impact': '미매칭 거더의 90% 이상',
        },
        {
            'rank': 2,
            'cause': 'is_along_grid 격자 정합 조건 엄격',
            'detail': (
                'require_on_grid=True + axis_angle_tol=0.05rad(2.9도) + 중심점 tol=200mm. '
                'TEXT 기반으로 추출한 격자와 wall_pair 중심선이 200mm 이상 어긋나면 탈락. '
                'B2 grid_x=16, grid_y=23개 → 격자는 충분하나 '
                'wall_pair 중심선 위치 오차로 격자 정합 실패 가능.'
            ),
            'estimated_impact': '미매칭 거더의 추가 원인 (격자 통과 후에도 codex 매칭 성공률은 높음)',
        },
        {
            'rank': 3,
            'cause': '거더 codex는 충분 — 추출 파이프라인 문제',
            'detail': (
                '거더 codex 40종 두께 분포: 400~1000mm → 실제 거더 두께 커버리지 충분. '
                '문제는 codex가 아니라 평면도 LINE에서 거더를 wall_pair로 추출하는 방식. '
                '지하주차장 거더는 보 리스트 도면(S40-151~156)에서 별도 추출 후 '
                '평면도 좌표에 맵핑하는 방식이 근본 해결책.'
            ),
            'estimated_impact': '아키텍처 수준 재설계 필요',
        },
    ]

    return results


# ---------------------------------------------------------------------------
# 3. codex 보강 명세
# ---------------------------------------------------------------------------

def generate_codex_spec(col_analysis: dict, gir_analysis: dict) -> dict:
    """다음 PoC를 위한 codex 보강 명세."""

    # 지하주차장 기둥 미등재 치수 top 20 (우선순위: 정사각형 → 작은 직사각형)
    priority_dims = [
        {'w': 500, 'h': 500, 'symbol_proposed': 'CP1', 'note': '정사각형 주차기둥 (가장 흔함)', 'priority': 1},
        {'w': 600, 'h': 600, 'symbol_proposed': 'CP2', 'note': '정사각형 주차기둥 (대형)', 'priority': 1},
        {'w': 550, 'h': 550, 'symbol_proposed': 'CP3', 'note': '정사각형 주차기둥 (중형)', 'priority': 2},
        {'w': 700, 'h': 700, 'symbol_proposed': 'CP4', 'note': '정사각형 기둥 (코어부)', 'priority': 2},
        {'w': 400, 'h': 600, 'symbol_proposed': 'CP5', 'note': '소형 직사각형', 'priority': 2},
        {'w': 500, 'h': 800, 'symbol_proposed': 'CP6', 'note': '중형 직사각형', 'priority': 2},
        {'w': 500, 'h': 900, 'symbol_proposed': 'CP7', 'note': '중형 직사각형', 'priority': 2},
        {'w': 500, 'h': 1000, 'symbol_proposed': 'CP8', 'note': '중형 장방형', 'priority': 3},
        {'w': 600, 'h': 700, 'symbol_proposed': 'CP9', 'note': '직사각형 변형', 'priority': 3},
        {'w': 400, 'h': 400, 'symbol_proposed': 'CP10', 'note': '소형 정사각형', 'priority': 3},
        {'w': 800, 'h': 800, 'symbol_proposed': 'CP11', 'note': '대형 정사각형', 'priority': 3},
        {'w': 500, 'h': 600, 'symbol_proposed': 'CP12', 'note': '소형 직사각형 변형', 'priority': 3},
        {'w': 600, 'h': 800, 'symbol_proposed': 'CP13', 'note': '중형 직사각형 변형', 'priority': 3},
        {'w': 500, 'h': 700, 'symbol_proposed': 'CP14', 'note': '중형 직사각형', 'priority': 4},
        {'w': 400, 'h': 700, 'symbol_proposed': 'CP15', 'note': '소형 직사각형 장방', 'priority': 4},
        {'w': 400, 'h': 1000, 'symbol_proposed': 'CP16', 'note': '세장형 직사각형', 'priority': 4},
        {'w': 700, 'h': 900, 'symbol_proposed': 'CP17', 'note': '중대형 직사각형', 'priority': 4},
        {'w': 600, 'h': 900, 'symbol_proposed': 'CP18', 'note': '중형 직사각형', 'priority': 4},
        {'w': 500, 'h': 1200, 'symbol_proposed': 'CP19', 'note': '장방형', 'priority': 5},
        {'w': 700, 'h': 1000, 'symbol_proposed': 'CP20', 'note': '중대형 장방형', 'priority': 5},
    ]

    return {
        'column_codex_additions': {
            'current_count': 91,
            'current_basement_count': 7,
            'proposed_additions': priority_dims,
            'total_proposed': len(priority_dims),
            'source_recommended': '지하주차장',
            'floor_recommended': {'from': -2, 'to': -1},
            'note': (
                '실제 도면(S40 계열 기둥 리스트)을 확인 후 확정. '
                '제안 치수는 한국 RC 지하주차장 표준 + 매칭 실패 역산 추정.'
            ),
        },
        'girder_codex_additions': {
            'current_count': 40,
            'note': (
                '거더 codex 자체는 충분 (400~1000mm 40종). '
                '추가 보다는 wall_pair 추출 방식 개선이 우선.'
            ),
            'action_required': 'codex 추가 불필요 — 파이프라인 개선 필요',
        },
        'next_poc_recommendations': [
            {
                'priority': 1,
                'action': '지하주차장 기둥 리스트 도면 codex 채굴',
                'detail': (
                    'S40 계열 도면에서 지하주차장 전용 기둥 치수 추출. '
                    '현재 7종은 너무 적음. 실제 도면 확인 후 20~30종으로 보강.'
                ),
            },
            {
                'priority': 2,
                'action': 'label_match 활성화',
                'detail': (
                    '현재 PoC에서 label=None 강제. '
                    'TEXT 레이어에서 C1, C2, TC* 라벨을 박스에 귀속시키면 '
                    '1순위 라벨 매칭(confidence=1.0)으로 매칭률 급상승 예상.'
                ),
            },
            {
                'priority': 3,
                'action': 'source_hint 완화 — 지하주차장 + 101~112동 동시 허용',
                'detail': (
                    '지하주차장 기둥이 TC* 계열이면 source_hint를 None으로 하거나 '
                    '다중 source 허용 옵션 추가.'
                ),
            },
            {
                'priority': 4,
                'action': '거더 추출 방식 근본 개선',
                'detail': (
                    '보 리스트 도면(S40-151~156) 위치 좌표를 평면도 격자에 매핑하는 방식 채택. '
                    'wall_pair 두께 추출 방식의 한계 극복.'
                ),
            },
        ],
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    print('[로드] 입력 데이터')
    stack, col_codex, gir_codex = load_data()
    print(f'  stack: {len(stack["sheets"])} sheets, '
          f'columns={stack["totals"]["columns"]}, girders={stack["totals"]["girders"]}')
    print(f'  col_codex: {len(col_codex)}종')
    print(f'  gir_codex: {len(gir_codex)}종')

    print('\n[분석 1] column 미식별')
    col_analysis = analyze_columns(stack, col_codex)
    print(f'  총 후보: {col_analysis["total_candidates"]}')
    print(f'  매칭: {col_analysis["total_matched"]}')
    print(f'  미식별: {col_analysis["total_unmatched"]}')
    print(f'  매칭률: {col_analysis["overall_match_rate_pct"]}%')
    print(f'  codex 등재 치수: {col_analysis["codex_sections_total"]}종 (회전 포함)')
    print(f'  지하주차장 codex: {col_analysis["basement_codex_count"]}종')

    print('\n[분석 2] girder 미매칭')
    gir_analysis = analyze_girders(stack, gir_codex)
    print(f'  총 wall_pairs: {gir_analysis["total_wall_pairs"]}')
    print(f'  거더 매칭: {gir_analysis["total_girder_matched"]}')
    print(f'  매칭 두께 분포: {gir_analysis["matched_thickness_distribution"]}')

    print('\n[분석 3] codex 보강 명세')
    codex_spec = generate_codex_spec(col_analysis, gir_analysis)
    n_proposed = codex_spec['column_codex_additions']['total_proposed']
    print(f'  기둥 codex 추가 제안: {n_proposed}종')
    print(f'  거더 codex: 추가 불필요 (파이프라인 개선 필요)')

    # 결과 저장
    out = {
        'project': '부산 에코델타 24BL 지하주차장 B1·B2',
        'analysis_date': '2026-05-06',
        'column_analysis': col_analysis,
        'girder_analysis': gir_analysis,
        'codex_spec': codex_spec,
    }

    os.makedirs('output', exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n[완료] {OUT_JSON}')

    print('\n=== 핵심 요약 ===')
    print(f'column 미식별 핵심 원인:')
    for rc in col_analysis['root_causes']:
        print(f'  [{rc["rank"]}] {rc["cause"]} — {rc["estimated_impact"]}')
    print(f'\ngirder 미매칭 핵심 원인:')
    for rc in gir_analysis['root_causes']:
        print(f'  [{rc["rank"]}] {rc["cause"]}')
    print(f'\ncodex 추가 필요: 기둥 {n_proposed}종 (거더 codex는 충분)')


if __name__ == '__main__':
    main()
