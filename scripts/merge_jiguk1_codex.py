"""
1지국 1,163 부재 법전 → 본 강역 자산 DB 통합

방부장 친명 (2026-05-05): "앞서간 1지국의 도움을 최대한 받으라"

소스: D:/Git/BOQ_2/sketchup_plugins/boq_member_specs.json
적재: jiguk3_assets.db members (region = JIGUK1_<member_type>)
"""

import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core import asset_db

CODEX_PATH = r"d:/Git/BOQ_2/sketchup_plugins/boq_member_specs.json"

with open(CODEX_PATH, encoding='utf-8') as f:
    codex = json.load(f)

# 한글 부재명 → member_type
MEMBER_MAP = {
    '보': 'BEAM',
    '기둥': 'COLUMN',
    '슬라브': 'SLAB',
    '벽체': 'WALL',
    '기초': 'FOUNDATION',
    '테두리보': 'BEAM',  # 테두리보도 보로 분류
}

# 강역(territory) — 1지국 법전은 별도 영역
jiguk1_id = asset_db.ensure_territory(
    name="1지국 통합 법전 (BOQ_2)",
    description="1지국 정도전이 다년간 정리한 1163종 부재 법전. 기둥-보 라멘구조 위주.",
    base_path=r"D:/Git/BOQ_2/sketchup_plugins",
)

stats = {'BEAM': 0, 'COLUMN': 0, 'SLAB': 0, 'WALL': 0, 'FOUNDATION': 0, 'UNKNOWN': 0}
inserted = 0
for s in codex:
    member_type = MEMBER_MAP.get(s.get('member'), 'UNKNOWN')
    stats[member_type] += 1
    if member_type == 'UNKNOWN':
        continue
    region = f"JIGUK1_{member_type}"
    code = s['symbol']
    width = s.get('width') or 0
    height = s.get('height') or 0
    thickness = s.get('thickness') or 0
    depth = s.get('depth') or 0
    wall_thk = s.get('wallThk') or 0

    # 슬라브: thickness 또는 depth
    eff_thickness = thickness or depth
    # 벽체: wallThk 또는 thickness
    if member_type == 'WALL':
        eff_thickness = wall_thk or thickness
    asset_db.insert_member(
        territory_id=jiguk1_id,
        region=region,
        code=code,
        member_type=member_type,
        width=width if width else None,
        height=height if height else None,
        thickness=eff_thickness if eff_thickness else None,
    )
    inserted += 1

print(f"[1지국 법전 통합]")
for k, v in stats.items():
    print(f"  {k}: {v}종")
print(f"  적재: {inserted}/{len(codex)}")

print()
print("=== 자산 DB 최종 통계 ===")
for table, cnt in asset_db.stats().items():
    print(f"  {table}: {cnt}")

# 슬라브 영역 분포
print()
print("=== 슬라브 분포 (전체 강역) ===")
for r in asset_db.query("""
    SELECT t.name AS territory, m.region, COUNT(*) AS n
    FROM members m JOIN territories t ON m.territory_id = t.id
    WHERE m.member_type = 'SLAB' GROUP BY t.name, m.region
"""):
    print(f"  {r['territory']} | {r['region']}: {r['n']}종")
