"""
probe_coord_align.py — 두 도면 기둥 좌표 정렬 프로브
=====================================================
101동 도면 ↔ 지하주차장 도면의 기둥 좌표 매핑.

방법:
  1. 각 도면에서 기둥 (cx, cy) 추출
  2. 후보 오프셋 (tx, ty) 스캔
  3. 가장 많은 기둥이 겹치는 오프셋 = 좌표계 변환

출력:
  output/coord_align_result.json — 최적 (tx, ty) + 겹침 기둥 목록
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf
from core.dxf_parser.entity_scanner import iter_all
from core.dxf_parser.full_extractor import FullExtractor, ColumnPrim

# ─────────────────────────────────────────────────────────────
# 경로
# ─────────────────────────────────────────────────────────────

DONG_DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
BSMNT_DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
OUT = "output"

# 101동 도면 기둥 클립 — E/V 앵커 (149013, 2321258) 기준 ±80m
DONG_CLIP = (149013 - 80000, 2321258 - 80000, 149013 + 80000, 2321258 + 80000)

# 지하주차장 도면 101동 영역 — "101" TEXT 기준 ±80m
BSMNT_101_TEXT = (632082.0, -1296738.0)
BSMNT_CLIP = (
    BSMNT_101_TEXT[0] - 80000, BSMNT_101_TEXT[1] - 80000,
    BSMNT_101_TEXT[0] + 80000, BSMNT_101_TEXT[1] + 80000,
)


def extract_columns_from_basement(doc, clip) -> list[ColumnPrim]:
    """지하주차장 도면에서 기둥 추출.

    기둥 레이어: 00_COLUMN
    기둥은 주로 LINE 교차점으로 표현되거나 LWPOLYLINE 닫힌 사각형.
    """
    msp = doc.modelspace()
    cols = []
    seen = set()

    # LWPOLYLINE 닫힌 사각형 (기둥 단면)
    for e in iter_all(msp):
        t = e.dxftype()
        try:
            layer = e.dxf.layer
        except Exception:
            layer = ''

        if t == 'LWPOLYLINE':
            try:
                if not (e.dxf.flags & 1):  # 닫힌 것만
                    continue
                pts = [(p[0], p[1]) for p in e.get_points()]
                if len(pts) < 3:
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                cx = (min(xs) + max(xs)) / 2
                cy = (min(ys) + max(ys)) / 2
                if not _in_clip(cx, cy, clip):
                    continue
                w = max(xs) - min(xs)
                h = max(ys) - min(ys)
                # 기둥 크기 필터 (100~2000mm)
                if not (100 <= w <= 2000 and 100 <= h <= 2000):
                    continue
                key = (round(cx / 100) * 100, round(cy / 100) * 100)
                if key in seen:
                    continue
                seen.add(key)
                cols.append(ColumnPrim(cx=cx, cy=cy, w=w, h=h,
                                       source='LWPOLY', layer=layer))
            except Exception:
                pass

        elif t == 'HATCH':
            try:
                pts = []
                for path in e.paths:
                    try:
                        pts = [(p[0], p[1]) for p in path.vertices]
                        if len(pts) >= 3:
                            break
                    except Exception:
                        pass
                if len(pts) < 3:
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                cx = (min(xs) + max(xs)) / 2
                cy = (min(ys) + max(ys)) / 2
                if not _in_clip(cx, cy, clip):
                    continue
                w = max(xs) - min(xs)
                h = max(ys) - min(ys)
                if not (100 <= w <= 2000 and 100 <= h <= 2000):
                    continue
                key = (round(cx / 100) * 100, round(cy / 100) * 100)
                if key in seen:
                    continue
                seen.add(key)
                cols.append(ColumnPrim(cx=cx, cy=cy, w=w, h=h,
                                       source='HATCH', layer=layer))
            except Exception:
                pass

    return cols


def find_best_offset(
    cols_a: list[ColumnPrim],    # 기준 도면 (101동)
    cols_b: list[ColumnPrim],    # 변환할 도면 (지하주차장)
    tol_mm: float = 300.0,
    sample_n: int = 30,
    grid_mm: float = 500.0,
) -> dict:
    """기둥 집합 A, B에서 최적 (tx, ty) 계산.

    투표법: 모든 (A,B) 기둥 쌍에서 delta = A - B 계산.
    가장 많이 표를 받은 delta = 실제 좌표 오프셋.

    복잡도: O(sample_n²). sample_n=30이면 900쌍.
    """
    from collections import Counter
    import random

    random.seed(42)
    sample_a = random.sample(cols_a, min(sample_n, len(cols_a)))
    sample_b = random.sample(cols_b, min(sample_n, len(cols_b)))
    pts_a = [(c.cx, c.cy) for c in sample_a]
    pts_b = [(c.cx, c.cy) for c in sample_b]

    # 모든 (A,B) 쌍에서 delta 투표
    deltas = []
    for bx, by in pts_b:
        for ax, ay in pts_a:
            dx = ax - bx
            dy = ay - by
            # grid_mm 단위로 반올림 (격자 오차 흡수)
            gdx = round(dx / grid_mm) * grid_mm
            gdy = round(dy / grid_mm) * grid_mm
            deltas.append((gdx, gdy))

    # 가장 많이 나온 delta
    cnt = Counter(deltas)
    print(f'  delta 후보 상위 5:')
    for delta, votes in cnt.most_common(5):
        print(f'    ({delta[0]:.0f},{delta[1]:.0f}) — {votes}표')

    best_delta = cnt.most_common(1)[0][0]
    tx, ty = float(best_delta[0]), float(best_delta[1])

    # 실제 검증 — 이 offset으로 겹치는 기둥 수
    matched = 0
    matched_pairs = []
    for bx, by in pts_b:
        ux, uy = bx + tx, by + ty
        for ax, ay in pts_a:
            if abs(ax - ux) < tol_mm and abs(ay - uy) < tol_mm:
                matched += 1
                matched_pairs.append({
                    'b_raw': [round(bx), round(by)],
                    'b_unified': [round(ux), round(uy)],
                    'a': [round(ax), round(ay)],
                    'error': round((abs(ax-ux)**2 + abs(ay-uy)**2)**0.5),
                })
                break

    return {
        'tx': tx, 'ty': ty,
        'matched': matched, 'total_b_sample': len(pts_b),
        'total_b_all': len(cols_b), 'total_a': len(pts_a),
        'match_rate': round(matched / max(1, len(pts_b)), 3),
        'matched_pairs': matched_pairs[:10],
    }


def _in_clip(x, y, clip):
    return clip[0] <= x <= clip[2] and clip[1] <= y <= clip[3]


# ─────────────────────────────────────────────────────────────
# 보조: INSERT 기반 추출
# ─────────────────────────────────────────────────────────────

def extract_columns_insert(doc, clip) -> list[ColumnPrim]:
    """INSERT 블록 기반 기둥 추출 (일반 FullExtractor)."""
    extractor = FullExtractor()
    result = extractor.extract(doc, clip=clip)
    return result.columns


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)

    print(f'[101동] 기둥 추출... clip={DONG_CLIP}')
    doc_dong = ezdxf.readfile(DONG_DXF, encoding='cp949')
    cols_dong = extract_columns_insert(doc_dong, DONG_CLIP)
    print(f'  {len(cols_dong)}개 (INSERT+HATCH)')

    # 101동 도면 기둥이 너무 적으면 더 넓게
    if len(cols_dong) < 50:
        print('  [확장] clip 없이 재추출...')
        cols_dong = extract_columns_insert(doc_dong, None)
        print(f'  {len(cols_dong)}개 (전체 도면)')

    print(f'\n[지하주차장] 기둥 추출... clip={BSMNT_CLIP}')
    doc_bsmnt = ezdxf.readfile(BSMNT_DXF, encoding='cp949')
    cols_bsmnt = extract_columns_from_basement(doc_bsmnt, BSMNT_CLIP)
    print(f'  LWPOLY+HATCH: {len(cols_bsmnt)}개')

    # INSERT 기둥도 추가
    cols_bsmnt_insert = extract_columns_insert(doc_bsmnt, BSMNT_CLIP)
    print(f'  INSERT: {len(cols_bsmnt_insert)}개')
    cols_bsmnt.extend(cols_bsmnt_insert)
    print(f'  합계: {len(cols_bsmnt)}개')

    print('\n[오프셋 탐색]')
    if len(cols_dong) < 5 or len(cols_bsmnt) < 5:
        print('  기둥 부족 — 수동 앵커 사용')
        # "101" TEXT를 기준점으로 한 오프셋 계산
        # 101동 도면 E/V (149013, 2321258) ↔ 지하주차장 "101" TEXT (632082, -1296738)
        tx = 149013 - BSMNT_101_TEXT[0]  # = -483069
        ty = 2321258 - BSMNT_101_TEXT[1]  # = 3617996
        align = {
            'tx': tx, 'ty': ty,
            'method': 'text_anchor_ev_approx',
            'note': '101동 E/V (149013,2321258) vs "101" TEXT (632082,-1296738)',
            'matched': 0, 'total_b_all': len(cols_bsmnt), 'total_a': len(cols_dong),
        }
    else:
        align = find_best_offset(cols_dong, cols_bsmnt)
        align['method'] = 'column_brute_force'

    print(f'  최적 오프셋: tx={align["tx"]:.0f} ty={align["ty"]:.0f}')
    print(f'  매칭율: {align.get("match_rate", "N/A")}')

    # 최종 결과
    result = {
        'dong_columns': len(cols_dong),
        'bsmnt_columns': len(cols_bsmnt),
        'alignment': align,
        'dong_clip': DONG_CLIP,
        'bsmnt_clip': BSMNT_CLIP,
        'bsmnt_101_text': list(BSMNT_101_TEXT),
        'elapsed_sec': round(time.time()-t0, 1),
    }

    out_path = os.path.join(OUT, 'coord_align_result.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'\n[종결] {time.time()-t0:.1f}s → {out_path}')
    print('  결론:')
    print(f'  지하주차장 기둥 → 101동 좌표계: +({align["tx"]:.0f}, {align["ty"]:.0f})')
    print(f'  이 값을 CoordUnifier manual_anchor에 주입 가능')


if __name__ == '__main__':
    main()
