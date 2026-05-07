"""
analyze_isolated.py -- 고립 선분 분석
=======================================
지하주차장 고립 11,230개의 원인 파악.
레이어별 분포 + 길이 분포 + 위치 분포 확인.
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
SNAP_TOL = 5.0


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
            elif et == 'ARC':
                c = e.dxf.center
                r = e.dxf.radius
                import math as _m
                a_s = _m.radians(e.dxf.start_angle)
                a_e = _m.radians(e.dxf.end_angle)
                x0 = c.x + r * _m.cos(a_s)
                y0 = c.y + r * _m.sin(a_s)
                x1 = c.x + r * _m.cos(a_e)
                y1 = c.y + r * _m.sin(a_e)
                seg = Seg(x0, y0, x1, y1, layer, 'ARC')
                if seg.length() >= 1.0:
                    segs.append(seg)
        except:
            pass

    for e in msp:
        proc(e)
    return segs


def check_connectivity(segments):
    grid_size = SNAP_TOL * 2
    grid = defaultdict(list)
    endpoints = []
    for seg in segments:
        endpoints.append((seg.x0, seg.y0))
        endpoints.append((seg.x1, seg.y1))
    for idx, (x, y) in enumerate(endpoints):
        gx, gy = int(x // grid_size), int(y // grid_size)
        grid[(gx, gy)].append(idx)

    def has_neighbor(x, y, excl):
        gx, gy = int(x // grid_size), int(y // grid_size)
        for dgx in range(-1, 2):
            for dgy in range(-1, 2):
                for idx in grid[(gx+dgx, gy+dgy)]:
                    if idx == excl:
                        continue
                    nx, ny = endpoints[idx]
                    if math.hypot(x-nx, y-ny) < SNAP_TOL:
                        return True
        return False

    connected, isolated = [], []
    for i, seg in enumerate(segments):
        hs = has_neighbor(seg.x0, seg.y0, i*2)
        he = has_neighbor(seg.x1, seg.y1, i*2+1)
        if hs or he:
            connected.append(seg)
        else:
            isolated.append(seg)
    return connected, isolated


if __name__ == '__main__':
    print('지하주차장 고립 선분 분석...')
    segs = extract(DXF_PKG)
    print(f'총 추출: {len(segs):,}')

    _, isolated = check_connectivity(segs)
    print(f'고립: {len(isolated):,}')

    # 레이어별 분포
    by_layer = defaultdict(int)
    for s in isolated:
        by_layer[s.layer] += 1
    print('\n고립 선분 레이어별:')
    for lyr, cnt in sorted(by_layer.items(), key=lambda x: -x[1]):
        print(f'  {lyr:<50} {cnt:>5}')

    # 길이 분포
    lengths = [s.length() for s in isolated]
    lengths.sort()
    n = len(lengths)
    print(f'\n고립 선분 길이 분포:')
    print(f'  min={lengths[0]:.1f}  max={lengths[-1]:.1f}')
    print(f'  p25={lengths[n//4]:.1f}  p50={lengths[n//2]:.1f}  p75={lengths[3*n//4]:.1f}')

    # 짧은 선분 (< 100mm)
    short = [s for s in isolated if s.length() < 100]
    print(f'  < 100mm: {len(short)}개 ({100*len(short)//max(1,n)}%)')

    # X,Y 범위
    xs = [s.x0 for s in isolated] + [s.x1 for s in isolated]
    ys = [s.y0 for s in isolated] + [s.y1 for s in isolated]
    print(f'\n고립 선분 좌표 범위:')
    print(f'  X: {min(xs):.0f} ~ {max(xs):.0f}')
    print(f'  Y: {min(ys):.0f} ~ {max(ys):.0f}')

    # 101동도 확인
    print('\n\n--- 101동 고립 분석 ---')
    DXF_DONG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'

    DONG_KEEP_PAT = re.compile(
        r'^S-GIRDER$|^S-BEAM$|^S-PC-GIRDER$|^S-PC-SLAB$'
        r'|^A-WALL-RC$|^A-WALL-BRICK$'
        r'|^00_SHEAR.WALL$|^00_SLAB.END'
        r'|^00_FOUNDATION$|^00_REINFORCE.BAR$'
        r'|A-WALL-RC'
        r'|A-WALL-BRICK'
        r'|A-COL$|A-COL\b',
        re.IGNORECASE,
    )

    import importlib.util, types
    # 간단히 PKG_KEEP_PAT를 DONG으로 바꿔 재실행
    PKG_KEEP_PAT_backup = PKG_KEEP_PAT
    # monkey-patch
    import tests.analyze_isolated as _self
    _self.PKG_KEEP_PAT = DONG_KEEP_PAT

    dong_segs = extract(DXF_DONG)
    print(f'총 추출: {len(dong_segs):,}')
    _, dong_iso = check_connectivity(dong_segs)
    print(f'고립: {len(dong_iso):,}')
    by_layer2 = defaultdict(int)
    for s in dong_iso:
        by_layer2[s.layer] += 1
    print('고립 선분 레이어별:')
    for lyr, cnt in sorted(by_layer2.items(), key=lambda x: -x[1]):
        print(f'  {lyr:<50} {cnt:>5}')

    lengths2 = sorted([s.length() for s in dong_iso])
    n2 = len(lengths2)
    if n2 > 0:
        print(f'길이: min={lengths2[0]:.1f} max={lengths2[-1]:.1f} '
              f'p50={lengths2[n2//2]:.1f}')
        short2 = [s for s in dong_iso if s.length() < 100]
        print(f'< 100mm: {len(short2)}개 ({100*len(short2)//max(1,n2)}%)')
