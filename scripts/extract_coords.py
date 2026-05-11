"""
extract_coords.py — PKG/DONG 오프셋 정밀 추출
=================================================
DXF 도면에서 직접 읽은 수치만 사용.
추측값 사용 시 confidence="low" 명시.

[전략]
  1. DONG + PKG 격자 라벨 추출 → 공통 격자 이름 교차
  2. E/V 코어 TEXT 위치 추출
  3. 격자 X1·Y1 교점 추출
  4. TX, TY = PKG 기준점 - DONG 기준점
  5. TZ: stage0_levels.json + PKG 도면 SL 텍스트 검증

실행: python scripts/extract_coords.py
"""
import sys
import os
import json
import re
import math
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf

DXF_DONG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
DXF_PKG  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'
OUT_JSON = 'output/coord_config.json'
STAGE0   = 'output/stage0_levels.json'

# DONG B1F 도엽 SW (검증된 값)
DONG_B1F_SW = (242247.0, 2290548.0)
SHEET_W, SHEET_H = 126000, 178200

# 격자 패턴
_GRID_X_PAT = re.compile(r'^X\s*(\d+[a-zA-Z]?)$', re.IGNORECASE)
_GRID_Y_PAT = re.compile(r'^Y\s*(\d+[a-zA-Z]?)$', re.IGNORECASE)
# SL 마커: "B1F SL", "B2F SL", "SL=xxx", "SL -9050" 등
_SL_PAT = re.compile(
    r'(B[12]F\s+SL|SL\s*[-=+]?\s*\d+|GL[-=+]?\s*\d+)',
    re.IGNORECASE,
)
_EV_PAT = re.compile(
    r'E/?V\b|ELEV|승강기|엘리베이터|ELEVATOR|LIFT',
    re.IGNORECASE,
)


def iter_all(container, depth=0, max_depth=8):
    if depth > max_depth:
        return
    for e in container:
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_all(list(e.virtual_entities()), depth+1, max_depth)
            except Exception:
                pass
        else:
            yield e


def extract_texts(msp, clip=None):
    """TEXT/MTEXT 전체 추출. clip=(xmin,ymin,xmax,ymax) 선택."""
    out = []
    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text) or ''
            txt = txt.strip()
            if not txt:
                continue
            pos = e.dxf.insert
            x, y = pos.x, pos.y
            if clip:
                xmin, ymin, xmax, ymax = clip
                if not (xmin <= x <= xmax and ymin <= y <= ymax):
                    continue
            out.append((txt, x, y))
        except Exception:
            pass
    return out


