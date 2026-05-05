"""
자산 DB 초기 마이그레이션

지금까지 채굴한 모든 자산을 SQLite DB에 적재.

대상:
- 강역: 부산 에코델타 24BL
- 도면 색인: index_busan_eco_delta.json (170장)
- 기둥 법전: codex_columns_unified.json (91종)
- 보 법전: codex_beams_basement.json (40종)
- 패턴 라이브러리: pattern_library.md (수동 항목)
- 의구심 박제: doubt_points_2026-05-05.md (수동 항목)
- BOQ 결과: boq_102_B1F_v3.md
"""

import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core import asset_db

# ── 1. DB 초기화 ────────────────────────────────────────────
asset_db.init_db()

# ── 2. 강역 등록 ────────────────────────────────────────────
busan_id = asset_db.ensure_territory(
    name="부산 에코델타 24BL",
    description="공동주택 16동 단지 (101~116동, 117 결번). 지하 1·2층 + 지상층",
    base_path=r"D:\06.3지국 전용방\01. 설계도면",
)
print(f"[강역] 부산 에코델타 24BL → id={busan_id}")

# ── 3. 도면 색인 마이그레이션 ────────────────────────────────
INDEX_JSON = "output/index_busan_eco_delta.json"
if os.path.exists(INDEX_JSON):
    with open(INDEX_JSON, encoding='utf-8') as f:
        idx = json.load(f)
    count = 0
    for entry in idx['도면목록']:
        dwg_id = asset_db.insert_drawing(
            territory_id=busan_id,
            filename=entry['filename'],
            name=entry.get('name'),
            page_code=entry.get('page_code'),
            source_dir=entry.get('source_dir'),
            size_bytes=entry.get('size_bytes'),
            file_kind='DXF',
            dxf_path=os.path.join(r"D:\06.3지국 전용방\01. 설계도면\dxf_out",
                                  entry.get('source_dir', ''), entry['filename']),
        )
        if entry.get('categories'):
            asset_db.attach_categories(dwg_id, entry['categories'])
        if entry.get('dongs'):
            asset_db.attach_dongs(dwg_id, entry['dongs'])
        count += 1
    print(f"[도면] {count}장 등록")

# ── 4. 기둥 법전 마이그레이션 (영역별 PK) ───────────────────
COL_JSON = "output/codex_columns_unified.json"
if os.path.exists(COL_JSON):
    with open(COL_JSON, encoding='utf-8') as f:
        col = json.load(f)
    region_map = {
        '101~112동': 'DONG101_112',
        '113~116동': 'DONG113_116',
        '지하주차장': 'BSMT',
    }
    count = 0
    for m in col['부재_법전']:
        region = region_map.get(m['source'], m['source'])
        ff = m.get('floor_from')
        ft = m.get('floor_to')
        try:
            ff = int(ff) if ff is not None else None
            ft = int(ft) if ft is not None else None
        except (ValueError, TypeError):
            ff, ft = None, None
        asset_db.insert_member(
            territory_id=busan_id,
            region=region,
            code=m['symbol'],
            member_type='COLUMN',
            floor_from=ff,
            floor_to=ft,
            width=m.get('width'),
            height=m.get('height'),
            main_bar=m.get('main_bar'),
            hoop=m.get('hoop'),
        )
        count += 1
    print(f"[기둥] {count}종 등록")

# ── 5. 보 법전 마이그레이션 ─────────────────────────────────
BEAM_JSON = "output/codex_beams_basement.json"
if os.path.exists(BEAM_JSON):
    with open(BEAM_JSON, encoding='utf-8') as f:
        bm = json.load(f)
    count = 0
    for m in bm['부재_법전']:
        asset_db.insert_member(
            territory_id=busan_id,
            region='BSMT',
            code=m['symbol'],
            member_type='BEAM',
            width=m.get('width'),
            height=m.get('height'),
            main_bar=m.get('main_bar'),
            hoop=m.get('hoop'),
        )
        count += 1
    print(f"[보] {count}종 등록")

