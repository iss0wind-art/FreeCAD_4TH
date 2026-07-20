# -*- coding: utf-8 -*-
"""코어(계단실·EV) 내부 해치를 걸러낸 화장실 후보만 내보낸다."""
import sys, json
from collections import Counter
from shapely.geometry import Polygon, Point
sys.stdout.reconfigure(encoding='utf-8')
H = json.load(open(r'D:\Git\BOQ_2\.bridge\hatch_TYP.json', encoding='utf-8'))
F = json.load(open(r'D:\Git\FreeCAD_4TH\.claude\worktrees\slab-precision-2026-07\output\slab_fill_101동.json', encoding='utf-8'))['TYP']
cores = [Polygon([(p[0], p[1]) for p in c['ring_rel']]) for c in F['cuts']]

kept, dropped_core, dropped_small = [], [], []
for h in H:
    p = Point(h['x'], h['y'])
    if any(c.contains(p) for c in cores):
        dropped_core.append(h)                 # 계단실·EV 내부 표기 — 화장실 아님
    elif h['a'] < 2.0:
        dropped_small.append(h)                # 2㎡ 미만 — 벽체 단면 등
    else:
        kept.append(h)
json.dump(kept, open(r'D:\Git\BOQ_2\.bridge\hatch_TYP_filtered.json', 'w', encoding='utf-8'),
          ensure_ascii=False)
print(f'해치 {len(H)}개')
print(f'  제외: 코어내부 {len(dropped_core)} + 소형(<2㎡) {len(dropped_small)}')
print(f'  남음: {len(kept)}개  면적분포 {dict(Counter(round(h["a"],2) for h in kept))}')
print(f'  SL부호 곁: {sum(1 for h in kept if h["sl"])}/{len(kept)}')
