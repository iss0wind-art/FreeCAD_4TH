"""
build_skeleton.py -- 골조선 분리 전문가 메인 빌드
===================================================
Step 1 레이어 조사 결과를 바탕으로:
  Step 2: 골조선 엔티티 추출 (Z=0 강제)
  Step 3: 겹침·중복 제거
  Step 4: 연결성 확인 + 고립 선분 격리
  Step 5: 결과 DXF 저장
  Step 6: 혼란 구간 수동 레이어 처리
  Step 7: 요약 JSON 저장
"""
from __future__ import annotations

import sys
import json
import math
from collections import defaultdict
from typing import List, Tuple, Optional, Dict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'D:/Git/FreeCAD_4TH')

import ezdxf
from ezdxf import colors as dxf_colors

DXF_DONG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
DXF_PKG  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'

OUT_DONG = 'output/skeleton_dong_b1f.dxf'
OUT_PKG  = 'output/skeleton_pkg_b1f.dxf'
OUT_JSON = 'output/skeleton_summary.json'

# ──────────────────────────────────────────────────────────────
# 레이어 분류 (Step 1 결과 반영)
# ──────────────────────────────────────────────────────────────

import re

# DONG: 101동 구조평면도 KEEP 패턴
DONG_KEEP_PAT = re.compile(
    r'^S-GIRDER$|^S-BEAM$|^S-PC-GIRDER$|^S-PC-SLAB$'
    r'|^A-WALL-RC$|^A-WALL-BRICK$'
    r'|^00_SHEAR.WALL$|^00_SLAB.END'
    r'|^00_FOUNDATION$|^00_REINFORCE.BAR$'
    r'|A-WALL-RC'            # XRef 안 RC벽
    r'|A-WALL-BRICK'         # XRef 안 벽돌벽 (구조) -- 나중에 필터 가능
    r'|A-COL$|A-COL\b',      # XRef 안 기둥
    re.IGNORECASE,
)

# PKG: 지하주차장 구조평면도 KEEP 패턴
PKG_KEEP_PAT = re.compile(
    r'^00_SHEAR.WALL$|^00_COLUMN$|^00_BEAM$|^00_\(APT\)BEAM$'
    r'|^00_UNDER.ELEMENT$|^00_SLAB.END'
    r'|^S-PC-GIRDER$|^S-PC-SLAB$'
    r'|^00_CENTER$'
    r'|A-WALL-RC',
    re.IGNORECASE,
)

# SKIP: 두 DXF 공통 잡선 패턴
SKIP_PAT = re.compile(
    r'HATCH|DEFPOINTS?|Defpoints?'
    r'|DIM\b|DIMENSION|_DIM$'
    r'|FUR|STAIR|DOOR|WINDOW|EQUIP'
    r'|ANNO|TEXT|MTEXT|NAME|SYMBOL'
    r'|MARK|NOTE|TAG|CHECK'
    r'|BORDER|FRAME|TITLE',
    re.IGNORECASE,
)

# 골조선으로 추출할 엔티티 타입
SKELETON_TYPES = {'LINE', 'LWPOLYLINE', 'ARC'}


# ──────────────────────────────────────────────────────────────
# 좌표 자료구조
# ──────────────────────────────────────────────────────────────

class Segment:
    """2D 선분 (Z=0 강제)."""
    __slots__ = ('x0', 'y0', 'x1', 'y1', 'layer', 'etype', 'arc_data')

    def __init__(self, x0, y0, x1, y1, layer='', etype='LINE', arc_data=None):
        self.x0 = float(x0)
        self.y0 = float(y0)
        self.x1 = float(x1)
        self.y1 = float(y1)
        self.layer = layer
        self.etype = etype
        self.arc_data = arc_data  # ARC: (cx, cy, r, a_start, a_end) or None

    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    def midpoint(self) -> Tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def canonical(self) -> 'Segment':
        """시작점이 더 작은 방향으로 정규화."""
        if (self.x0, self.y0) <= (self.x1, self.y1):
            return self
        return Segment(self.x1, self.y1, self.x0, self.y0,
                       self.layer, self.etype, self.arc_data)

    def __repr__(self):
        return f'Seg({self.x0:.1f},{self.y0:.1f} -> {self.x1:.1f},{self.y1:.1f})'