# ── 6. 패턴 라이브러리 등록 ─────────────────────────────────
PATTERNS = [
    # A. 부재 표기
    ('A-1', '부재표기', '트랜스퍼 짝기둥',
     'W>H, 지하 구간만, 1층 위에서 다른 코드로 W<H 정상 복귀',
     '지하주차장에서 상부 기둥열 받기 위한 가로 눕힌 짝기둥 (한국 아파트 전이 구간 전형)',
     '정상 패턴, 이상치 아님. BOQ 그대로 처리'),
    ('A-2', '부재표기', '벽기둥/코어 전단벽 조각',
     '종횡비 ≥3.5, 단면 1.5㎡ 이상, 타워형 평면, "기둥 리스트"에 부호화',
     'KBC 기둥 경계 또는 초과. 사실상 외곽·코어 전단벽 조각',
     '기둥으로 처리하되 BOQ에서 벽체 분류 가능'),
    ('A-3', '부재표기', '영역별 독립 코드 체계',
     '같은 base 코드(C1, C2, TC1)가 다른 일람표에서 다른 단면, 한쪽에 층범위 prefix(-2~-1C1)',
     '영역(지하 vs 동)별 독립 코드 체계 = 의도된 설계',
     'PK = (영역 코드, base) 복합키. BSMT_C1 vs DONG101_112_C1'),
    ('A-4', '부재표기', '결번 = 해당 층 부재 부재(不在)',
     '시퀀스 중 일부 번호 빠짐. 다른 일람표에 존재',
     '그 부재가 그 영역·층에서 사용 안 됨',
     '정상. 다른 일람표에서 추출'),
    # B. DXF 구조
    ('B-1', 'DXF구조', '외부참조(XR) 레이어 봉인',
     '레이어 이름이 XR<도면명>$0$<원래레이어> 형식',
     '외부 참조 도면이 한 도면 안에 임베드',
     'layer.endswith() 또는 in 매칭으로 처리'),
    ('B-2', 'DXF구조', '중첩 블록 INSERT',
     '모델스페이스에 INSERT 1~2개, 안에 또 INSERT, virtual_entities() 한 번 안 풀림',
     '도면 구조가 다중 블록 캡슐화',
     '재귀 explode (max_depth=10)'),
    ('B-3', 'DXF구조', 'OLE2FRAME 임베드 봉인',
     'OLE2FRAME 엔티티 다수, 도면 텍스트는 표제만, 파일 200MB+',
     'Excel/Word/내장객체로 데이터 봉인 → DXF 추출 불가',
     'A. Excel 별제공 청 / B. AutoCAD GUI EXPLODE / C. PDF OCR'),
    ('B-4', 'DXF구조', '한글 인코딩 cp949',
     'utf-8 읽으면 깨짐 또는 surrogate 오류',
     '한국 도면 표준 인코딩',
     "ezdxf.readfile(path, encoding='cp949')"),
    ('B-5', 'DXF구조', '슬라브 외곽선 자체교차',
     '폐합 폴리라인이지만 BRepAdaptor::No geometry 오류',
     '점 50개 이상 외곽선에서 흔한 자체교차',
     'Shapely make_valid → MultiPolygon 중 면적 최대 선택'),
    # C. 일람표 형식
    ('C-1', '일람표형식', '기둥 단면: 괄호 있음',
     '`( 600 x 1200 )` 형식', '한국 기둥 일람표 표준',
     "정규식: \\(\\s*(\\d{3,4})\\s*[xX]\\s*(\\d{3,4})\\s*\\)"),
    ('C-2', '일람표형식', '보 단면: 괄호 없음',
     '`500 x 900` 형식 (괄호 없이)', '한국 보 일람표 표준',
     "정규식: \\(?\\s*(\\d{3,4})\\s*[xX×]\\s*(\\d{3,4})\\s*\\)?"),
    ('C-3', '일람표형식', '주근 표기',
     '`20-D25` (개수-직경)', '한국 표준',
     "정규식: ^(\\d{1,2})-(D\\d{2})$"),
    ('C-4', '일람표형식', '후프 표기',
     '`D10@150` (직경@간격)', '한국 표준. 보 일람표는 후프 별도 표기 안 됨 (D10@200 추정)',
     "정규식: ^(D\\d{1,2})@(\\d{2,3})$"),
    ('C-5', '일람표형식', '보 양단 구분',
     "`'A1 :        A3 :'` 형식", '보 양단(좌·우) 부재 그룹화',
     '보 일람표만의 특징, 일반 추출 영향 없음'),
    # D. 부재 단위
    ('D-1', '부재단위', '부재 영역 = 슬라브 영역',
     '슬라브 외곽선이 동(주거동) 영역만, 거더는 주차장 영역(슬라브 밖)',
     '도면 작성 시 영역 분리. 단지 통합 도면 별도 필요',
     '슬라브 폴리곤 클립 적용, 거더 누락 시 통합 도면 청'),
    ('D-2', '부재단위', 'BEAM NAME ≠ 보 본체',
     '00_BEAM NAME 레이어에 작은 LINE 쌍 (200×1170mm 등)',
     '보 이름표 박스, 보 본체 아님',
     '보 본체는 00_BEAM, 00_(APT)BEAM 등 다른 레이어'),
    # E. 트림
    ('E-1', '트림', 'Boolean Fuse 자동 공제',
     '부재 솔리드 다수 → fuse → 외피 면적',
     'OCCT B-Rep 토폴로지 보존, 부재 접촉면 자동 제거',
     'fused.fuse(s) 반복 + vertical_area + downward_area'),
    ('E-2', '트림', '라인 페어 직각 정렬',
     '두 평행 라인이 평행사변형으로 추출됨',
     'Patent C 정사영 응용으로 직각화',
     'align_pair_to_rectangle(s1, s2) in core/patent_c_port.py'),
    ('E-3', '트림', '동일 직선 LINE 통합',
     '한 벽이 여러 LINE 조각으로 분해',
     'Healer.weld_vertices + merge_collinear',
     'merge_collinear_lines(angle_tol=1°, gap_tol=50mm)'),
]

