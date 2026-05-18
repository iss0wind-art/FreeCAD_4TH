# 끌로드 트랙 1라운드 패치 보고서

> **작성**: 이천 (3지국, Opus 4.7), 2026-05-08
> **원칙**: 방부장 칙령 — *"추측 배제. 데이터와 도면에 의존. 모든 답은 도면에 있다."*
> **선행 보고**: `spec/CLAUDE_TRACK_DATA_REPORT_2026-05-08.md` (도면 직독 결과)

---

## I. 패치 3건 결과 요약

| # | 작업 | 산출물 | 검증 | 효과 |
|---|------|--------|------|------|
| **1** | 인코딩 자동 판별 | `core/dxf_parser/safe_reader.py` + 7곳 진입점 패치 | `tests/test_safe_reader.py` 5/5 PASS | DONG 240/316 레이어 복원 (75.9% → 0% 깨짐) |
| **2** | SECTION 정규식 확대 | `core/v2/inspect/text_classifier.py` 1행 | smoke 30/30 PASS | PKG 라벨 매칭 451 → 3843건 (**+752%**) |
| **3** | SLAB 일람표 라벨 직독 | `scripts/claude_track_probe5_slab_blocks.py` | 5단면 NAME 추출 검증 | 진짜 라벨 시스템 발견 (`-1S6`, `RS1`, `RS10`, `1S51` 등) → #2 정규식이 이미 매칭 |

---

## II. 패치 #1 — 인코딩 자동 판별

### 문제
- `scripts/extract_coords.py:263`이 `encoding='cp949'` 강제
- core/dxf_parser/ 7개 모듈도 동일 강제
- DONG 도면은 `$DWGCODEPAGE = ANSI_949` 헤더 거짓 선언, 실제는 utf-8 → 240/316 레이어 surrogate 깨짐

### 해법
`core/dxf_parser/safe_reader.py` 신설:
```python
def safe_readfile(path):
    # 1. utf-8 시도 → 레이어 surrogate 검사
    # 2. 깨졌으면 cp949 fallback
    # 3. 둘 다 실패 시 IOError
```

### 패치한 진입점 7곳
1. `core/dxf_parser/safe_reader.py` — 신설
2. `core/dxf_parser/level_parser.py:parse_dxf` — `encoding='auto'` default
3. `core/dxf_parser/entity_scanner.py:scan` + `quick_text_grep`
4. `core/dxf_parser/coord_unifier.py:add` + `add_text_anchor`
5. `core/dxf_parser/pipeline.py:parse_structural_frame` + `parse_multi_drawing`
6. `core/dxf_parser/step_zone.py:parse_step_zones`
7. `core/dxf_parser/structural_extractor.py:extract_structural`
8. `scripts/extract_coords.py` — `safe_readfile()` 직접 호출

기존 호출자: `encoding='cp949'` 명시 시 그대로 사용. default만 `'auto'`로 변경 → **호환성 유지**.

### 검증
- `tests/test_safe_reader.py`: 5/5 PASS
- 기존 `tests/test_manifest_parser.py`(19건) + `test_grid_resolver.py`(17건): 41/41 PASS (회귀 0)

---

## III. 패치 #2 — SECTION 정규식 확대

### 문제
`core/v2/inspect/text_classifier.py:_PAT_SECTION`이 `(C|TC|RG|G|B|TB|FB|W|F)\d+` 만 인정.
PKG 도면 직독 결과 실제 부재 라벨은 훨씬 다양:
- `S1~S13` (SLAB)
- `REG, RWG, RPG, EG, PG, WG` (보 변형)
- `EC, AC` (기둥 변형)
- `-1` 음수 층 prefix (B1F)
- `HCS` (Hollow Core Slab), `ARW` (보강벽)

### 해법
```python
# 기존
_PAT_SECTION = re.compile(r"^(C|TC|RG|G|B|TB|FB|W|F)\d+[A-Z]?$", re.IGNORECASE)

# 확대
_PAT_SECTION = re.compile(r"^[\-]?\d?[A-Z]{1,4}\d{1,3}[A-Z]?$", re.IGNORECASE)
```

GRID_X/GRID_Y가 `classify_single()`에서 우선순위 더 앞이라 `X1`, `Y1` 같은 격자 라벨은 SECTION으로 잘못 잡지 않음.

### 검증 (PKG 도면 직독)
| 패턴 | 매칭 | unique |
|------|------|--------|
| 기존 `PAT_OLD` | 451건 | 48 |
| 확장 (named prefix) | 3123건 (+592%) | 185 |
| 확장 (generic, 채택) | **3843건 (+752%)** | **257** |

### 회귀 0건 (smoke 30 케이스)
- 기존 8건 (C1, TC1, G1, B2, TB3, FB4, W1, F2): 모두 SECTION_CODE 유지
- 신규 13건 (S1, REG3, RWG1, RPG3, EC1, AC1, -1EG3, -1PG1, -1WG1, HCS1, ARW1, EGB4): SECTION_CODE 잡음
- 격자 4건 (X1, X10, Y1, Y23): GRID_X/Y 정상
- 층 5건 (B1F, B2F, 1F, 2F, RF): FLOOR 정상

