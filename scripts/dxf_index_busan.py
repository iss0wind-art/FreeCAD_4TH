"""
부산 에코델타 24BL 강역 자동 색인

DXF 변환 직후 실행 — 175장의 의미·역할·동·부재 종류를 자동 분류.

산출:
- output/index_busan_eco_delta.json — 도면별 메타데이터
- output/index_busan_eco_delta.md — 사람이 읽을 인덱스
"""

import os
import re
import json
import sys
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF_BASE = r"D:\06.3지국 전용방\01. 설계도면\dxf_out"
OUT_JSON = "output/index_busan_eco_delta.json"
OUT_MD   = "output/index_busan_eco_delta.md"

# 도면명 패턴 → 분류
PATTERNS = [
    (r'(\d{3})동\s*구조평면도',       'STRUCTURE_PLAN_DONG',  '동별 구조평면도'),
    (r'벽체\s*일람표',                 'WALL_LIST',            '벽체 일람표'),
    (r'기둥\s*리스트',                 'COLUMN_LIST',          '기둥 리스트'),
    (r'지하주차장.*구조평면도',        'BASEMENT_PARKING',     '지하주차장 구조평면도'),
    (r'지하주차장.*보\s*리스트',       'BEAM_LIST',            '지하주차장 보 리스트'),
    (r'단위세대.*구조평면도',          'UNIT_PLAN',            '단위세대 구조평면도'),
    (r'주동.*주출입구',                'MAIN_ENTRANCE',        '주동 주출입구'),
    (r'기초판\s*확장',                 'FOUNDATION_EXT',       '기초판 확장 검토'),
    (r'구조일반사항',                  'GENERAL_NOTES_S',      '구조 일반사항'),
    (r'건축일반사항',                  'GENERAL_NOTES_A',      '건축 일반사항'),
    (r'단지배치도',                    'COMPLEX_PLAN',         '단지 배치도'),
    (r'지반층배치도',                  'GROUND_PLAN',          '지반층 배치도'),
    (r'배치도',                        'LAYOUT',               '배치도'),
    (r'단면도',                        'SECTION',              '단면도'),
    (r'입면적',                        'ELEVATION_AREA',       '입면적 산출'),
    (r'장애인.*편의시설',              'ACCESSIBLE',           '장애인 편의시설'),
    (r'방화구획',                      'FIRE_DIVISION',        '방화구획'),
    (r'방수계획',                      'WATERPROOF',           '방수계획'),
    (r'단열계획',                      'INSULATION',           '단열계획'),
    (r'바닥단열',                      'FLOOR_INSULATION',     '바닥 단열'),
    (r'주차장.*방화',                  'PARKING_FIRE',         '주차장 방화구획'),
    (r'면적산출',                      'AREA_CALC',            '면적 산출'),
    (r'위치도',                        'LOCATION',             '위치도'),
    (r'조감도',                        'BIRDVIEW',             '조감도'),
    (r'지구단위',                      'DISTRICT_UNIT',        '지구단위계획'),
    (r'폐기물.*보관',                  'WASTE',                '폐기물 보관시설'),
    (r'자전거',                        'BICYCLE',              '자전거 주차'),
    (r'캐노피',                        'CANOPY',               '캐노피'),
    (r'난간|트렌치',                   'RAILING',              '난간·트렌치'),
    (r'사선검토',                      'SUNLIGHT',             '사선검토'),
    (r'동선|교통',                     'TRAFFIC',              '동선·교통체계'),
    (r'시설물',                        'FACILITY',             '시설물'),
    (r'도면목록',                      'INDEX',                '도면목록'),
    (r'개선안',                        'IMPROVEMENT',          '개선안'),
]

DONG_RE = re.compile(r'(\d{3})동')
PAGE_RE = re.compile(r'S?\d{2}-\d+~?\d*')

