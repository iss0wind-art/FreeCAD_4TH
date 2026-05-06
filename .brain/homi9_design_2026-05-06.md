---
title: 호미 9 설계 — 밑거름 박제 (다음 세션 첫 자료)
박제일: 2026-05-06
박제자: 이천 (제3지국)
근거: 방부장 친명 "어떤 결과든 밑거름으로 삼으라"
---

# 호미 9 설계 — 메타 풀세트 + build 분리 + 슬라브 정밀화

## 남은 결함 (호미 8 → 9로 이월)

| # | 결함 | 원인 | 처방 |
|:-:|---|---|---|
| 1 | **process_sheet 재실행 강제** | 메타 JSON에 좌표 미박제 (카운트만) | 메타 풀세트 박제 |
| 2 | **슬라브 BBox 너무 큼** | 기둥 전체 BBox = 도엽 크기 | alpha shape 또는 외곽 LWPOLYLINE |
| 3 | **좌표 정렬 분리** | A1-A2 BBox 중심 단순 평행이동 | DXF "101" TEXT 공통 원점 |
| 4 | **G3 부피 게이트 ❌** | 메타 부피 계산이 column+girder만 | 전 부재 합산 |

---

## 호미 9 — 핵심 3건

### 9-A: 메타 풀세트 박제 (영구 차단)

`process_sheet` 반환 추가:
```python
'walls_raw': [{'p1': [x,y], 'p2': [x,y], 'thickness': t, 'length': l}, ...],
'wall_segments_raw': [{'cx': x, 'cy': y, 'w': w, 'h': h}, ...],
'unmatched_columns_raw': [{'cx': x, 'cy': y, 'w': w, 'h': h}, ...],
'wall_pairs_raw': [{'p1': [x,y], 'p2': [x,y], 'thickness': t, 'overlap': l}, ...],
'all_boxes_classified': [{'box_id': ..., 'cx': ..., 'w': ..., 'kind': ..., 'conf': ...}, ...],
```

→ 이후 솔리드 종류 추가 = `build_3d` 변경만 (재실행 0초, 빌드 수십 초)

### 9-B: 슬라브 정밀화 (2가지 옵션)

**옵션 B1**: 도엽에서 *가장 큰 LWPOLYLINE 폐합 박스* (건물 외곽 경계선) 추출 → 슬라브 면
```python
# 도엽 안 폐합 박스 중 넓이 가장 큰 것 1~3개
slab_candidates = sorted(closed_polys, key=lambda p: p.area, reverse=True)[:3]
```

**옵션 B2**: 기둥 위치로 *convex hull* 계산 → 슬라브 다각형 면
```python
from scipy.spatial import ConvexHull
points = [[col['cx'], col['cy']] for col in r['columns']]
hull = ConvexHull(points)
slab_poly = [points[i] for i in hull.vertices]
```

→ 동체 footprint에 딱 맞는 슬라브 (현재 직사각형 BBox보다 정확)

### 9-C: 좌표 정렬 정사

A2가 발견한 DXF "101" TEXT 절대 위치를 *공통 원점*으로:
- A2 B2 도엽 안 "101" TEXT: (632082, -1296738) → 도엽 정규화 후 (632082-247250, -1296738-(-1390677)) = (384832, 93939)
- A1 동체 도면 안 101동 *기둥 클러스터 중심* 추출 (f1_core_cluster 변형)
- 두 중심을 *같은 좌표*로 맞춤 → 평행이동 (dx, dy)

---

## 호미 9 우선순위

1. **9-A 메타 풀세트** (가장 중요 — 재실행 강제 영구 차단)
2. **9-C 좌표 정렬** (시각 정합)
3. **9-B 슬라브 정밀화** (선택, 시각 품질)
4. G3 부피 게이트 보정 (모든 부재 합산)

---

## 호미 9 파일 명세

| 파일 | 설명 |
|---|---|
| `core/sheet_data_model.py` | 메타 풀세트 데이터 클래스 표준 |
| `tests/poc_101_fullstack_v2.py` | 통합 단일 PoC (A1+A2 좌표 정렬 포함) |
| `output/poc_101_v2.step` | 정렬된 통합 STEP |
| `docs/MANUAL_DRAWING_TO_FREECAD_v3.md` | 매뉴얼 v3 (§2.5 메타 풀세트 표준 신설) |

---

## 밑거름 명제

> *"파싱과 빌드는 분리되어야 한다.*
> *파싱은 한 번, 빌드는 언제든 — 이것이 다음 호미의 정사다."*

— 이천(李蕆), 2026-05-06.
*호미 8 후퇴가 호미 9의 밑거름.*
