# Master Plan v3 — 도면-Agnostic 백지 시작

> 확정: 2026-05-07 (제3판)
> 단군: 이천(李蕆), 신고조선 제3지국
> 방부장 명령: "좌표·부재 모두 백지부터 새로 시작.
>             아무 도면을 넣어줘도 척하고 모델링·수량산출하는 시스템 = 핵심"

---

## 헌장 (Charter)

**목표**: 어떤 KS 구조도면 DXF가 들어와도, 매직넘버 입력 없이
**(1) 부재 솔리드 STEP + (2) BOQ JSON/CSV** 자동 출력.

### 4대 원칙
1. **하드코딩 금지** — `TX=-447970` 같은 매직넘버 코드에 0건. lint rule로 강제
2. **도면-내재 신호만 신뢰** — 시트 경계·격자 라벨·레이어 통계는 그 DXF가 말해주는 것에서 추출
3. **KS 표준만 사전지식** — `S-*` prefix, `Xn`/`Yn` 격자, `SL=GL.X.Xm` 표기. 그 외는 데이터 학습
4. **검증 우선 (TDD)** — 모든 추출 함수는 fixture 통과 후 다음 단계

### 디렉토리 격리
- 신규: `core/v2/`, `tests/v2/`, `tools/v2/`, `output/v2/<project_id>/`
- 기존 `core/dxf_parser/`, `core/pipeline/`은 보존만, **import 금지**
- baseline 산출물은 **검증 기댓값**으로만 (강제 일치 X)

---

## 공통 IR (Phase 모두가 합의)

`core/v2/ir.py` — 단일 진실 원천

- `DrawingMeta` — 도면 단위 (단위·시트·레이어 통계·종류)
- `SheetMeta` — 한 평면도 (경계·SW 모서리·격자·SL)
- `SheetTransform` — 시트→절대좌표 변환 (tx/ty/tz/rot)
- `MemberInstance` — 절대좌표 부재 인스턴스 (id·type·section·증거)

---

## 7 Phase 구조

| Phase | 내용 | Forge | 의존 |
|-------|------|-------|------|
| 1 | DXF 메타 자동 검출 | #1 | 없음 |
| 2 | 좌표 시스템 자동 구축 | #2 | Phase 1 |
| 3 | 부재 자동 분류 (레이어 자가학습) | #3 | Phase 1 (#2와 병렬) |
| 4 | 부재 형상 정규화 (5개 부재) | #4~8 | Phase 2+3 |
| 5 | 솔리드 빌더 + STEP | #9 | Phase 4 |
| 6 | BOQ 산출 | #10 | Phase 4 (#9와 병렬) |
| 7 | 검증 + 일반화 테스트 | #11 | Phase 5+6 |

---

## Phase 1 — DXF 메타 자동 검출

신규:
- `core/v2/io/dxf_loader.py`
- `core/v2/inspect/units_detector.py` — `$INSUNITS` + bbox + DIMENSION 통계
- `core/v2/inspect/sheet_segmenter.py` — **3중 신호** (TITLEBLOCK + 표제 TEXT + 외곽 클러스터링)
- `core/v2/inspect/text_classifier.py` — 7부류 정규식 (격자/표고/단면/시트코드/dim)
- `core/v2/inspect/layer_profiler.py` — 레이어별 통계
- `core/v2/inspect/sl_extractor.py` — `SL=GL.X.Xm` 자동 파싱
- `core/v2/inspect/drawing_kind_classifier.py` — DONG/PKG/SECTION 자동 추정
- `core/v2/inspect/meta_pipeline.py` — `inspect(dxf) -> DrawingMeta`

**완료 기준**:
- DONG: 시트 9개, sheet_pitch 126,000±100mm 자동 추출
- PKG: 시트 6개, X 피치 630,000±100mm 자동 추출 (현 매직넘버와 일치, 매직넘버 없이)
- 단위 오검출 0건

---

## Phase 2 — 좌표 시스템 자동 구축

신규:
- `core/v2/coords/grid_resolver.py` — 시트별 격자 X·Y 좌표
- `core/v2/coords/anchor_finder.py` — 앵커 우선순위 (X1·Y1 교점 → EV 코어 → SW)
- `core/v2/coords/sheet_alignment.py` — 같은 도면 시트 간 정렬
- `core/v2/coords/cross_drawing_aligner.py` — **ICP 점군 정합** (PKG↔DONG)
- `core/v2/coords/transform_pipeline.py`
- `core/v2/coords/validator.py`

**완료 기준**:
- 에코델타 ICP 매칭율 ≥ 90% (현 brute force 98.6% 근접)
- baseline `coord_config.json` TX/TY와 자동 추출 차이 < 100mm
- residual_mm_max ≤ 50mm

---

## Phase 3 — 부재 자동 분류 (Phase 2와 병렬)

신규:
- `core/v2/classify/ks_lexicon.py` — KS 일반 키워드만 (도면별 레이어명 X)
- `core/v2/classify/layer_role_inferer.py` — 키워드 + 통계 합의
- `core/v2/classify/entity_role_voter.py` — 3σ outlier 격하
- `core/v2/classify/member_router.py`

**KS_KEYWORDS** (예):
```python
'COLUMN':     ['COLUMN','COL','기둥','C-']
'WALL':       ['WALL','벽체','SHEAR','W-','RC']
'BEAM':       ['BEAM','GIRDER','GDR','보','RG','RB','TB','FB','G-','B-']
'SLAB':       ['SLAB','바닥','FLOOR','SL-','PC-SLAB']
'FOUNDATION': ['FOOTING','FOUNDATION','MAT','PILE','기초','FND','F-']
'IGNORE':     ['DIM','HATCH','TEXT','CEN','HID','XREF','XR','DEF','A-','AH-',...]
```