def classify(filename):
    name = os.path.splitext(filename)[0]
    # 동 번호 추출
    dong_match = DONG_RE.findall(name)
    dongs = sorted(set(int(d) for d in dong_match if 100 <= int(d) <= 200))

    # 페이지 코드
    page = PAGE_RE.search(name)
    page_code = page.group(0) if page else None

    # 카테고리 매칭
    categories = []
    for pat, code, label in PATTERNS:
        if re.search(pat, name):
            categories.append({'code': code, 'label': label})

    return {
        'filename': filename,
        'name': name,
        'page_code': page_code,
        'dongs': dongs,
        'categories': categories,
    }

def main():
    if not os.path.exists(DXF_BASE):
        print(f"[대기] DXF 변환 결과 폴더 없음: {DXF_BASE}")
        return

    all_entries = []
    for sub in sorted(os.listdir(DXF_BASE)):
        sub_path = os.path.join(DXF_BASE, sub)
        if not os.path.isdir(sub_path):
            continue
        for f in sorted(os.listdir(sub_path)):
            if f.lower().endswith('.dxf'):
                size = os.path.getsize(os.path.join(sub_path, f))
                entry = classify(f)
                entry['source_dir'] = sub
                entry['size_bytes'] = size
                all_entries.append(entry)

    if not all_entries:
        print("[대기] DXF 파일 없음 — 변환 완료 후 재실행")
        return

    # 통계
    by_category = {}
    by_dong = {d: [] for d in range(101, 117)}
    by_dong['공통'] = []

    for e in all_entries:
        for c in e['categories']:
            by_category.setdefault(c['code'], []).append(e['filename'])
        if e['dongs']:
            for d in e['dongs']:
                by_dong.setdefault(d, []).append(e['filename'])
        else:
            by_dong['공통'].append(e['filename'])

    # JSON 산출
    os.makedirs("output", exist_ok=True)
    result = {
        '강역': '부산 에코델타 24BL',
        '색인일시': datetime.now().isoformat(timespec='seconds'),
        '총_도면수': len(all_entries),
        '도면목록': all_entries,
        '카테고리별': {k: len(v) for k, v in by_category.items()},
        '동별': {str(k): len(v) for k, v in by_dong.items() if v},
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Markdown 산출
    md = []
    md.append(f"# 부산 에코델타 24BL — 강역 자동 색인\n")
    md.append(f"> 색인일시: {result['색인일시']}")
    md.append(f"> 총 도면 수: **{len(all_entries)}장**\n")

    md.append("## 카테고리별 분포\n")
    md.append("| 코드 | 분류 | 개수 |")
    md.append("|------|------|-----:|")
    cat_label = {c['code']: c['label'] for c in [{'code': p[1], 'label': p[2]} for p in PATTERNS]}
    for code, files in sorted(by_category.items(), key=lambda x: -len(x[1])):
        md.append(f"| {code} | {cat_label.get(code, code)} | {len(files)} |")

    md.append("\n## 동별 분포\n")
    md.append("| 동 | 도면 수 |")
    md.append("|---:|------:|")
    for d in range(101, 117):
        cnt = len(by_dong.get(d, []))
        if cnt > 0:
            md.append(f"| {d}동 | {cnt} |")
    md.append(f"| 공통 | {len(by_dong.get('공통', []))} |")

    md.append("\n## 핵심 도면 (청 2·3 답)\n")
    md.append("### 청 2 — 벽체 일람표 + 기둥 리스트\n")
    for e in all_entries:
        if any(c['code'] in ('WALL_LIST', 'COLUMN_LIST') for c in e['categories']):
            md.append(f"- `{e['filename']}` ({e['size_bytes']/1024:.1f} KB)")

    md.append("\n### 청 3 — 지하주차장 통합 도면 + 보 리스트\n")
    for e in all_entries:
        if any(c['code'] in ('BASEMENT_PARKING', 'BEAM_LIST') for c in e['categories']):
            md.append(f"- `{e['filename']}` ({e['size_bytes']/1024:.1f} KB)")

    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))

    print(f"[색인] 총 {len(all_entries)}장 / 카테고리 {len(by_category)}종")
    print(f"  JSON: {OUT_JSON}")
    print(f"  MD:   {OUT_MD}")

if __name__ == '__main__':
    main()