# ──────────────────────────────────────────────────────────────
# Step 2: 골조선 엔티티 추출
# ──────────────────────────────────────────────────────────────

def extract_skeleton_segments(
    dxf_path: str,
    keep_pat: re.Pattern,
    label: str,
    encoding: str = 'cp949',
) -> Tuple[List[Segment], Dict]:
    """
    DXF에서 골조선 레이어의 LINE/LWPOLYLINE/ARC를 추출.
    Z값 무조건 0으로 고정.

    Returns:
        (segments, stats)
    """
    print(f'\n[{label}] Step 2: 골조선 엔티티 추출 시작...')
    try:
        doc = ezdxf.readfile(dxf_path, encoding=encoding)
    except Exception as e:
        print(f'  FAIL: 파일 읽기 오류 — {e}')
        return [], {}

    msp = doc.modelspace()

    segments: List[Segment] = []
    stats = {
        'total_scanned': 0,
        'kept': 0,
        'dropped_layer': 0,
        'dropped_type': 0,
        'dropped_degenerate': 0,
        'by_layer': defaultdict(int),
        'by_type': defaultdict(int),
    }

    def process_entity(e, depth=0):
        if depth > 6:
            return
        etype = e.dxftype()

        # INSERT 재귀
        if etype == 'INSERT':
            try:
                for sub in e.virtual_entities():
                    process_entity(sub, depth + 1)
            except Exception:
                pass
            return

        stats['total_scanned'] += 1

        # 레이어 확인
        layer = '0'
        try:
            layer = e.dxf.layer or '0'
        except Exception:
            pass

        # KEEP 여부 판단
        if not keep_pat.search(layer):
            stats['dropped_layer'] += 1
            return
        if SKIP_PAT.search(layer):
            stats['dropped_layer'] += 1
            return

        # 타입 필터
        if etype not in SKELETON_TYPES:
            stats['dropped_type'] += 1
            return

        # 좌표 추출 (Z=0 강제)
        segs = _entity_to_segments(e, etype, layer)
        if not segs:
            stats['dropped_degenerate'] += 1
            return

        for seg in segs:
            if seg.length() < 1.0:  # 1mm 미만 잡선 제거
                stats['dropped_degenerate'] += 1
                continue
            segments.append(seg)
            stats['kept'] += 1
            stats['by_layer'][layer] += 1
            stats['by_type'][etype] += 1

    for e in msp:
        process_entity(e)

    stats['by_layer'] = dict(stats['by_layer'])
    stats['by_type'] = dict(stats['by_type'])

    print(f'  스캔: {stats["total_scanned"]:,}  추출: {stats["kept"]:,}  '
          f'(레이어제거: {stats["dropped_layer"]:,}, '
          f'타입제거: {stats["dropped_type"]:,}, '
          f'잡선제거: {stats["dropped_degenerate"]:,})')
    print(f'  추출 레이어 ({len(stats["by_layer"])}개):')
    for lyr, cnt in sorted(stats['by_layer'].items(), key=lambda x: -x[1])[:15]:
        print(f'    {lyr:<48} {cnt:>5}')

    return segments, stats


