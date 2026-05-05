"""1지국 채굴 노하우 5건 → 자산 DB 패턴 박제"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core import asset_db

PATTERNS = [
    ('G-1', '1지국노하우', '재귀 INSERT 전개 + transform_point',
     'INSERT 블록 만나면 회전·스케일·오프셋 결합 행렬로 재귀 (depth ≤ 10)',
     '한국 구조도 99% 평탄화. 도엽 블록 캡슐화 해소',
     '1지국 parse_dxf.py:215~430 collect_entities 함수 이식'),
    ('G-2', '1지국노하우', 'MTEXT escape 정규화',
     'AutoCAD 폰트·색깔 escape 코드',
     'AutoCAD 포맷 코드 벗겨 실텍스트만 회수',
     '정규식: \\f0;{...};, \\P 처리'),
    ('G-3', '1지국노하우', 'detect_member 한국 토속 필터',
     '블랙리스트 → 도면번호 → 층수 → 한글 설명문 → 구간 → 테두리보 → 부재 순',
     '한국 도면 false positive 방지 (B1F→보 오인 등)',
     '1지국 parse_dxf.py:79~161 detect_member 함수 이식'),
    ('G-4', '1지국노하우', '일람표 그리드 분석 (1지국 핵심 자산)',
     '헤더 행 탐색 → Y좌표 ±100 행 클러스터링 → 거리 매칭',
     '일람표 채굴의 본질. 1지국이 가장 비싸게 산 노하우',
     '1지국 parse_dxf.py:437~586 두 단계 그리드 분석 이식'),
    ('G-5', '1지국노하우', '20mm 위치 dedupe',
     '같은 symbol 두 번 (dx, dy < 20)',
     '동일 부재 중복 추출 방지',
     'parse_dxf.py:589~601 dedupe 로직 이식'),
]
for code, cat, title, ident, meaning, resp in PATTERNS:
    asset_db.insert_pattern(
        code=code, category=cat, title=title,
        identification=ident, meaning=meaning, response=resp,
        first_found_date='2026-05-05',
        notes='1지국 정도전 다년 자산. 방부장 친명에 의해 검수·이식'
    )
print(f'1지국 노하우 5건 박제 완료')
print(f'DB 패턴 총 {asset_db.stats()["patterns"]}건')
