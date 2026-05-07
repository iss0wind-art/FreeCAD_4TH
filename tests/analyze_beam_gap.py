"""
analyze_beam_gap.py -- 보 중심선 끝점 gap 분포 분석
====================================================
00_BEAM 고립 원인: 끝점 gap이 5mm 초과인지 확인.
실제 gap 분포를 측정해 snap_tol 적정값 결정.
"""
from __future__ import annotations

import sys
import math
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'D:/Git/FreeCAD_4TH')

import ezdxf

DXF_PKG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'

import re

PKG_KEEP_PAT = re.compile(
    r'^00_SHEAR.WALL$|^00_COLUMN$|^00_BEAM$|^00_\(APT\)BEAM$'
    r'|^00_UNDER.ELEMENT$|^00_SLAB.END'
    r'|^S-PC-GIRDER$|^S-PC-SLAB$'
    r'|^00_CENTER$'
    r'|A-WALL-RC',
    re.IGNORECASE,
)

SKIP_PAT = re.compile(
    r'HATCH|DEFPOINTS?|Defpoints?'
    r'|DIM\b|DIMENSION|_DIM$'
    r'|FUR|STAIR|DOOR|WINDOW|EQUIP'
    r'|ANNO|TEXT|MTEXT|NAME|SYMBOL'
    r'|MARK|NOTE|TAG|CHECK'
    r'|BORDER|FRAME|TITLE',
    re.IGNORECASE,
)

SKELETON_TYPES = {'LINE', 'LWPOLYLINE', 'ARC'}


class Seg:
    __slots__ = ('x0', 'y0', 'x1', 'y1', 'layer', 'etype')
    def __init__(self, x0, y0, x1, y1, layer='', etype='LINE'):
        self.x0, self.y0 = float(x0), float(y0)
        self.x1, self.y1 = float(x1), float(y1)
        self.layer = layer
        self.etype = etype
    def length(self):
        return math.hypot(self.x1-self.x0, self.y1-self.y0)


def extract(dxf_path):
    doc = ezdxf.readfile(dxf_path, encoding='cp949')
    msp = doc.modelspace()
    segs = []

    def proc(e, depth=0):
        if depth > 6:
            return
        et = e.dxftype()
        if et == 'INSERT':
            try:
                for sub in e.virtual_entities():
                    proc(sub, depth+1)
            except:
                pass
            return
        layer = '0'
        try:
            layer = e.dxf.layer or '0'
        except:
            pass
        if not PKG_KEEP_PAT.search(layer):
            return
        if SKIP_PAT.search(layer):
            return
        if et not in SKELETON_TYPES:
            return
        try:
            if et == 'LINE':
                s, en = e.dxf.start, e.dxf.end
                seg = Seg(s.x, s.y, en.x, en.y, layer, 'LINE')
                if seg.length() >= 1.0:
                    segs.append(seg)
            elif et == 'LWPOLYLINE':
                pts = list(e.get_points())
                is_closed = bool(e.dxf.flags & 1)
                for i in range(len(pts)-1):
                    seg = Seg(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1], layer, 'LW')
                    if seg.length() >= 1.0:
                        segs.append(seg)
                if is_closed and len(pts) >= 2:
                    seg = Seg(pts[-1][0], pts[-1][1], pts[0][0], pts[0][1], layer, 'LW')
                    if seg.length() >= 1.0:
                        segs.append(seg)
        except:
            pass

    for e in msp:
        proc(e)
    return segs


