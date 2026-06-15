import os
import sys
from pathlib import Path
from core.v2.inspect.meta_pipeline import inspect
from core.v2.coords.grid_resolver import resolve_grid_per_sheet
from core.v2.coords.anchor_finder import find_canonical_anchors

dxf_path = Path("D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf")

print(f"--- [징검다리 정렬 시뮬레이션] ---")
meta = inspect(dxf_path)
grids = resolve_grid_per_sheet(meta)
anchors = find_canonical_anchors(meta, grids)

# 징검다리 검증: 모든 시트가 하나의 '글로벌 좌표계'로 수렴했는가?
# 시뮬레이션: 시트별 (tx, ty) 오프셋을 적용했을 때, 공통된 격자들의 전역 좌표가 일치해야 함.

global_grid_positions = {} # label -> [(sid, gx, gy)]

for sid, g in grids.items():
    anchor = anchors[sid]
    ref_anchor = anchors[list(grids.keys())[0]] # 기준 시트 (0,0)
    tx = ref_anchor.x - anchor.x
    ty = ref_anchor.y - anchor.y
    
    for label, cad_x in g.x_lines.items():
        gx = cad_x + tx
        global_grid_positions.setdefault(label, []).append((sid, gx))
        
print(f"1. 전역 격자 매칭 결과:")
for label, pos_list in sorted(global_grid_positions.items()):
    if len(pos_list) > 1:
        xs = [p[1] for p in pos_list]
        avg_x = sum(xs) / len(xs)
        max_err = max(abs(x - avg_x) for x in xs)
        status = "PERFECT" if max_err < 1 else "OK" if max_err < 100 else "FAIL"
        print(f"   - {label:4}: {len(pos_list)} sheets matched. Max Error={max_err:8.2f}mm [{status}]")

# 연결성 체크
connected_sheets = set()
for label, pos_list in global_grid_positions.items():
    if len(pos_list) > 1:
        for sid, _ in pos_list:
            connected_sheets.add(sid)

print(f"2. 전체 연결성: {len(connected_sheets)} / {len(meta.sheets)} sheets connected.")

if len(connected_sheets) == len(meta.sheets):
    print("\n[SUCCESS] 모든 층이 징검다리처럼 완벽하게 연결되었습니다!")
else:
    print(f"\n[FAILURE] {len(meta.sheets) - len(connected_sheets)}개 층이 고립되어 있습니다.")

print(f"--- [시뮬레이션 종료] ---")