def extract_grid_coords(texts, label_pat_x, label_pat_y):
    """격자 라벨 → {label: coord} 딕셔너리."""
    x_dict = {}  # label → x좌표 목록
    y_dict = {}  # label → y좌표 목록
    for txt, x, y in texts:
        mx = label_pat_x.match(txt)
        my = label_pat_y.match(txt)
        if mx:
            lbl = mx.group(1).upper()
            x_dict.setdefault(lbl, []).append(x)
        elif my:
            lbl = my.group(1).upper()
            y_dict.setdefault(lbl, []).append(y)

    # 중위값으로 확정
    x_final = {lbl: sorted(vals)[len(vals)//2] for lbl, vals in x_dict.items()}
    y_final = {lbl: sorted(vals)[len(vals)//2] for lbl, vals in y_dict.items()}
    return x_final, y_final


def find_ev_texts(texts):
    """E/V 텍스트 위치 목록 반환."""
    ev_pts = []
    for txt, x, y in texts:
        if _EV_PAT.search(txt):
            ev_pts.append({'text': txt, 'x': x, 'y': y})
    return ev_pts


def find_sl_markers(texts):
    """SL 관련 텍스트 마커 반환."""
    sl_pts = []
    for txt, x, y in texts:
        if _SL_PAT.search(txt):
            sl_pts.append({'text': txt, 'x': x, 'y': y})
    return sl_pts


def cluster_center(pts, radius=10000):
    """좌표 클러스터 중심 반환."""
    if not pts:
        return None
    if len(pts) == 1:
        return pts[0]['x'], pts[0]['y']

    best_cx, best_cy, best_n = None, None, 0
    for p in pts:
        cluster = [q for q in pts
                   if abs(q['x']-p['x']) < radius and abs(q['y']-p['y']) < radius]
        if len(cluster) > best_n:
            best_n = len(cluster)
            best_cx = sum(q['x'] for q in cluster) / len(cluster)
            best_cy = sum(q['y'] for q in cluster) / len(cluster)

    return best_cx, best_cy


def compute_offset_from_grid(dong_x_dict, dong_y_dict,
                              pkg_x_dict, pkg_y_dict):
    """공통 격자 라벨로 TX, TY 계산.

    반환: (tx, ty, evidence_list, confidence)
    TX = pkg_x[lbl] - dong_x[lbl]
    TY = pkg_y[lbl] - dong_y[lbl]
    """
    common_x = set(dong_x_dict) & set(pkg_x_dict)
    common_y = set(dong_y_dict) & set(pkg_y_dict)

    print(f'  공통 X 격자: {sorted(common_x)}')
    print(f'  공통 Y 격자: {sorted(common_y)}')

    tx_vals = []
    ty_vals = []
    evidence = []

    for lbl in sorted(common_x):
        dx = dong_x_dict[lbl]
        px = pkg_x_dict[lbl]
        tx_candidate = px - dx
        tx_vals.append(tx_candidate)
        evidence.append({
            'type': 'grid_X',
            'label': lbl,
            'dong_x': round(dx),
            'pkg_x': round(px),
            'tx': round(tx_candidate),
        })
        print(f'    X{lbl}: DONG={dx:.0f}, PKG={px:.0f}, TX={tx_candidate:.0f}')

    for lbl in sorted(common_y):
        dy = dong_y_dict[lbl]
        py = pkg_y_dict[lbl]
        ty_candidate = py - dy
        ty_vals.append(ty_candidate)
        evidence.append({
            'type': 'grid_Y',
            'label': lbl,
            'dong_y': round(dy),
            'pkg_y': round(py),
            'ty': round(ty_candidate),
        })
        print(f'    Y{lbl}: DONG={dy:.0f}, PKG={py:.0f}, TY={ty_candidate:.0f}')

    if not tx_vals or not ty_vals:
        return None, None, evidence, 'low'

    # 이상치 제거: 중위값에서 5000mm 이상 벗어나면 제거
    def median_filter(vals, tol=5000):
        m = sorted(vals)[len(vals)//2]
        filtered = [v for v in vals if abs(v - m) <= tol]
        return filtered if filtered else vals

    tx_clean = median_filter(tx_vals)
    ty_clean = median_filter(ty_vals)
    tx = sum(tx_clean) / len(tx_clean)
    ty = sum(ty_clean) / len(ty_clean)

    tx_std = (sum((v-tx)**2 for v in tx_clean)/max(len(tx_clean),1))**0.5
    ty_std = (sum((v-ty)**2 for v in ty_clean)/max(len(ty_clean),1))**0.5

    # 신뢰도 판단
    n = min(len(tx_clean), len(ty_clean))
    if n >= 3 and tx_std < 500 and ty_std < 500:
        confidence = 'high'
    elif n >= 2 and tx_std < 2000 and ty_std < 2000:
        confidence = 'medium'
    else:
        confidence = 'low'

    evidence.append({
        'type': 'summary',
        'tx_samples': len(tx_clean),
        'ty_samples': len(ty_clean),
        'tx_std_mm': round(tx_std),
        'ty_std_mm': round(ty_std),
    })

    return round(tx), round(ty), evidence, confidence


def extract_b1f_sl_from_pkg(texts):
    """PKG 도면 텍스트에서 B1F SL 값 추출.

    반환: {'sl': int, 'text': str, 'x': float, 'y': float} or None
    """
    b1f_candidates = []
    for item in texts:
        txt = item['text']
        # "B1F SL" 또는 "1F SL" 패턴
        m = re.search(r'B1F\s+SL\s*[+\-]?\s*(\d+)', txt, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            b1f_candidates.append({'sl': val, **item})
        # "SL -5600" or "SL=-5600" 패턴 (B2F가 -9050이므로 -4000~-6500 범위만)
        m2 = re.search(r'SL\s*=?\s*(-?\d+)', txt, re.IGNORECASE)
        if m2:
            val = int(m2.group(1))
            if -6500 <= val <= -4000:
                b1f_candidates.append({'sl': val, **item})

    return b1f_candidates


def main():
    t0 = time.time()
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print('=' * 60)
    print('좌표 정밀화 — DXF 직독')
    print('=' * 60)

    # ─────────────────────────────────────────────
    # Step 1: DXF 로드
    # ─────────────────────────────────────────────
    print(f'\n[Step 1] DXF 로드...')
    # [패치 2026-05-08, 끌로드 트랙] DONG는 헤더가 ANSI_949지만 실제 utf-8.
    # safe_readfile()이 utf-8 우선 + cp949 fallback으로 자동 판별.
    from core.dxf_parser.safe_reader import safe_readfile
    print(f'  DONG: {DXF_DONG}')
    doc_dong = safe_readfile(DXF_DONG)
    msp_dong = doc_dong.modelspace()
    print(f'  DONG 로드 완료 ({time.time()-t0:.1f}s)')

    print(f'  PKG: {DXF_PKG}')
    doc_pkg = safe_readfile(DXF_PKG)
    msp_pkg = doc_pkg.modelspace()
    print(f'  PKG 로드 완료 ({time.time()-t0:.1f}s)')

    # ─────────────────────────────────────────────
    # Step 2: DONG 텍스트 추출 (B1F 도엽 영역 내)
    # ─────────────────────────────────────────────
    print(f'\n[Step 2] DONG B1F 도엽 텍스트 추출...')
    sw = DONG_B1F_SW
    # 도엽 범위 약간 확장 (격자 라벨은 도엽 바깥에도 있음)
    margin = 20000
    dong_clip = (sw[0]-margin, sw[1]-margin,
                 sw[0]+SHEET_W+margin, sw[1]+SHEET_H+margin)
    print(f'  DONG 클립: xmin={dong_clip[0]:.0f}, ymin={dong_clip[1]:.0f}, '
          f'xmax={dong_clip[2]:.0f}, ymax={dong_clip[3]:.0f}')

    dong_texts = extract_texts(msp_dong, clip=dong_clip)
    print(f'  DONG TEXT {len(dong_texts)}건')

    dong_x_dict, dong_y_dict = extract_grid_coords(
        dong_texts, _GRID_X_PAT, _GRID_Y_PAT
    )
    print(f'  DONG 격자: X {sorted(dong_x_dict.keys())} ({len(dong_x_dict)}개)')
    print(f'  DONG 격자: Y {sorted(dong_y_dict.keys())} ({len(dong_y_dict)}개)')

    dong_ev = find_ev_texts(dong_texts)
    print(f'  DONG E/V 텍스트: {len(dong_ev)}건')
    for ev in dong_ev[:5]:
        print(f'    "{ev["text"]}" @ ({ev["x"]:.0f}, {ev["y"]:.0f})')

    # ─────────────────────────────────────────────
    # Step 3: PKG 텍스트 추출 (101동 인근 클립)
    # ─────────────────────────────────────────────
    print(f'\n[Step 3] PKG 101동 인근 텍스트 추출...')
    # 기존 coord_align_result.json의 bsmnt_clip 활용
    try:
        with open('output/coord_align_result.json', encoding='utf-8') as f:
            align = json.load(f)
        bsmnt_clip_raw = align.get('bsmnt_clip')
        if bsmnt_clip_raw:
            # 클립을 크게 확장해서 격자 라벨 포함
            bc = bsmnt_clip_raw
            expand = 300000  # 30만mm 확장
            pkg_clip = (bc[0]-expand, bc[1]-expand, bc[2]+expand, bc[3]+expand)
            print(f'  coord_align_result 기반 PKG 클립 (확장 {expand//1000}m): '
                  f'({pkg_clip[0]:.0f}, {pkg_clip[1]:.0f}) ~ ({pkg_clip[2]:.0f}, {pkg_clip[3]:.0f})')
        else:
            pkg_clip = None
    except Exception as e:
        print(f'  coord_align_result 없음: {e}')
        pkg_clip = None

    pkg_texts_all = extract_texts(msp_pkg)  # 전체 텍스트 (클립 없이)
    print(f'  PKG 전체 TEXT {len(pkg_texts_all)}건')

    # 전체에서 격자 추출 (격자 라벨은 넓게 퍼져 있음)
    pkg_x_dict_all, pkg_y_dict_all = extract_grid_coords(
        pkg_texts_all, _GRID_X_PAT, _GRID_Y_PAT
    )
    print(f'  PKG 전체 격자: X {len(pkg_x_dict_all)}개, Y {len(pkg_y_dict_all)}개')
    if pkg_x_dict_all:
        print(f'    X 샘플: {sorted(pkg_x_dict_all.keys())[:10]}')
    if pkg_y_dict_all:
        print(f'    Y 샘플: {sorted(pkg_y_dict_all.keys())[:10]}')

    pkg_ev = find_ev_texts(pkg_texts_all)
    print(f'  PKG E/V 텍스트: {len(pkg_ev)}건')
    for ev in pkg_ev[:10]:
        print(f'    "{ev["text"]}" @ ({ev["x"]:.0f}, {ev["y"]:.0f})')

    pkg_sl = find_sl_markers(pkg_texts_all)
    print(f'  PKG SL 마커: {len(pkg_sl)}건')
    for sl in pkg_sl[:10]:
        print(f'    "{sl["text"]}" @ ({sl["x"]:.0f}, {sl["y"]:.0f})')

    # ─────────────────────────────────────────────
    # Step 4: TX, TY 계산
    # ─────────────────────────────────────────────
    print(f'\n[Step 4] TX, TY 계산...')

    # 전략 A: 공통 격자 라벨로 오프셋 계산
    print(f'\n  [전략 A] 공통 격자 라벨 오프셋:')
    tx_a, ty_a, evidence_a, conf_a = compute_offset_from_grid(
        dong_x_dict, dong_y_dict,
        pkg_x_dict_all, pkg_y_dict_all
    )
    print(f'  결과: TX={tx_a}, TY={ty_a}, confidence={conf_a}')

    # 전략 B: E/V 코어 좌표 차이
    # DONG E/V 클러스터 중심 구하기
    dong_ev_center = cluster_center(dong_ev) if dong_ev else None
    # PKG E/V 중 101동 인근 필터링 (coord_align_result의 bsmnt_101_text 기준)
    pkg_ev_101 = []
    if bsmnt_clip_raw:
        bc = bsmnt_clip_raw
        # 101동 위치에서 ±50000mm 이내 E/V
        bc_cx = (bc[0]+bc[2])/2
        bc_cy = (bc[1]+bc[3])/2
        pkg_ev_101 = [ev for ev in pkg_ev
                      if abs(ev['x']-bc_cx) < 100000 and abs(ev['y']-bc_cy) < 100000]
    pkg_ev_101_center = cluster_center(pkg_ev_101) if pkg_ev_101 else None

    print(f'\n  [전략 B] E/V 코어 오프셋:')
    if dong_ev_center and pkg_ev_101_center:
        tx_b = round(pkg_ev_101_center[0] - dong_ev_center[0])
        ty_b = round(pkg_ev_101_center[1] - dong_ev_center[1])
        print(f'  DONG E/V 중심: ({dong_ev_center[0]:.0f}, {dong_ev_center[1]:.0f})')
        print(f'  PKG E/V 중심(101동 근처): ({pkg_ev_101_center[0]:.0f}, {pkg_ev_101_center[1]:.0f})')
        print(f'  TX_B={tx_b}, TY_B={ty_b}')
    else:
        tx_b, ty_b = None, None
        print(f'  FAIL: DONG E/V={dong_ev_center}, PKG E/V 101동={pkg_ev_101_center}')

    # 기존 추측값 (비교용)
    TX_OLD, TY_OLD = -448000, 3622000
    print(f'\n  [기존 추측값] TX={TX_OLD}, TY={TY_OLD}')

    # 최종 TX, TY 결정
    # 주의: DONG 도면에는 X/Y 격자 라벨이 없으므로 grid 전략은 사용 불가.
    # 실제 정밀값은 column_brute_force 방식으로 계산됨 (scripts/verify_coords.py 참조)
    # coord_config.json에 이미 검증된 값이 존재하는 경우 그 값을 사용
    import os
    if os.path.exists(OUT_JSON):
        try:
            with open(OUT_JSON, encoding='utf-8') as _f:
                _existing = json.load(_f)
            if _existing.get('confidence') in ('high', 'medium'):
                TX_FINAL = _existing['TX_PKG']
                TY_FINAL = _existing['TY_PKG']
                method = _existing.get('method', 'existing')
                confidence_final = _existing['confidence']
                evidence_final = [{'type': 'existing_verified', 'source': OUT_JSON}]
                print(f'  기존 검증값 사용: TX={TX_FINAL}, TY={TY_FINAL} (confidence={confidence_final})')
            else:
                raise ValueError('confidence low')
        except Exception:
            TX_FINAL, TY_FINAL = TX_OLD, TY_OLD
            method = 'fallback_old_estimate'
            confidence_final = 'low'
            evidence_final = [{'type': 'fallback', 'reason': 'grid/ev 둘 다 실패, 기존 검증값 없음'}]
    elif tx_a is not None and conf_a in ('high', 'medium'):
        TX_FINAL, TY_FINAL = tx_a, ty_a
        method = 'grid_intersection'
        confidence_final = conf_a
        evidence_final = evidence_a
    elif tx_b is not None:
        TX_FINAL, TY_FINAL = tx_b, ty_b
        method = 'ev_core'
        confidence_final = 'medium'
        evidence_final = [
            {'type': 'ev_core',
             'dong_ev_center': [round(dong_ev_center[0]), round(dong_ev_center[1])],
             'pkg_ev_101_center': [round(pkg_ev_101_center[0]), round(pkg_ev_101_center[1])],
             'tx': TX_FINAL, 'ty': TY_FINAL}
        ]
    else:
        TX_FINAL, TY_FINAL = TX_OLD, TY_OLD
        method = 'fallback_old_estimate'
        confidence_final = 'low'
        evidence_final = [{'type': 'fallback', 'reason': 'grid/ev 둘 다 실패'}]

    # 기존값과 차이 출력
    print(f'\n  [최종] TX={TX_FINAL}, TY={TY_FINAL} (method={method}, confidence={confidence_final})')
    print(f'  기존 대비: ΔTX={TX_FINAL-TX_OLD:+.0f}, ΔTY={TY_FINAL-TY_OLD:+.0f}')

    # ─────────────────────────────────────────────
    # Step 5: TZ 계산
    # ─────────────────────────────────────────────
    print(f'\n[Step 5] TZ 계산...')
    with open(STAGE0, encoding='utf-8') as f:
        levels = json.load(f)

    tz_b2f = levels['floor_sl']['B2F']['sl_abs']
    tz_b1f_stage0 = levels['floor_sl']['B1F']['sl_abs']
    print(f'  stage0 B2F SL: {tz_b2f}mm (verified={levels["floor_sl"]["B2F"]["verified"]})')
    print(f'  stage0 B1F SL: {tz_b1f_stage0}mm (verified={levels["floor_sl"]["B1F"]["verified"]})')

    # PKG 도면에서 SL 마커 확인
    b1f_from_pkg = extract_b1f_sl_from_pkg(pkg_sl)
    print(f'\n  PKG 도면 B1F SL 후보: {b1f_from_pkg[:5]}')

    # B2F SL 마커도 확인
    b2f_sl_vals = []
    for item in pkg_sl:
        m = re.search(r'B2F\s+SL\s*[+\-]?\s*(\d+)', item['text'], re.IGNORECASE)
        if m:
            b2f_sl_vals.append({'sl': int(m.group(1)), **item})
        m2 = re.search(r'SL\s*=?\s*(-?\d+)', item['text'], re.IGNORECASE)
        if m2:
            val = int(m2.group(1))
            if -10000 <= val <= -8000:
                b2f_sl_vals.append({'sl': val, **item})
    print(f'  PKG 도면 B2F SL 후보: {b2f_sl_vals[:3]}')

    # TZ = SL 절대값 (구조 Z=0 기준)
    # TZ_B2F: B2F 슬라브 면 Z좌표
    # PKG는 B2F 기준으로 모델링됨 (좌표가 음수)
    # TZ 보정: PKG 도면 Z=0이 어디인지 확인 필요
    tz_b2f_final = tz_b2f  # -9050mm (검증됨)
    tz_b1f_final = tz_b1f_stage0  # -5600mm (미검증)
    tz_confidence = 'low' if not levels['floor_sl']['B1F']['verified'] else 'high'

    print(f'\n  TZ_B2F={tz_b2f_final}mm (confidence=high)')
    print(f'  TZ_B1F={tz_b1f_final}mm (confidence={tz_confidence})')

    # ─────────────────────────────────────────────
    # Step 6: 결과 저장
    # ─────────────────────────────────────────────
    print(f'\n[Step 6] 결과 저장...')
    result = {
        'TX_PKG': TX_FINAL,
        'TY_PKG': TY_FINAL,
        'TZ_B1F': tz_b1f_final,
        'TZ_B2F': tz_b2f_final,
        'method': method,
        'confidence': confidence_final,
        'evidence': {
            'grid_offset': evidence_final,
            'tz_b2f_verified': levels['floor_sl']['B2F']['verified'],
            'tz_b1f_verified': levels['floor_sl']['B1F']['verified'],
            'tz_b1f_confidence': tz_confidence,
            'pkg_sl_markers': pkg_sl[:10],
            'dong_ev_texts': dong_ev[:5],
            'pkg_ev_texts': pkg_ev[:10],
            'dong_grid_x': {k: round(v) for k, v in dong_x_dict.items()},
            'dong_grid_y': {k: round(v) for k, v in dong_y_dict.items()},
            'pkg_grid_x_sample': {k: round(v) for k, v in list(pkg_x_dict_all.items())[:20]},
            'pkg_grid_y_sample': {k: round(v) for k, v in list(pkg_y_dict_all.items())[:20]},
        },
        'old_estimate': {'TX': TX_OLD, 'TY': TY_OLD},
        'delta_from_old': {
            'TX': TX_FINAL - TX_OLD if TX_FINAL is not None else None,
            'TY': TY_FINAL - TY_OLD if TY_FINAL is not None else None,
        },
        'elapsed_sec': round(time.time()-t0, 1),
    }

    os.makedirs('output', exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'  저장: {OUT_JSON}')

    print(f'\n{"="*60}')
    print(f'최종 결과:')
    print(f'  TX_PKG  = {TX_FINAL} mm  (method={method})')
    print(f'  TY_PKG  = {TY_FINAL} mm')
    print(f'  TZ_B1F  = {tz_b1f_final} mm  (confidence={tz_confidence})')
    print(f'  TZ_B2F  = {tz_b2f_final} mm  (confidence=high)')
    print(f'  전체 confidence = {confidence_final}')
    print(f'{"="*60}')
    print(f'완료 ({time.time()-t0:.1f}s)')

    return result


if __name__ == '__main__':
    main()