def _entity_to_segments(e, etype: str, layer: str) -> List[Segment]:
    """엔티티 → Segment 목록 변환. Z=0 강제."""
    segs = []
    try:
        if etype == 'LINE':
            s, en = e.dxf.start, e.dxf.end
            segs.append(Segment(s.x, s.y, en.x, en.y, layer, 'LINE'))

        elif etype == 'LWPOLYLINE':
            pts = list(e.get_points())  # (x, y, start_width, end_width, bulge)
            if len(pts) < 2:
                return []
            is_closed = bool(e.dxf.flags & 1)
            # 열린 것만 골조선 (닫힌 것은 면 외곽선)
            # 단, 닫힌 것도 포함 — 기둥 외곽 등
            for i in range(len(pts) - 1):
                x0, y0 = pts[i][0], pts[i][1]
                x1, y1 = pts[i+1][0], pts[i+1][1]
                segs.append(Segment(x0, y0, x1, y1, layer, 'LWPOLYLINE'))
            if is_closed and len(pts) >= 2:
                x0, y0 = pts[-1][0], pts[-1][1]
                x1, y1 = pts[0][0], pts[0][1]
                segs.append(Segment(x0, y0, x1, y1, layer, 'LWPOLYLINE'))

        elif etype == 'ARC':
            c = e.dxf.center
            r = e.dxf.radius
            a_s = math.radians(e.dxf.start_angle)
            a_e = math.radians(e.dxf.end_angle)
            # ARC → 시작/끝점을 직선으로 근사 (골조선 연결성용)
            x0 = c.x + r * math.cos(a_s)
            y0 = c.y + r * math.sin(a_s)
            x1 = c.x + r * math.cos(a_e)
            y1 = c.y + r * math.sin(a_e)
            arc_data = (c.x, c.y, r, e.dxf.start_angle, e.dxf.end_angle)
            segs.append(Segment(x0, y0, x1, y1, layer, 'ARC', arc_data))

    except Exception:
        pass
    return segs


# ──────────────────────────────────────────────────────────────
# Step 3: 겹침·중복 제거
# ──────────────────────────────────────────────────────────────

DUPLICATE_TOL = 5.0    # 동일 선분 판정 (양 끝점 거리 < 5mm)
PARALLEL_TOL  = 50.0   # 평행 중복 판정 (간격 < 50mm)
ANGLE_TOL_DEG = 1.0    # 방향 유사 판정 (각도 < 1도)