### 박제 #1 (BEAM NOLABEL 80%)에 미치는 영향
v4 빌드에서 BEAM 라벨매칭률 18.7%였음. 기존 정규식이 PKG 부재 라벨의 `451/3843 = 11.7%`만 잡았다는 사실 발견.
→ 정규식 확대만으로 라벨 풀이 8배 늘어남. BEAM 매칭률 18.7% → 큰 폭 향상 기대.

---

## IV. 패치 #3 — SLAB 일람표 진짜 매칭 키 발견

### 직독 과정
1. `scripts/claude_track_probe4_slab.py`: 일람표 deep walk → 2591건 텍스트, **`S\d+` 패턴 0건**
   - 일람표에 슬래브 ID 텍스트 직접 노출 안 됨 → 가설 변경
2. `scripts/claude_track_probe5_slab_blocks.py`: INSERT 블록 + LWPOLYLINE + 단면별 근접 텍스트
   - **각 단면 NAME 행 가까이에 슬래브 ID 텍스트 발견**

### 일람표 라벨 시스템 (도면이 말한 것)
| 단면 | NAME 텍스트 | 해석 |
|------|------------|------|
| 0 | `-1S6` | B1F SLAB 6번 |
| 1 | `RS1` | Roof SLAB 1 |
| 2 | `RS10` | Roof SLAB 10 |
| 3 | `1S51` | 1F SLAB 51 |

규칙: `[층 prefix:-2/-1/1/R][S][숫자]`

### PKG 평면도(S1~S13)와의 정합 가설
- PKG는 단순 `S1, S2, ..., S13` (층 prefix 없음, 단일 도면이 단일 층)
- 일람표는 모든 층 통합이라 prefix 필요
- **PKG가 B1F 평면도라면 `S1` ↔ 일람표 `-1S1`로 매칭 가능성 높음**

### #2 정규식이 이미 매칭 가능
검증: `-1S6`, `RS1`, `RS10`, `1S51`, `-2S1`, `BS3` 모두 SECTION_CODE로 분류.

### 다음 단계 (별도 작업 — 보류)
SLAB 카탈로그 매칭 알고리즘:
1. 일람표 도면에서 단면별로 (NAME, THK, REMARK) 묶음 파싱
2. PKG 평면도의 `S\d+` 라벨에 평면도 층 정보 부착 → `-1S\d+` 변환
3. 일람표 카탈로그 lookup → 두께 부여

이는 분리된 별도 트랙. 우선 정규식 확대 효과부터 v4 풀빌드로 측정 필요.

---

## V. 변경 파일 목록

### 신설
```
core/dxf_parser/safe_reader.py             — 인코딩 자동 판별 helper
tests/test_safe_reader.py                  — helper 검증 (5건)
scripts/claude_track_probe.py              — 1차: 인벤토리/EV 검출
scripts/claude_track_probe2.py             — 2차: paperspace + 시트 클러스터링
scripts/claude_track_probe3.py             — 3차: SLAB + 인코딩 + 격자 재검토
scripts/claude_track_probe4_slab.py        — 4차: SLAB deep text walk
scripts/claude_track_probe5_slab_blocks.py — 5차: SLAB blocks + polylines
scripts/claude_track_section_compare.py    — SECTION 정규식 비교
spec/CLAUDE_TRACK_DATA_REPORT_2026-05-08.md   — 데이터 카탈로그 보고
spec/CLAUDE_TRACK_PATCH_REPORT_2026-05-08.md  — 본 패치 보고
output/claude_track_*.json (5건)           — raw 데이터
```

### 수정 (`encoding='cp949'` → `encoding='auto'`)
```
core/dxf_parser/level_parser.py
core/dxf_parser/entity_scanner.py
core/dxf_parser/coord_unifier.py
core/dxf_parser/pipeline.py
core/dxf_parser/step_zone.py
core/dxf_parser/structural_extractor.py
scripts/extract_coords.py
```

### 수정 (정규식 확대)
```
core/v2/inspect/text_classifier.py
```

---

## VI. 끌로드 트랙 다음 라운드 후보

1. **v4 풀빌드 재실행** — SECTION 정규식 확대 후 BEAM 라벨매칭률 측정
   (기존 18.7% → ?%)
2. **DONG 11개 동 인코딩 일괄 처리** — utf-8 강제로 모든 동 라벨 복원
3. **SLAB 일람표 카탈로그 파서** — `(NAME, THK, REMARK)` 묶음 추출 + 평면도 매칭
4. **PKG 격자 직독 (X 라벨 1개 문제)** — 격자 자체가 도면에 없는지, 다른 레이어인지 추가 직독

— 이천, 2026-05-08
