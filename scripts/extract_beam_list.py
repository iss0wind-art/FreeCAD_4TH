"""
보 리스트 채굴 — 지하주차장 보 일람표

대상: S40-151~156 지하주차장 보 리스트.dxf (6.3 MB, 일반 TEXT)

기둥 리스트와 형식 다를 수 있음 — 보는 보통 상부근/하부근 구분
"""

import os, re, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF_PATH = r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S40-151~156 지하주차장 보 리스트.dxf"
OUT_JSON = "output/codex_beams_basement.json"
OUT_MD   = "output/codex_beams_basement.md"

import ezdxf

# 패턴
SECTION_RE = re.compile(r'\(?\s*(\d{3,4})\s*[xX×]\s*(\d{3,4})\s*\)?')
MAIN_BAR_RE = re.compile(r'^(\d{1,2})-(D\d{2})$')
HOOP_RE = re.compile(r'^(D\d{1,2})@(\d{2,3})$')
# 보 코드: G1, G2, B1, B2, RG1, RG2, EG, REG, AG 등 매우 다양
BEAM_CODE_RE = re.compile(r'^(R?[BGE]G?\d+[A-Z]?)$|^([BGE][A-Z]?\d+[A-Z]?)$')

def get_all_text(msp):
    items = []
    for e in msp:
        if e.dxftype() == 'TEXT':
            try:
                items.append({'text': e.dxf.text.strip(), 'x': e.dxf.insert.x, 'y': e.dxf.insert.y})
            except: pass
        elif e.dxftype() == 'MTEXT':
            try:
                items.append({'text': e.text.strip(), 'x': e.dxf.insert.x, 'y': e.dxf.insert.y})
            except: pass
        elif e.dxftype() == 'INSERT':
            try:
                for sub in e.virtual_entities():
                    if sub.dxftype() in ('TEXT', 'MTEXT'):
                        items.append({
                            'text': (sub.dxf.text if sub.dxftype() == 'TEXT' else sub.text).strip(),
                            'x': sub.dxf.insert.x, 'y': sub.dxf.insert.y,
                        })
            except: pass
    return items

doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()
texts = get_all_text(msp)
print(f"[TEXT] 총 {len(texts)}개")

# 패턴 분포 미리 확인
from collections import Counter
patterns = Counter()
samples_by_pattern = {}
for t in texts:
    txt = t['text']
    if not txt: continue
    if SECTION_RE.search(txt):
        patterns['SECTION'] += 1
        samples_by_pattern.setdefault('SECTION', []).append(txt)
    elif MAIN_BAR_RE.match(txt):
        patterns['MAIN_BAR'] += 1
        samples_by_pattern.setdefault('MAIN_BAR', []).append(txt)
    elif HOOP_RE.match(txt):
        patterns['HOOP'] += 1
        samples_by_pattern.setdefault('HOOP', []).append(txt)
    elif BEAM_CODE_RE.match(txt):
        patterns['BEAM_CODE'] += 1
        samples_by_pattern.setdefault('BEAM_CODE', []).append(txt)
    elif re.match(r'^[A-Z]+\s*\d+', txt):
        patterns['OTHER_CODE'] += 1
        samples_by_pattern.setdefault('OTHER_CODE', []).append(txt)

print(f"[패턴 분포] {dict(patterns)}")
for k, samples in samples_by_pattern.items():
    print(f"  {k} 샘플: {samples[:8]}")

# 분류
classified = []
for it in texts:
    txt = it['text']
    if not txt: continue
    m = SECTION_RE.search(txt)
    if m:
        classified.append({**it, 'kind': 'SECTION', 'width': int(m.group(1)), 'height': int(m.group(2))})
        continue
    m = MAIN_BAR_RE.match(txt)
    if m:
        classified.append({**it, 'kind': 'MAIN_BAR', 'count': int(m.group(1)), 'rebar': m.group(2)})
        continue
    m = HOOP_RE.match(txt)
    if m:
        classified.append({**it, 'kind': 'HOOP', 'rebar': m.group(1), 'spacing': int(m.group(2))})
        continue
    m = BEAM_CODE_RE.match(txt)
    if m:
        classified.append({**it, 'kind': 'CODE', 'symbol': txt})

# 코드 → 인접 자료 매핑 (기둥 리스트와 동일 알고리즘)
codes = [c for c in classified if c['kind'] == 'CODE']
sections = [c for c in classified if c['kind'] == 'SECTION']
mains = [c for c in classified if c['kind'] == 'MAIN_BAR']
hoops = [c for c in classified if c['kind'] == 'HOOP']

def find_nearest(target, candidates, max_dx=10000, max_dy=5000):
    best, best_d = None, float('inf')
    for c in candidates:
        dx = abs(c['x'] - target['x'])
        dy = abs(c['y'] - target['y'])
        if dx > max_dx or dy > max_dy: continue
        d = dx + dy * 2
        if d < best_d:
            best_d = d; best = c
    return best

beams = []
for code in codes:
    sec = find_nearest(code, sections)
    main = find_nearest(code, mains)
    hoop = find_nearest(code, hoops)
    beams.append({
        'symbol': code['symbol'],
        'pos': (code['x'], code['y']),
        'width': sec['width'] if sec else None,
        'height': sec['height'] if sec else None,
        'main_bar': f"{main['count']}-{main['rebar']}" if main else None,
        'hoop': f"{hoop['rebar']}@{hoop['spacing']}" if hoop else None,
    })

# 중복 제거
seen = {}
for b in beams:
    if b['symbol'] not in seen:
        seen[b['symbol']] = b
unique = sorted(seen.values(), key=lambda x: x['symbol'])

print(f"\n[채굴] 보 코드 {len(codes)}개 인스턴스 → 고유 {len(unique)}종")
for b in unique[:30]:
    print(f"  {b['symbol']:8s} {b['width'] or '-'}x{b['height'] or '-'}  주근:{b['main_bar'] or '-'}  후프:{b['hoop'] or '-'}")

os.makedirs("output", exist_ok=True)
with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump({'강역': '부산 에코델타 24BL', '도면': os.path.basename(DXF_PATH),
               '부재_종류': 'BEAM (지하주차장)', '고유_부재_수': len(unique), '부재_법전': unique},
              f, ensure_ascii=False, indent=2, default=str)

md = []
md.append(f"# 보 법전 — 지하주차장\n")
md.append(f"> 도면: `{os.path.basename(DXF_PATH)}` | 채굴 {len(unique)}종\n")
md.append("| 코드 | W (mm) | H (mm) | 주근 | 후프 |")
md.append("|------|-------:|-------:|------|------|")
for b in unique:
    md.append(f"| {b['symbol']} | {b['width'] or '-'} | {b['height'] or '-'} | {b['main_bar'] or '-'} | {b['hoop'] or '-'} |")
with open(OUT_MD, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md))

print(f"\n[저장] {OUT_JSON}")
print(f"[저장] {OUT_MD}")
print("완료.")
