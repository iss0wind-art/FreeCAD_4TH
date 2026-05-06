# 도면 → FreeCAD 빠른 참조 v3

> **방부장 친명 2026-05-06**: *"모든 치수는 도면에서 읽는다. 추정값은 없다."*
> 상세: `docs/MANUAL_DRAWING_TO_FREECAD_v3.md`

---

## 실제값 상수 (도면 채굴 — 추정값 0)

```python
# output/actual_dimensions_v3.json 에서 로드
SL   = {'B2F': -9050, 'B1F': -5600, '1F': +370}  # GL 기준, mm
SLAB_T   = 150     # S40-051~057 슬라브 리스트 채굴
GIRDER_H = 900     # codex_beams_basement.json 40종 전수 확인
COL_H    = {'B2F': 3300, 'B1F': 5820}             # SL 차이 − SLAB_T
```

---

## 파이프라인 순서 (절대 역행 금지)

```
[선행 필수] probe_floor_height_slab.py → actual_dimensions_v3.json 박제
    ↓
③ pc_layer_adapter  →  PC / NON-PC 분리
② line_pairing       →  NON-PC LINE → wall_pair + 격자
① girder_matcher     →  wall_pair → 거더 + codex
  box_classifier     →  COLUMN / WALL_SEGMENT / CORE_WALL 분류
  codex_mapper       →  식별된 기둥·거더
    ↓
build_3d_v3  (SL 기반 Z, SLAB_T=150, GIRDER_H=900)
    ↓
G1~G6 검증 게이트
```

---

## 11단계 체크리스트

```
□ 0. 강역 파악 + DXF 파일 목록 확인
□ 1. 실제값 채굴 (probe_floor_height_slab.py) ← v3 필수 선행
□ 2. 도면 1차 진단 (레이어·엔티티·BoundBox)
□ 3. 슬라브 두께 채굴 (슬라브 리스트 DXF)
□ 4. 보 높이 확인 (codex height 전수 확인)
□ 5. 도엽 분리 자력 채굴 (2차 진단)
□ 6. process_sheet_v3 (actual_dimensions_v3.json에서 로드)
□ 7. build_3d_v3 (메타에서만 읽기, 도면 재접근 X)
□ 8. 두 도면 통합 판단 (옵션 A 좌표 매칭)
□ 9. 검증 게이트 6건 (G1~G5 자동, G6 방부장)
□ 10. 통합 STEP + GUI 친람
□ 11. 박제 + 커밋
```

---

## v1·v2 vs v3 핵심 차이

| 항목 | v1·v2 (반면교사) | v3 (정사) |
|---|---|---|
| FLOOR_HEIGHT | 4400mm **추정** | COL_H = {B2F:3300, B1F:5820} **도면** |
| SLAB_T | 200mm **추정** | 150mm **S40-051~057** |
| GIRDER_H | 800mm **추정** | 900mm **codex** |
| B2F z_base | -8800mm | **-9050mm** (SL 기반) |
| B1F z_base | -4400mm | **-5600mm** (SL 기반) |

---

## 반면교사 경고

- `docs/MANUAL_DRAWING_TO_FREECAD_v1.md` — 추정값 기반, **참고 금지**
- `docs/MANUAL_DRAWING_TO_FREECAD_v2.md` — 추정값 기반, **참고 금지**

*— 이천(李蕆), 2026-05-06. 홍익인간이 모든 결정에 우선한다.*