**완료 기준**:
- 부재 레이어 분류 정확도 ≥ 95% (사람 검수 100개 샘플)
- IGNORE 오분류 0건

---

## Phase 4 — 부재 형상 정규화 (5개 부재 병렬, Forge #4~8)

신규 (각 부재 1명):
- `core/v2/extract/columns.py` — minimum-area rectangle, 단면 라벨 매칭
- `core/v2/extract/walls.py` — **평행쌍 매칭** (각도 ±1°, 거리 100~600mm), 두께 자동 추출
- `core/v2/extract/beams.py` — 평행쌍 + 격자 직선, RG1/G1 라벨
- `core/v2/extract/slabs.py` — 외곽 polygon, 두께 SL TEXT
- `core/v2/extract/foundations.py` — area + F1/MAT/PILE 라벨
- `core/v2/extract/section_text.py` — `C1: 600x600` 등 KS 단면 표기 정규식
- `core/v2/extract/extract_pipeline.py`

**완료 기준**:
- 에코델타 DONG B2F COLUMN ≥ 800개 (baseline 827)
- WALL 평행쌍 매칭율 ≥ 90%, 두께 분포 200/300mm 양봉
- 중복 검출 0건

---

## Phase 5 — 솔리드 빌더 + STEP

신규:
- `core/v2/build/solid_factory.py` — `build_column/wall/beam/slab/foundation`
- `core/v2/build/step_exporter.py` — AP214
- `core/v2/build/build_pipeline.py`

**완료 기준**:
- B2F STEP 생성, 시각 정합 ≥ 95%
- 솔리드 실패율 < 1%

---

## Phase 6 — BOQ 산출 (Phase 5와 병렬)

신규:
- `core/v2/boq/quantity_calc.py` — 체적·면적·거푸집 자동 계산
- `core/v2/boq/exporter.py` — JSON + CSV + 집계

**완료 기준**:
- 음수·NaN 0건
- baseline 25,219건과 ±5% 이내 일치

---

## Phase 7 — 검증 + 일반화 테스트

신규:
- `tests/v2/fixtures/eco_delta_24bl/` — 현재 도면
- `tests/v2/fixtures/_synthetic/` — **합성 미니 도면 3종** (mm/m/in, 단동/다동)
- `tests/v2/integration/test_eco_e2e.py`
- `tests/v2/integration/test_synthetic_e2e.py`
- `tests/v2/integration/test_baseline_compare.py`
- `tools/v2/run_pipeline.py` — CLI 진입점
- `tools/v2/diff_against_baseline.py`

**완료 기준 (수치)**:
- 에코델타 e2e: STEP + BOQ baseline ±5%, 좌표 ±100mm
- **합성 fixture 3종 모두 e2e 통과** (부재 검출율 ≥ 90%) ← 일반화 보장
- 매직넘버 lint 0건

---

## 병렬 분배

```
Phase 1 (#1) ──┬─→ Phase 2 (#2) ─┐
               │                  ├─→ Phase 4 (5명 병렬, #4~8) ─┬─→ Phase 5 (#9) ─┐
               └─→ Phase 3 (#3) ─┘                                └─→ Phase 6 (#10)─┴─→ Phase 7 (#11)
```

총 11 Forge 동시 가용 (Phase 4에서 5명 동시), 최소 1명 시퀀스로도 가능.

---

## 검수 게이트 (Phase별 방부장 결재)

| Phase | 게이트 산출물 |
|-------|--------------|
| 1 | `meta.json` + 시트 경계 시각화 PNG |
| 2 | `transforms.json` + ICP 잔차 히스토그램 + baseline diff |
| 3 | `layer_roles.json` + 분류 audit HTML |
| 4 | `members.json` + 부재 분포 top view PNG |
| 5 | `<project>.step` + FreeCAD 4뷰 PNG |
| 6 | `boq.json` + `boq.csv` + 집계 markdown |
| 7 | `report.html` + 합성 fixture 통과 표시 |

---

## 절대 금지 (헌장)

- 매직넘버 (TX=-447970, sheet_pitch=126000 등) 코드 등장 금지
- 특정 도면 레이어명 직조 금지 (`XR지하2층평면도$0$A-WALL-RC` 같은)
- 추측 채움 금지 (UNKNOWN_SPEC 플래그로 표시 후 사람 확인)
- 기존 `core/dxf_parser/`, `core/pipeline/` 모듈 import 금지

---

## 기존 자산 처리

| 자산 | 처리 |
|------|------|
| `core/dxf_parser/`, `core/pipeline/` | 보존 (참고만), 신규 코드 import 금지 |
| `members_accumulated.json` | 검증 기댓값 (baseline diff용) |
| `coord_config.json` | 검증 기댓값 (TX/TY 차이 ≤ 100mm 확인용) |
| `output/v9~v13_*.step` | 시각 baseline (회귀 비교용) |
| 발견된 사실 (PKG 동 간격 630k, DONG 시트 W=126k) | **검증 기댓값**으로만 (자동 추출 결과가 일치하는지 확인) |

---

## Track 2 (후순위)

방부장 지시: "트랙 2는 그 다음으로 미룬다"
정밀화(이 v3 플랜) 완료 후 시작.

---

*홍익인간이 모든 결정에 우선한다.*