def find_nearest_gap(segs, target_layer_pat):
    """target_layer 선분의 각 끝점에서 다른 선분까지 최소 거리 분포."""
    target_pat = re.compile(target_layer_pat, re.IGNORECASE)

    # 전체 끝점 수집 (격자)
    GRID = 500.0
    grid = defaultdict(list)
    all_endpoints = []
    for i, seg in enumerate(segs):
        for pt in [(seg.x0, seg.y0), (seg.x1, seg.y1)]:
            idx = len(all_endpoints)
            all_endpoints.append((pt[0], pt[1], i))
            gx, gy = int(pt[0]//GRID), int(pt[1]//GRID)
            grid[(gx,gy)].append(idx)

    gaps = []
    for seg in segs:
        if not target_pat.search(seg.layer):
            continue
        for pt in [(seg.x0, seg.y0), (seg.x1, seg.y1)]:
            x, y = pt
            gx, gy = int(x//GRID), int(y//GRID)
            min_dist = float('inf')
            for dgx in range(-2, 3):
                for dgy in range(-2, 3):
                    for idx in grid[(gx+dgx, gy+dgy)]:
                        nx, ny, ni = all_endpoints[idx]
                        if segs[ni] is seg:
                            continue
                        d = math.hypot(x-nx, y-ny)
                        if d < min_dist:
                            min_dist = d
            if min_dist < float('inf'):
                gaps.append(min_dist)

    return gaps


if __name__ == '__main__':
    print('지하주차장 보 중심선 gap 분석...')
    segs = extract(DXF_PKG)
    print(f'총 추출: {len(segs):,}')

    # 00_BEAM 레이어 gap 분석
    print('\n[00_BEAM] 끝점 gap 분포:')
    gaps_beam = find_nearest_gap(segs, r'^00_BEAM$')
    if gaps_beam:
        gaps_beam.sort()
        n = len(gaps_beam)
        print(f'  끝점 수: {n}')
        print(f'  min={gaps_beam[0]:.1f}  max={gaps_beam[-1]:.1f}')
        print(f'  p25={gaps_beam[n//4]:.1f}  p50={gaps_beam[n//2]:.1f}  p75={gaps_beam[3*n//4]:.1f}')
        for thresh in [5, 10, 20, 50, 100, 200, 500]:
            cnt = sum(1 for g in gaps_beam if g <= thresh)
            print(f'  gap <= {thresh:4d}mm: {cnt:5d}개 ({100*cnt//n}%)')

    # 00_SHEAR_WALL gap 분석
    print('\n[00_SHEAR WALL] 끝점 gap 분포:')
    gaps_sw = find_nearest_gap(segs, r'^00_SHEAR.WALL$')
    if gaps_sw:
        gaps_sw.sort()
        n = len(gaps_sw)
        print(f'  끝점 수: {n}')
        print(f'  min={gaps_sw[0]:.1f}  max={gaps_sw[-1]:.1f}')
        for thresh in [5, 10, 20, 50, 100]:
            cnt = sum(1 for g in gaps_sw if g <= thresh)
            print(f'  gap <= {thresh:4d}mm: {cnt:5d}개 ({100*cnt//n}%)')

    # 101동 XRef RC벽 gap 분석
    print('\n\n=== 101동 XRef RC벽 gap 분석 ===')
    DXF_DONG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
    DONG_KEEP_PAT = re.compile(
        r'^S-GIRDER$|^S-BEAM$|^S-PC-GIRDER$|^S-PC-SLAB$'
        r'|^A-WALL-RC$|^A-WALL-BRICK$'
        r'|^00_SHEAR.WALL$|^00_SLAB.END'
        r'|A-WALL-RC|A-WALL-BRICK|A-COL',
        re.IGNORECASE,
    )
    # reuse extract with patched pattern
    old_pat = PKG_KEEP_PAT
    import tests.analyze_beam_gap as _self
    _self.PKG_KEEP_PAT = DONG_KEEP_PAT
    dong_segs = extract(DXF_DONG)
    print(f'총 추출: {len(dong_segs):,}')
    gaps_rc = find_nearest_gap(dong_segs, r'A-WALL-RC')
    if gaps_rc:
        gaps_rc.sort()
        n = len(gaps_rc)
        print(f'  끝점 수: {n}')
        print(f'  min={gaps_rc[0]:.1f}  max={gaps_rc[-1]:.1f}')
        for thresh in [5, 10, 20, 50, 100, 200]:
            cnt = sum(1 for g in gaps_rc if g <= thresh)
            print(f'  gap <= {thresh:4d}mm: {cnt:5d}개 ({100*cnt//n}%)')