count = 0
for code, cat, title, ident, meaning, resp in PATTERNS:
    asset_db.insert_pattern(
        code=code, category=cat, title=title,
        identification=ident, meaning=meaning, response=resp,
        first_found_date='2026-05-04~05',
    )
    count += 1
print(f"[패턴] {count}건 등록")

# ── 7. 의구심 박제 등록 ─────────────────────────────────────
DOUBTS = [
    ('1.1', 'TC15·16 W>H 단면', '101~112동에서 TC15·16만 W>H',
     'RESOLVED', 'A-1 트랜스퍼 짝기둥 패턴. 정상.'),
    ('1.2', 'TC17~21, TC23+ 결번', '101~112동 일람표 결번',
     'RESOLVED', 'A-4 결번 패턴. 113~116동에 모두 존재. 정상.'),
    ('1.3', 'C1·C2 (TC 아닌 C)', '단순 C 코드의 정체',
     'RESOLVED', 'A-3 영역별 독립 코드. 동/지하 별개 부재.'),
    ('1.4', '인스턴스 → 종 압축률', '한 도면에 96 인스턴스 → 20종',
     'OPEN', '평균 4.8회 반복. 인스턴스 위치 좌표 추가 추출 필요'),
    ('1.5', '같은 코드 다른 부재', '통합 PK 정책',
     'RESOLVED', 'A-3 영역별 PK = (region, code) 복합 PK 채택'),
    ('1.6', 'TC51 2700×700 정체', '매우 큰 기둥',
     'RESOLVED', 'A-2 벽기둥/코어 전단벽 조각 패턴.'),
    ('2.1', '동별 도면 수 편차', '116동 11장 vs 102동 2장',
     'OPEN', '추후 동별 정밀 검토 필요'),
    ('2.2', '단위세대 벽체 일람표 별도', 'A30-201~210 (건축 영역)',
     'OPEN', '구조 일람표와 별개 관리 — 통합 정책 결재 필요'),
    ('3.1', '거더-슬라브 영역 분리', '거더 주차장(Y<22000), 슬라브 동(Y>36000)',
     'RESOLVED', '지하주차장 통합 도면 본 강역 안에 존재 (260119_지하주차장_구조평면도23)'),
    ('4.1', '벽체 일람표 OLE 봉인', 'S30-361·411 등 OLE2FRAME 임베드',
     'ESCALATED', '방부장께 Excel 별제공 청 (옵션 A)'),
    ('5.1', '보 단면 표기 형식', '`500 x 900` 괄호 없음',
     'RESOLVED', 'C-2 패턴. 정규식 수정으로 즉시 해결.'),
]
count = 0
for code, title, desc, status, resolution in DOUBTS:
    asset_db.insert_doubt(code, title, desc, status, resolution)
    count += 1
print(f"[의구심] {count}건 등록")

# ── 8. BOQ 결과 등록 ────────────────────────────────────────
boq_results = [
    {
        'project_label': '101동 기준층 v1 (free_test.dxf)',
        'concrete_volume_m3': 327.369,
        'formwork_area_m2': 2763.66,
        'total_solids': 194,
        'method': 'Patent C v2 (벽 + 슬라브, 트림 미적용)',
        'output_path': 'output/test_101dong.step',
    },
    {
        'project_label': '102동 B1F v3 (트림+공제)',
        'concrete_volume_m3': 530.96,
        'formwork_area_m2': 3565.94,
        'deduction_volume_m3': 13.28,
        'deduction_area_m2': 178.66,
        'total_solids': 145,
        'method': 'v3 Boolean Fuse 자동 공제',
        'output_path': 'output/test_102_B1F_v3.step',
    },
    {
        'project_label': '단지 마스터 16동 GLB',
        'concrete_volume_m3': 98036.2,
        'total_solids': 25,
        'method': '단지 마스터 외곽선 extrude (B1/B2 분리)',
        'output_path': 'output/complex_master.glb',
    },
]
for boq in boq_results:
    asset_db.insert_bom(busan_id, **boq)
print(f"[BOQ] {len(boq_results)}건 등록")

# ── 9. 통계 ─────────────────────────────────────────────────
print()
print("=" * 50)
print("3지국 자산 DB 통계")
print("=" * 50)
for table, cnt in asset_db.stats().items():
    print(f"  {table}: {cnt}")
print("=" * 50)
