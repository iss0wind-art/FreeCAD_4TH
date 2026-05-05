"""
기둥 리스트 일괄 채굴 — 통합 부재 법전 시드

PoC(poc_column_list.py)에서 검증된 알고리즘을 3장 기둥 리스트에 일괄 적용.

대상:
- S30-471~491 101~112동 기둥리스트
- S30-492~507 113~116동 기둥리스트
- S40-111~112 지하주차장 기둥 리스트
"""

import os, re, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DXF_FILES = [
    (r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S30-471~491 101~112동 기둥리스트.dxf", "101~112동"),
    (r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S30-492~507 113~116동 기둥리스트.dxf", "113~116동"),
    (r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S40-111~112 지하주차장 기둥 리스트.dxf", "지하주차장"),
]

OUT_JSON = "output/codex_columns_unified.json"
OUT_MD   = "output/codex_columns_unified.md"

import ezdxf

# 패턴 (PoC와 동일)
SECTION_RE = re.compile(r'\(\s*(\d{3,4})\s*[xX]\s*(\d{3,4})\s*\)')
MAIN_BAR_RE = re.compile(r'^(\d{1,2})-(D\d{2})$')
HOOP_RE = re.compile(r'^(D\d{1,2})@(\d{2,3})$')

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

def classify(item):
    t = item['text']
    m_code = re.search(r'(-?\d+)\s*~\s*(-?\d+)\s*([TBC]?C\d+[A-Z]?)', t)
    if m_code:
        return ('CODE', {'floor_from': int(m_code.group(1)), 'floor_to': int(m_code.group(2)), 'symbol': m_code.group(3)})
    if re.match(r'^([TBC]?C\d+[A-Z]?)$', t):
        return ('CODE', {'symbol': t, 'floor_from': None, 'floor_to': None})
    m_sec = SECTION_RE.search(t)
    if m_sec:
        return ('SECTION', {'width': int(m_sec.group(1)), 'height': int(m_sec.group(2))})
    m_main = MAIN_BAR_RE.match(t)
    if m_main:
        return ('MAIN_BAR', {'count': int(m_main.group(1)), 'rebar': m_main.group(2)})
    m_hoop = HOOP_RE.match(t)
    if m_hoop:
        return ('HOOP', {'rebar': m_hoop.group(1), 'spacing': int(m_hoop.group(2))})
    return None

def process_file(path, label):
    doc = ezdxf.readfile(path, encoding='cp949')
    msp = doc.modelspace()
    texts = get_all_text(msp)
    classified = []
    for it in texts:
        c = classify(it)
        if c:
            kind, data = c
            classified.append({**it, 'kind': kind, **data})

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

    columns = []
    for code in codes:
        sec = find_nearest(code, sections)
        main = find_nearest(code, mains)
        hoop = find_nearest(code, hoops)
        columns.append({
            'source': label,
            'symbol': code['symbol'],
            'floor_from': code.get('floor_from'),
            'floor_to': code.get('floor_to'),
            'width': sec['width'] if sec else None,
            'height': sec['height'] if sec else None,
            'main_bar': f"{main['count']}-{main['rebar']}" if main else None,
            'hoop': f"{hoop['rebar']}@{hoop['spacing']}" if hoop else None,
        })

    # 중복 제거
    seen = {}
    for c in columns:
        key = (c['symbol'], c['floor_from'], c['floor_to'])
        if key not in seen:
            seen[key] = c
    return list(seen.values()), len(texts), len(classified)

def main():
    all_columns = []
    summary = []
    for path, label in DXF_FILES:
        if not os.path.exists(path):
            print(f"[건너뜀] {label}: 파일 없음")
            continue
        print(f"[처리 중] {label} - {os.path.basename(path)}")
        cols, total_text, classified = process_file(path, label)
        print(f"  TEXT {total_text} → 분류 {classified} → 고유 {len(cols)}종")
        all_columns.extend(cols)
        summary.append({'label': label, 'total_text': total_text, 'classified': classified, 'unique': len(cols)})

    # 통합 (source 다른 곳에서 같은 symbol → 다른 항목)
    print(f"\n[통합] 총 기둥 부재: {len(all_columns)}종")

    os.makedirs("output", exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({
            '강역': '부산 에코델타 24BL',
            '부재_종류': 'COLUMN',
            '소스_도면_수': len(summary),
            '통합_법전_부재_수': len(all_columns),
            '소스별_통계': summary,
            '부재_법전': all_columns,
        }, f, ensure_ascii=False, indent=2, default=str)

    md = []
    md.append(f"# 부산 에코델타 24BL — 기둥 통합 법전 (PoC 일괄)\n")
    md.append(f"> 소스 도면: {len(summary)}장 / 통합 부재: {len(all_columns)}종\n")
    md.append("## 소스별 통계\n")
    md.append("| 소스 | TEXT 총수 | 분류됨 | 고유 부재 |")
    md.append("|------|--------:|-----:|--------:|")
    for s in summary:
        md.append(f"| {s['label']} | {s['total_text']} | {s['classified']} | {s['unique']} |")

    md.append("\n## 통합 기둥 법전\n")
    md.append("| 소스 | 코드 | 층 | W (mm) | H (mm) | 주근 | 후프 |")
    md.append("|------|------|-----|-------:|-------:|------|------|")
    for c in sorted(all_columns, key=lambda x: (x['source'], x['symbol'])):
        floor = f"{c['floor_from']}~{c['floor_to']}" if c['floor_from'] is not None else '-'
        md.append(f"| {c['source']} | {c['symbol']} | {floor} | {c['width'] or '-'} | {c['height'] or '-'} | {c['main_bar'] or '-'} | {c['hoop'] or '-'} |")

    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))

    print(f"[저장] {OUT_JSON}")
    print(f"[저장] {OUT_MD}")
    print("완료.")

if __name__ == '__main__':
    main()
