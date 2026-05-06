# 도면 → FreeCAD 빠른 참조 (1쪽 요약) — v2 갱신

> 전문: `docs/MANUAL_DRAWING_TO_FREECAD_v2.md` (v1: `docs/MANUAL_DRAWING_TO_FREECAD_v1.md`)  
> 근거: 방부장 친명 2026-05-06  
> v2 갱신: 2026-05-06 — 101동 통합 PoC 반영

---

## 7 도구함 (core/)

| # | 파일 | 역할 |
|:-:|---|---|
| 1 | `pc_layer_adapter.py` | 어댑터 ③: PC vs 일반 레이어 분리 |
| 2 | `line_pairing.py` | 어댑터 ②: LINE 페어링 + 격자 자동 추출 |
| 3 | `girder_matcher.py` | 어댑터 ①: 두께로 거더 분리 + codex 매칭 |
| 4 | `f1_anchor_aligner.py` | F-1 좌표 정렬 (E/V 코어 SW = 원점) |
| 5 | `f1_core_cluster.py` | F-1 코어 클러스터링 (γ+α) |
| 6 | `box_classifier.py` | 박스 분류: β(종횡비)+γ(코어)+α(격자) |
| 7 | `codex_instance_mapper.py` | 인스턴스 ↔ codex 매핑 |

---

## 정사 파이프라인 순서 (절대 역행 금지)

```
DXF 로드 (cp949)
    ↓
[③] pc_layer_adapter.classify_entities(raws)
    → PC 풀 / NON-PC 풀 분리
    ↓
[②] line_pairing.run_adapter_2(non_pc_lines)
    → wall_pairs + grid_obj
    ↓
[①] girder_matcher.detect_girders_from_adapter2(a2, ...)
    → girder codex 매칭
    ↓
[분류] box_classifier.classify_batch(non_pc_boxes, grid=grid_obj)
    → column / wall_segment / core_wall
    ↓
[codex] codex_instance_mapper.map_instances(column_instances, codex)
    → 식별된 기둥
    ↓
[3D] FreeCAD Part.Wire → Face → extrude → compound.exportStep()
```

---

## 표준 상수

```python
FLOOR_HEIGHT      = 4400   # mm (표준 층고)
GIRDER_H_DEFAULT  = 800    # mm (보 높이 기본)
COLUMN_W_MIN      = 400    # mm (기둥 최소)
COLUMN_W_MAX      = 3000   # mm (기둥 최대)
COLUMN_MAX_RATIO  = 3.0    # 종횡비 임계 (기둥 vs 벽)
GRID_TOL          = 300    # mm (격자 교차점 허용 오차)
ITER_ALL_MAX_DEPTH = 8     # INSERT 재귀 최대 깊이
```

---

## Z 좌표 공식

```python
# 기둥 Z
z_base = floor * FLOOR_HEIGHT
# B2F: -8800, B1F: -4400, 1F: 0, 2F: 4400

# 거더 Z (천장 슬라브 하부)
gz_base = z_base + FLOOR_HEIGHT - GIRDER_H
```

---

## 검증 게이트 6건

| 게이트 | 기준 | 자동 |
|:-:|---|:-:|
| G1 | 솔리드 수 == 메타 | ✅ |
| G2 | 모든 `s.isValid()` | ✅ |
| G3 | 부피 오차 < 0.1% | ✅ |
| G4 | Z 분포에 두 층 이상 | ✅ |
| G5 | max(unique_x, unique_y) ≤ 15 | ✅ |
| G6 | 방부장 GUI 시각 확인 | 수동 |

**G5 미통과 시**: `grid=None`, `confidence >= 0.4` 완화 + 정직 박제

---

## 격자 우선순위

```
TEXT X*/Y* 라벨 ≥ 2개 → text_labels (정확, intersection_tol=300)
없으면              → adapter_2 자동 격자 (min_length=5000mm)
```

---

## 10단계 체크리스트 (새 도면) — v2 확장

