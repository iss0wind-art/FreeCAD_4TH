"""
청 2 자력 채굴 PoC — 기둥 리스트 정밀 추출

대상: S30-471~491 101~112동 기둥리스트.dxf (5.5 MB)

목표:
1. 기둥 코드(TC1, TC2, ...) → 단면(W×H) 자동 매핑
2. 배근 정보 (주근, 후프) 추출
3. 검증: TEXT 추출 + LWPOLYLINE 단면 면적 이중 확인
4. 산출: JSON + Markdown
"""

import os, re, json, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF_PATH = r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S30-471~491 101~112동 기둥리스트.dxf"
OUT_JSON = "output/codex_columns_101_112.json"
OUT_MD   = "output/codex_columns_101_112.md"

import ezdxf
doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()

# ── 1. 모든 TEXT 추출 (위치 + 내용) ─────────────────────────
def get_all_text(msp):
    items = []
    for e in msp:
        if e.dxftype() == 'TEXT':
            try:
                items.append({
                    'text': e.dxf.text.strip(),
                    'x': e.dxf.insert.x,
                    'y': e.dxf.insert.y,
                    'h': e.dxf.height,
                })
            except: pass
        elif e.dxftype() == 'MTEXT':
            try:
                items.append({
                    'text': e.text.strip(),
                    'x': e.dxf.insert.x,
                    'y': e.dxf.insert.y,
                    'h': e.dxf.char_height,
                })
            except: pass
        elif e.dxftype() == 'INSERT':
            try:
                for sub in e.virtual_entities():
                    if sub.dxftype() in ('TEXT', 'MTEXT'):
                        items.append({
                            'text': (sub.dxf.text if sub.dxftype() == 'TEXT' else sub.text).strip(),
                            'x': sub.dxf.insert.x,
                            'y': sub.dxf.insert.y,
                            'h': sub.dxf.height if sub.dxftype() == 'TEXT' else sub.dxf.char_height,
                        })
            except: pass
    return items

texts = get_all_text(msp)
print(f"[TEXT] 총 {len(texts)}개")

# ── 2. 패턴 매칭으로 분류 ───────────────────────────────────
# 기둥 코드: TC1, TC2, ... (-2~1TC1 같은 층 표기 포함)
COL_CODE_RE = re.compile(r'^-?\d*~?\d*\s*([TBC]?C\d+[A-Z]?)$')
# 단면: ( 600 x 1200 ) 또는 (600x1200)
SECTION_RE = re.compile(r'\(\s*(\d{3,4})\s*[xX]\s*(\d{3,4})\s*\)')
# 주근: 20-D25, 16-D29 등
MAIN_BAR_RE = re.compile(r'^(\d{1,2})-(D\d{2})$')
# 후프: D10@150
HOOP_RE = re.compile(r'^(D\d{1,2})@(\d{2,3})$')

def classify_text(item):
    t = item['text']
    # 기둥 코드: -2~1TC1 같은 형태 — '-2~1' 부분 떼고 TC# 추출
    m_code = re.search(r'(\d+)\s*~\s*(\d+)\s*([TBC]?C\d+[A-Z]?)', t)
    if m_code:
        return ('CODE', {
            'floor_from': int(m_code.group(1)),
            'floor_to': int(m_code.group(2)),
            'symbol': m_code.group(3),
        })
    # 또는 단순 TC1
    if re.match(r'^([TBC]?C\d+[A-Z]?)$', t):
        return ('CODE', {'symbol': t, 'floor_from': None, 'floor_to': None})
    # 단면
    m_sec = SECTION_RE.search(t)
    if m_sec:
        return ('SECTION', {'width': int(m_sec.group(1)), 'height': int(m_sec.group(2))})
    # 주근
    m_main = MAIN_BAR_RE.match(t)
    if m_main:
        return ('MAIN_BAR', {'count': int(m_main.group(1)), 'rebar': m_main.group(2)})
    # 후프
    m_hoop = HOOP_RE.match(t)
    if m_hoop:
        return ('HOOP', {'rebar': m_hoop.group(1), 'spacing': int(m_hoop.group(2))})
    # 헤더 (NAME, SECTION, MAIN BAR, HOOP)
    if t in ('NAME', 'SECTION', 'MAIN BAR', 'HOOP ( MID )', 'HOOP ( END )'):
        return ('HEADER', {'label': t})
    return None

classified = []
for it in texts:
    c = classify_text(it)
    if c:
        kind, data = c
        classified.append({**it, 'kind': kind, **data})