def remove_duplicates(segments: List[Segment]) -> Tuple[List[Segment], int]:
    """
    동일 선분 제거.
    양 끝점이 모두 DUPLICATE_TOL 이내이면 하나만 유지.

    Returns:
        (deduped, removed_count)
    """
    print(f'\n  Step 3a: 동일 선분 제거 (tol={DUPLICATE_TOL}mm)...')
    if not segments:
        return [], 0

    # 정규화된 형태로 비교
    canonical = [s.canonical() for s in segments]
    keep_mask = [True] * len(canonical)
    removed = 0

    # O(n²)는 느리므로 공간 해시로 가속
    # 그리드 셀 크기 = DUPLICATE_TOL * 2
    grid_size = DUPLICATE_TOL * 2
    grid: Dict[Tuple[int,int,int,int], List[int]] = defaultdict(list)

    for i, seg in enumerate(canonical):
        cell = (
            int(seg.x0 // grid_size),
            int(seg.y0 // grid_size),
            int(seg.x1 // grid_size),
            int(seg.y1 // grid_size),
        )
        grid[cell].append(i)

    # 같은 셀 또는 인접 셀 내에서만 비교
    checked = set()
    for i, seg_i in enumerate(canonical):
        if not keep_mask[i]:
            continue
        cell = (
            int(seg_i.x0 // grid_size),
            int(seg_i.y0 // grid_size),
            int(seg_i.x1 // grid_size),
            int(seg_i.y1 // grid_size),
        )
        # 같은 셀 내 비교
        for j in grid[cell]:
            if j <= i or not keep_mask[j]:
                continue
            pair = (i, j)
            if pair in checked:
                continue
            checked.add(pair)
            seg_j = canonical[j]
            d0 = math.hypot(seg_i.x0 - seg_j.x0, seg_i.y0 - seg_j.y0)
            d1 = math.hypot(seg_i.x1 - seg_j.x1, seg_i.y1 - seg_j.y1)
            if d0 < DUPLICATE_TOL and d1 < DUPLICATE_TOL:
                keep_mask[j] = False
                removed += 1

    deduped = [s for s, keep in zip(segments, keep_mask) if keep]
    print(f'    입력: {len(segments):,}  제거: {removed:,}  남은: {len(deduped):,}')
    return deduped, removed


def remove_parallel_overlaps(segments: List[Segment]) -> Tuple[List[Segment], int]:
    """
    평행 근사 중복 제거.
    같은 방향 + 간격 < PARALLEL_TOL + 길이 유사 → 중간값으로 통합.
    경고: O(n²) 부분 있음. 대용량에서 느릴 수 있음.

    Returns:
        (merged, merged_count)
    """
    print(f'  Step 3b: 평행 중복 통합 (tol={PARALLEL_TOL}mm, angle={ANGLE_TOL_DEG}°)...')
    if not segments:
        return [], 0

    merged_count = 0
    keep_mask = [True] * len(segments)

    def seg_angle(s: Segment) -> float:
        """선분 방향 각도 (0~180도)."""
        dx = s.x1 - s.x0
        dy = s.y1 - s.y0
        a = math.degrees(math.atan2(dy, dx)) % 180
        return a

    def point_to_line_dist(px, py, x0, y0, x1, y1) -> float:
        """점 (px,py)에서 선분 (x0,y0)-(x1,y1) 까지 수선 거리."""
        dx, dy = x1 - x0, y1 - y0
        L2 = dx*dx + dy*dy
        if L2 < 1e-10:
            return math.hypot(px - x0, py - y0)
        t = ((px - x0)*dx + (py - y0)*dy) / L2
        if t < 0:
            return math.hypot(px - x0, py - y0)
        if t > 1:
            return math.hypot(px - x1, py - y1)
        foot_x = x0 + t * dx
        foot_y = y0 + t * dy
        return math.hypot(px - foot_x, py - foot_y)

    # 각도별 버킷으로 분류
    angle_bucket: Dict[int, List[int]] = defaultdict(list)
    for i, seg in enumerate(segments):
        bucket_key = int(seg_angle(seg) // ANGLE_TOL_DEG)
        angle_bucket[bucket_key].append(i)

    new_segments = list(segments)

    for bucket_key, indices in angle_bucket.items():
        if len(indices) < 2:
            continue
        for ii in range(len(indices)):
            i = indices[ii]
            if not keep_mask[i]:
                continue
            si = segments[i]
            for jj in range(ii + 1, len(indices)):
                j = indices[jj]
                if not keep_mask[j]:
                    continue
                sj = segments[j]

                # 각도 유사성 재확인
                ai = seg_angle(si)
                aj = seg_angle(sj)
                angle_diff = min(abs(ai - aj), 180 - abs(ai - aj))
                if angle_diff > ANGLE_TOL_DEG * 2:
                    continue

                # 상호 수선 거리 계산
                d1 = point_to_line_dist(si.x0, si.y0, sj.x0, sj.y0, sj.x1, sj.y1)
                d2 = point_to_line_dist(si.x1, si.y1, sj.x0, sj.y0, sj.x1, sj.y1)
                dist = min(d1, d2)

                if dist > PARALLEL_TOL:
                    continue

                # 선분이 겹치는 범위 확인 (투영 범위)
                dx = sj.x1 - sj.x0
                dy = sj.y1 - sj.y0
                L = math.hypot(dx, dy)
                if L < 1.0:
                    continue

                ux, uy = dx / L, dy / L
                # si 끝점의 sj 위 투영
                t0 = (si.x0 - sj.x0)*ux + (si.y0 - sj.y0)*uy
                t1 = (si.x1 - sj.x0)*ux + (si.y1 - sj.y0)*uy
                if t0 > t1:
                    t0, t1 = t1, t0
                # sj 길이
                L_sj = math.hypot(sj.x1 - sj.x0, sj.y1 - sj.y0)
                overlap = min(t1, L_sj) - max(t0, 0)
                overlap_ratio = overlap / max(L, L_sj) if max(L, L_sj) > 0 else 0

                if overlap_ratio < 0.5:
                    continue  # 50% 미만 겹침은 다른 선분으로 판단

                # 통합: 중간값 선분으로 교체
                mx0 = (si.x0 + sj.x0) / 2
                my0 = (si.y0 + sj.y0) / 2
                mx1 = (si.x1 + sj.x1) / 2
                my1 = (si.y1 + sj.y1) / 2
                new_segments[i] = Segment(mx0, my0, mx1, my1,
                                          si.layer, si.etype, si.arc_data)
                keep_mask[j] = False
                merged_count += 1
                si = new_segments[i]  # 갱신된 선분으로 계속 비교

    merged = [s for s, keep in zip(new_segments, keep_mask) if keep]
    print(f'    입력: {len(segments):,}  통합: {merged_count:,}  남은: {len(merged):,}')
    return merged, merged_count


# ──────────────────────────────────────────────────────────────
# Step 4: 연결성 확인
# ──────────────────────────────────────────────────────────────

SNAP_TOL = 5.0  # 끝점 snap 허용 거리 (5mm)


def check_connectivity(
    segments: List[Segment],
) -> Tuple[List[Segment], List[Segment]]:
    """
    선분 끝점 snap: 5mm 이내 → 같은 노드.
    고립 선분 (양 끝점 모두 연결 없음) → 별도 목록.

    Returns:
        (connected, isolated)
    """
    print(f'\n  Step 4: 연결성 확인 (snap_tol={SNAP_TOL}mm)...')
    if not segments:
        return [], []

    # 모든 끝점 수집
    endpoints: List[Tuple[float, float]] = []
    for seg in segments:
        endpoints.append((seg.x0, seg.y0))
        endpoints.append((seg.x1, seg.y1))

    # 그리드 기반 끝점 인접 탐색
    grid_size = SNAP_TOL * 2
    grid: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for idx, (x, y) in enumerate(endpoints):
        gx, gy = int(x // grid_size), int(y // grid_size)
        grid[(gx, gy)].append(idx)

    def has_neighbor(x, y, exclude_idx: int) -> bool:
        gx, gy = int(x // grid_size), int(y // grid_size)
        for dgx in range(-1, 2):
            for dgy in range(-1, 2):
                for idx in grid[(gx + dgx, gy + dgy)]:
                    if idx == exclude_idx:
                        continue
                    nx, ny = endpoints[idx]
                    if math.hypot(x - nx, y - ny) < SNAP_TOL:
                        return True
        return False

    connected: List[Segment] = []
    isolated: List[Segment] = []

    for seg_idx, seg in enumerate(segments):
        ep0_idx = seg_idx * 2
        ep1_idx = seg_idx * 2 + 1
        has_start = has_neighbor(seg.x0, seg.y0, ep0_idx)
        has_end   = has_neighbor(seg.x1, seg.y1, ep1_idx)
        if has_start or has_end:
            connected.append(seg)
        else:
            isolated.append(seg)

    print(f'    연결됨: {len(connected):,}  고립: {len(isolated):,}')
    return connected, isolated


# ──────────────────────────────────────────────────────────────
# Step 6: 혼란 구간 탐지 + 수동 레이어용 바운딩박스
# ──────────────────────────────────────────────────────────────

def find_noisy_zones(
    segments: List[Segment],
    grid_size: float = 500.0,  # 500mm = 0.5m 그리드
    density_threshold: int = 100,
) -> List[Dict]:
    """
    선분 밀도 기반 혼란 구간 탐지.
    그리드 셀당 선분 수가 threshold 이상이면 '혼란 구간'으로 표시.

    Returns:
        [{'bbox': (xmin, ymin, xmax, ymax), 'count': N}, ...]
    """
    print(f'\n  Step 6: 혼란 구간 탐지...')
    if not segments:
        return []

    cell_counts: Dict[Tuple[int, int], int] = defaultdict(int)
    for seg in segments:
        mx = (seg.x0 + seg.x1) / 2
        my = (seg.y0 + seg.y1) / 2
        gx, gy = int(mx // grid_size), int(my // grid_size)
        cell_counts[(gx, gy)] += 1

    noisy = []
    for (gx, gy), cnt in cell_counts.items():
        if cnt >= density_threshold:
            xmin = gx * grid_size
            ymin = gy * grid_size
            xmax = xmin + grid_size
            ymax = ymin + grid_size
            noisy.append({
                'bbox': (xmin, ymin, xmax, ymax),
                'count': cnt,
            })

    noisy.sort(key=lambda x: -x['count'])
    if noisy:
        print(f'    혼란 구간 {len(noisy)}개 발견 (상위 5):')
        for z in noisy[:5]:
            b = z['bbox']
            print(f'      bbox=({b[0]:.0f},{b[1]:.0f})-({b[2]:.0f},{b[3]:.0f})  '
                  f'선분수={z["count"]}')
    else:
        print(f'    혼란 구간 없음')
    return noisy


# ──────────────────────────────────────────────────────────────
# Step 5: 결과 DXF 저장
# ──────────────────────────────────────────────────────────────

def save_skeleton_dxf(
    clean: List[Segment],
    isolated: List[Segment],
    original: List[Segment],
    noisy_zones: List[Dict],
    out_path: str,
    label: str,
) -> Dict:
    """
    골조선 DXF 저장.
    레이어:
      SKELETON_CLEAN:    정제된 골조선 (흰색)
      SKELETON_ISOLATED: 고립 선분 (빨간색)
      SKELETON_ORIGINAL: 원본 (회색, 참고용)
      SKELETON_MANUAL:   혼란 구간 바운딩박스 (노란색, 수동 작업 안내)
    """
    print(f'\n  Step 5: DXF 저장 → {out_path}')

    doc = ezdxf.new(dxfversion='R2010')
    msp = doc.modelspace()

    # 레이어 정의
    doc.layers.add('SKELETON_CLEAN',    color=7)   # 흰색
    doc.layers.add('SKELETON_ISOLATED', color=1)   # 빨간색
    doc.layers.add('SKELETON_ORIGINAL', color=8)   # 회색
    doc.layers.add('SKELETON_MANUAL',   color=2)   # 노란색

    def add_segment(seg: Segment, layer_name: str):
        if seg.etype == 'ARC' and seg.arc_data:
            cx, cy, r, a_start, a_end = seg.arc_data
            msp.add_arc(
                center=(cx, cy, 0),
                radius=r,
                start_angle=a_start,
                end_angle=a_end,
                dxfattribs={'layer': layer_name},
            )
        else:
            msp.add_line(
                start=(seg.x0, seg.y0, 0),
                end=(seg.x1, seg.y1, 0),
                dxfattribs={'layer': layer_name},
            )

    # SKELETON_ORIGINAL (원본, 회색)
    for seg in original:
        add_segment(seg, 'SKELETON_ORIGINAL')

    # SKELETON_CLEAN (정제)
    for seg in clean:
        add_segment(seg, 'SKELETON_CLEAN')

    # SKELETON_ISOLATED (고립)
    for seg in isolated:
        add_segment(seg, 'SKELETON_ISOLATED')

    # SKELETON_MANUAL (혼란 구간 바운딩박스)
    manual_count = 0
    for zone in noisy_zones:
        xmin, ymin, xmax, ymax = zone['bbox']
        # 바운딩박스 사각형 (LWPOLYLINE)
        pts = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
        pline = msp.add_lwpolyline(pts, close=True,
                                   dxfattribs={'layer': 'SKELETON_MANUAL'})
        # 중심에 텍스트
        msp.add_text(
            f'MANUAL({zone["count"]})',
            dxfattribs={
                'layer': 'SKELETON_MANUAL',
                'height': (xmax - xmin) * 0.05,
                'insert': ((xmin + xmax) / 2, (ymin + ymax) / 2, 0),
            }
        )
        manual_count += 1

    doc.saveas(out_path)
    print(f'    저장 완료: clean={len(clean)}, isolated={len(isolated)}, '
          f'original={len(original)}, manual_zones={manual_count}')

    return {
        'clean_lines': len(clean),
        'isolated': len(isolated),
        'manual': manual_count,
    }


# ──────────────────────────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────────────────────────

def process_dxf(
    dxf_path: str,
    out_path: str,
    keep_pat: re.Pattern,
    label: str,
) -> Dict:
    """단일 DXF 처리 파이프라인."""
    print(f'\n{"="*60}')
    print(f'[{label}] 처리 시작')
    print('='*60)

    # Step 2: 추출
    original, stats = extract_skeleton_segments(dxf_path, keep_pat, label)
    if not original:
        print(f'  FAIL: 추출된 골조선 없음')
        return {'clean_lines': 0, 'isolated': 0, 'manual': 0, 'error': 'no segments'}

    # Step 3: 중복 제거
    print(f'\n  Step 3: 중복 제거...')
    deduped, dup_removed = remove_duplicates(original)
    merged, par_merged = remove_parallel_overlaps(deduped)

    # Step 4: 연결성
    connected, isolated = check_connectivity(merged)

    # Step 6: 혼란 구간 탐지
    noisy_zones = find_noisy_zones(merged)

    # Step 5: DXF 저장
    result = save_skeleton_dxf(
        clean=connected,
        isolated=isolated,
        original=original,
        noisy_zones=noisy_zones,
        out_path=out_path,
        label=label,
    )
    result['total_extracted'] = len(original)
    result['duplicates_removed'] = dup_removed + par_merged
    result['noisy_zones'] = len(noisy_zones)
    return result


if __name__ == '__main__':
    import os
    os.makedirs('output', exist_ok=True)

    # 101동 처리
    dong_result = process_dxf(DXF_DONG, OUT_DONG, DONG_KEEP_PAT, '101동 구조평면도')

    # 지하주차장 처리
    pkg_result  = process_dxf(DXF_PKG,  OUT_PKG,  PKG_KEEP_PAT,  '지하주차장 구조평면도')

    # Step 7: 요약 JSON
    summary = {
        'dong_b1f': {
            'clean_lines': dong_result.get('clean_lines', 0),
            'isolated':    dong_result.get('isolated', 0),
            'manual':      dong_result.get('manual', 0),
            'total_extracted': dong_result.get('total_extracted', 0),
            'duplicates_removed': dong_result.get('duplicates_removed', 0),
            'noisy_zones': dong_result.get('noisy_zones', 0),
            'error':       dong_result.get('error', None),
        },
        'pkg_b1f': {
            'clean_lines': pkg_result.get('clean_lines', 0),
            'isolated':    pkg_result.get('isolated', 0),
            'manual':      pkg_result.get('manual', 0),
            'total_extracted': pkg_result.get('total_extracted', 0),
            'duplicates_removed': pkg_result.get('duplicates_removed', 0),
            'noisy_zones': pkg_result.get('noisy_zones', 0),
            'error':       pkg_result.get('error', None),
        },
    }

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f'\n{"="*60}')
    print('Step 7: 요약 JSON 저장')
    print(f'  -> {OUT_JSON}')
    print()
    print(f'[101동]   clean={dong_result.get("clean_lines",0):,}  '
          f'isolated={dong_result.get("isolated",0):,}  '
          f'manual={dong_result.get("manual",0)}')
    print(f'[지하주차장] clean={pkg_result.get("clean_lines",0):,}  '
          f'isolated={pkg_result.get("isolated",0):,}  '
          f'manual={pkg_result.get("manual",0)}')
    print()
    print('완료.')