```
[ ] 0. 두 도면 통합 여부? YES→좌표 매칭 먼저 (옵션 A→B→C)
[ ] 1. 환경: FreeCAD 1.1 + 7 도구함 + codex JSON 확인
[ ] 2. 1차 진단: probe_basement_dxf.py 패턴 실행
[ ] 3. 도엽 분리: TEXT + 폐합 박스 SW 좌표 자력 채굴 (명세서≠실제 주의)
[ ] 4. 스크립트 작성: poc_xxx.py (경로·상수·SHEETS 설정)
[ ] 5. 순서 확인: ③→②→①→codex 절대 역행 금지
[ ] 6. 격자 게이트: unique>15→grid=None / unique=0→라벨 없음 박제
[ ] 7. 실행: FreeCAD 1.1 python.exe poc_xxx.py
[ ] 8. 검증: G1~G5 확인 + G6 방부장 GUI 요청 + dispatch_log 박제
[ ] 9. 통합 STEP 빌드: build_XXX_combined_step.py (두 도면 통합 시)
```

---

## 실패 시 즉시 참조

| 증상 | 원인 | 처방 |
|---|---|---|
| codex 매핑 0건 | `map_instances` 미호출 또는 codex 경로 오류 | codex JSON 존재·스키마 확인 |
| C1 과매칭 | column 분류 전 codex 매핑 | `classify_batch` 먼저, COLUMN만 매핑 |
| 거더 0건 | 도면 진실 또는 격자 밖 | `require_on_grid=True` 확인, 실제 없으면 정직 박제 |
| G5 미통과 | 단지 통합 도면 (격자 큼) | `grid=None`, `conf >= 0.4`, 사유 박제 |
| G5 unique=0 | 격자 라벨 자체 없음 (101동 패턴) | adapter_2 폴백, "라벨 없음" 별도 박제 |
| GLB 회귀 실패 | 선형 변환 불가 (잔차 120m) | 옵션 A(DXF 텍스트 직접 검색)로 우회 |
| unmatched 많음 | codex 단면 미포함 | 분포 분석 후 상위 단면 codex 추가 |
| 통합 BBox 비합리 | 좌표 정렬 실패 | A2 기준점·평행이동 벡터 재확인 |
| FreeCAD import 오류 | 경로 문제 | `python.exe` 경로 확인, `sys.path.insert` |
| cp949 오류 | DXF 인코딩 | `ezdxf.readfile(DXF, encoding='cp949')` |

---

## v2 좌표 매칭 요약 (두 도면 통합)

```
핵심 명제: "도엽 안에서 동 라벨 한 줄이 두 좌표계를 잇는다."

옵션 A (권장):
  1. 주변 도면에서 동 번호 TEXT 검색 ("101", "102" 등)
  2. 절대 좌표 → 도엽 SW 차감 → 상대 좌표
  3. A1 솔리드 중심 - A2 기준점 = 평행 이동 벡터
  4. a2_moved.translate(FreeCAD.Vector(dx, dy, 0))

옵션 B (비권장): GLB 선형 회귀 — 101동 PoC에서 잔차 120m 실패
옵션 C (Phase 2): 격자 라벨 공통 교차점
```

---

## 시행 사례 숫자

| PoC | 날짜 | 솔리드 | 기둥 | 거더 | 부피 |
|---|---|---:|---:|---:|---|
| 102동 9도엽 | 2026-05-05 | **87** | 55 | 32 | 129.523 m³ |
| 지하주차장 B1·B2 | 2026-05-06 | **300** | 289 | 11 | — |
| 101동 동체 (A1) | 2026-05-06 | **419** | 399 | 20 | 746.819 m³ |
| 101동 주변 주차장 (A2) | 2026-05-06 | **99** | 86 | 13 | 175.032 m³ |
| **101동 통합** | **2026-05-06** | **518** | **485** | **33** | **921.851 m³** |

---

*— 이천(李蕆), 2026-05-06. v2 갱신. 홍익인간.*