# 통계
from collections import Counter
kinds = Counter(c['kind'] for c in classified)
print(f"[분류] {dict(kinds)}")

# ── 3. 위치 기반 그룹핑: 같은 행(같은 y)의 부재 통합 ──────────
# 일람표는 보통 가로 행마다 한 부재
codes = [c for c in classified if c['kind'] == 'CODE']
print(f"\n[기둥 코드] {len(codes)}개")
for c in codes[:10]:
    fr = c.get('floor_from'); to = c.get('floor_to')
    floor = f'{fr}~{to}' if fr is not None else '-'
    print(f"  {c['symbol']:8s} ({floor}) @ ({c['x']:.0f}, {c['y']:.0f})")

# 코드와 가까운 (행 ±h*3 이내) 단면·주근·후프 매칭
def find_nearest_below(target, candidates, max_dx=20000, max_dy=15000):
    """target 좌표 아래·옆쪽에서 가장 가까운 것 찾기 (일람표 가로형 가정)"""
    best, best_d = None, float('inf')
    for c in candidates:
        dx = abs(c['x'] - target['x'])
        dy = abs(c['y'] - target['y'])
        if dx > max_dx or dy > max_dy: continue
        d = dx + dy * 2  # y 차이를 더 가중
        if d < best_d:
            best_d = d; best = c
    return best

sections = [c for c in classified if c['kind'] == 'SECTION']
mains = [c for c in classified if c['kind'] == 'MAIN_BAR']
hoops = [c for c in classified if c['kind'] == 'HOOP']

print(f"\n[자료] 단면 {len(sections)}, 주근 {len(mains)}, 후프 {len(hoops)}")

# 각 코드에 단면·주근·후프 매핑
columns = []
for code in codes:
    sec = find_nearest_below(code, sections, max_dx=10000, max_dy=5000)
    main = find_nearest_below(code, mains, max_dx=10000, max_dy=5000)
    hoop = find_nearest_below(code, hoops, max_dx=10000, max_dy=5000)
    columns.append({
        'symbol': code['symbol'],
        'floor_range': f"{code.get('floor_from')}~{code.get('floor_to')}",
        'pos': (code['x'], code['y']),
        'width': sec['width'] if sec else None,
        'height': sec['height'] if sec else None,
        'main_bar': f"{main['count']}-{main['rebar']}" if main else None,
        'hoop': f"{hoop['rebar']}@{hoop['spacing']}" if hoop else None,
    })

# 중복 제거: 같은 symbol 중 첫번째만
seen = {}
for c in columns:
    key = (c['symbol'], c['floor_range'])
    if key not in seen:
        seen[key] = c
unique_columns = list(seen.values())
unique_columns.sort(key=lambda c: (c['floor_range'], c['symbol']))

print(f"\n[채굴] 고유 기둥 {len(unique_columns)}종")
for c in unique_columns[:20]:
    w = c['width'] or '-'; h = c['height'] or '-'
    mb = c['main_bar'] or '-'; ho = c['hoop'] or '-'
    print(f"  {c['symbol']:8s} ({c['floor_range']}) {w}x{h}mm  주근:{mb}  후프:{ho}")

# ── 4. 산출 ─────────────────────────────────────────────────
os.makedirs("output", exist_ok=True)
result = {
    '강역': '부산 에코델타 24BL',
    '도면': os.path.basename(DXF_PATH),
    '부재_종류': 'COLUMN',
    '동_범위': '101~112동',
    '총_텍스트': len(texts),
    '분류된_텍스트': len(classified),
    '고유_부재_수': len(unique_columns),
    '부재_법전': unique_columns,
}
with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)

# Markdown
md = []
md.append(f"# 부재 법전 채굴 — 101~112동 기둥 리스트\n")
md.append(f"> 도면: `{os.path.basename(DXF_PATH)}` | 채굴: {len(unique_columns)}종\n")
md.append("## 기둥 일람\n")
md.append("| 코드 | 층 범위 | W (mm) | H (mm) | 주근 | 후프 |")
md.append("|------|---------|-------:|-------:|------|------|")
for c in unique_columns:
    md.append(f"| {c['symbol']} | {c['floor_range']} | {c['width'] or '-'} | {c['height'] or '-'} | {c['main_bar'] or '-'} | {c['hoop'] or '-'} |")

with open(OUT_MD, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md))

print(f"\n[저장] {OUT_JSON}")
print(f"[저장] {OUT_MD}")
print("완료.")
