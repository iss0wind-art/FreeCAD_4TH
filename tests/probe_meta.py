"""A1·A2 메타 정독 — wall_pairs 활용 가능 여부 확인."""
import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

m1 = json.load(open(r'D:/Git/FreeCAD_4TH/output/poc_101_b1_b2_dong.json', encoding='utf-8'))
m2 = json.load(open(r'D:/Git/FreeCAD_4TH/output/poc_101_around_parking.json', encoding='utf-8'))

print('=== A1 (101동 동체) ===')
for s in m1.get('sheets', []):
    print(f"sheet={s.get('sheet_id')} floor={s.get('floor')}")
    for k in ['n_lines_input','n_wall_pairs','n_boxes_input','classification_stats']:
        print(f'  {k}: {s.get(k)}')
    print(f"  columns 3d: {len(s.get('columns', []))}, girders 3d: {len(s.get('girders', []))}")
print()
print('=== A2 (주변 주차장) ===')
for s in m2.get('sheets', []):
    print(f"sheet={s.get('sheet_id')} floor={s.get('floor')}")
    for k in s.keys():
        if k in ('columns','girders'):
            print(f'  {k}: list len={len(s[k])}')
            continue
        v = s[k]
        if isinstance(v, list): print(f'  {k}: list len={len(v)}')
        elif isinstance(v, dict): print(f'  {k}: dict')
        else: print(f'  {k}: {v}')
