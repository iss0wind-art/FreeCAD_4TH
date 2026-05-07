# 구현 계획 — FreeCAD BOQ 자동화 투트랙

> 확정: 2026-05-07
> 단군: 이천(李蕆), 신고조선 제3지국
> 기획안: docs/forge_brief.md

---

## 전체 그림

```
                    ┌─ Track 1 (직접 투입) ─────────────────────┐
DXF + 기존 자산 ─────┤                                           ├─► STEP + BOQ
                    └─ Track 2 (도면 가공) ─────────────────────┘
```

---

## 공통 인프라 (먼저 추출)

| 파일 | 내용 |
|------|------|
| `core/pipeline/boq_solid_builder.py` | `box_solid`, `beam_solid`, `prism_solid`, `export_step`, `export_boq_json/csv` 단일 정의 |
| `core/pipeline/member_data.py` | `Member` 데이터클래스 단일 정의 |

현재 v7·v9·v11 빌드 스크립트에 중복 정의된 함수들을 단일화.

---

## Track 1 — DXF 직접 투입

`members_accumulated.json` 25,219건 → 솔리드.

| Phase | 파일 | 내용 | 완료 기준 |
|-------|------|------|-----------|
| **1-A** | `tests/build_v10_wall_solid.py` | WALL 두께 보강(wall_extractor) → 솔리드 | WALL 솔리드 14,000건+ |
| **1-B** | `tests/build_v10_slab_pkg.py` | PKG SLAB 격자 패널 | 패널 800개+ |
| **1-C** | `tests/export_boq_final_t1.py` | BOQ 통합 (JSON+CSV) | 전 타입 count > 0 |
| **1-D** | `tests/build_final_track1.py` | STEP 최종 통합 | `final_track1.step` > 50MB |

**리스크**: F-2 XRef RC벽 2,189건 — `entity_scanner.py` INSERT 재귀 시 xref_offset 누적 미적용.

---

## Track 2 — 도면 가공 후 투입

골조선 Step 4~5 → 부재 재추출 → STEP.

| Phase | 파일 | 내용 | 완료 기준 |
|-------|------|------|-----------|
| **2-A** | `tests/skeleton_step4_connect.py` | 끊어진 선 연결 (방향<5° + gap<800mm) | isolated 70%+ 연결 |
| **2-B** | `tests/skeleton_step5_manual_col_col.py` | 자동 불가 → 기둥-기둥 직선 | MANUAL 선 500개+ |
| **2-C** | `core/pipeline/stage3_skeleton_to_members.py` | 정제 골조선 → 부재 재추출 | BEAM 6,000+, WALL 15,000+ |
| **2-D** | `tests/build_final_track2.py` | 최종 STEP + BOQ | `final_track2.step` > 80MB |

---

## 실행 순서

```
[Step 0] 공통 인프라 추출 (boq_solid_builder, member_data)
   │
   ├── [Step 1] Track 1 시작
   │     1-A (WALL) ──┐
   │     1-B (SLAB) ──┼── 1-C (BOQ) ── 1-D (STEP)
   │
   └── [Step 2] Track 2 시작 (1-A 완료 후 2-B 시작)
         2-A (선 연결) ── 2-B (기둥-기둥) ── 2-C (재추출) ── 2-D (STEP)
```

---

## FAIL 해소 전략

| FAIL | Track 1 | Track 2 |
|------|---------|---------|
| F-1: 보-기둥 매입 | BOQ 정확, STEP 끝점 truncation | gap 800mm 연결로 75% 해소 |
| F-2: XRef RC벽 | INSERT 오프셋 누적 수정 | skeleton DXF가 이미 적용 → 자동 해소 |
| F-3: 골조선→STEP | 우회 (members_accumulated 직접) | 트랙 자체가 해결 |
| F-4: DONG 슬라브 | 면적 0 표기 | 동일 |

---

## 완료 기준 (두 트랙 공통, DOD)

1. **STEP**: COLUMN+BEAM+WALL+SLAB 전수 포함 (DONG+PKG, B1F+B2F)
2. **BOQ**: 부재별 고유 ID + 체적/면적, JSON + CSV
3. **검증**: `verify_coords.py` 오차 < 100mm
4. **누락 0건, 추측값 0건**

---

## 절대 금지 (공통 규칙)

- 추측값 사용 금지 — `coord_config.json` 확정값만
- 대충 일부만 처리 금지 — count=0이면 FAIL 보고
- Z값 임의 지정 금지 — `stage0_levels.json` 직독
- 기존 `core/` 모듈 무단 수정 금지 — 확장만 허용

---

*홍익인간이 모든 결정에 우선한다.*
