# FreeCAD BOQ 자동화 — Forge 기획안

> 작성: 이천(李蕆), 신고조선 제3지국 단군  
> 날짜: 2026-05-07  
> 대상: Claude Forge 에이전트 군

---

## 1. 한 줄 목표

**건축 구조 도면(DXF) → 부재별 완전한 3D 모델(STEP) + 수량산출서(BOQ) 자동 생성**

---

## 2. 왜 만드는가

건설 공무에서 BOQ(자재 수량표)는 사람이 도면을 읽고 손으로 집계한다.
이 프로젝트는 그 과정을 자동화한다.

- 입력: 구조도 DXF 2장 (101동 + 지하주차장)
- 출력: 부재별 ID가 붙은 STEP 파일 + JSON/CSV BOQ

형제 지국 정도전(1지국)의 SketchUp 버전과 동일한 목적, FreeCAD 버전.

---

## 3. 투트랙 전략 (핵심)

같은 목표를 두 가지 경로로 동시에 공략한다.
어느 트랙이 먼저 목표에 도달하든 그것이 정답이다.

```
DXF 원본
  │
  ├─── [Track 1: 직접 투입] ──────────────────────────────────────────►
  │        DXF 그대로 → 레이어 필터 → 부재 추출 → 솔리드 생성 → STEP+BOQ
  │        장점: 빠름, 단순
  │        리스크: 잡선 혼입, Z 부정확, 겹침 솔리드
  │
  └─── [Track 2: 도면 가공 후 투입] ──────────────────────────────────►
           DXF → 가공 5단계 → 정제 데이터 → 솔리드 생성 → STEP+BOQ
           장점: 정밀, 완결성 높음
           리스크: 가공 단계에서 막히면 지연

목표는 동일:
  ✅ 완전한 3D 모델 (COLUMN + BEAM + WALL + SLAB, 부재별 ID)
  ✅ 수량산출서 (체적 m³ / 면적 m² 전수)
```

---

## 4. Track 1 — 직접 투입

> DXF 원본을 그대로 파이프라인에 던진다.
> 지금 `v9_clean.step` (7,411 솔리드)이 이 방식의 현재 수준이다.

### 현재 상태

```
DXF 2장
  └─ stage0: 층고 파싱            ✅ output/stage0_levels.json
  └─ stage1: 골조 레이어 필터      ✅ output/stage1_filter.json
  └─ stage2: 부재 분류            ✅ 25,219건 전수 (COLUMN/BEAM/WALL/SLAB/FND)
  └─ stage3: 좌표 통일            ✅ output/coord_config.json (오차 0.2mm)
  └─ stage4: BOQ 집계             ✅ output/members_boq.json
  └─ stage5: FreeCAD STEP 빌드    ⚠️ v9 7,411 솔리드 (WALL·SLAB 미포함)
```

### 확정 좌표 (재사용 필수)

```python
TX_PKG = -447_970   # mm — 기둥 143쌍 매칭, 오차 0.2mm
TY_PKG = +3_621_813 # mm
TZ_B1F = -5_600     # mm — DXF 단면도 직독
TZ_B2F = -9_050     # mm — DXF 단면도 직독
```

### Track 1 미완성 항목

| 항목 | 현황 | 해결 방향 |
|------|------|-----------|
| WALL 솔리드 | 분류 17,057건, STEP 미생성 | LINE 쌍 → 두께·높이 makeBox |
| SLAB 솔리드 | PKG 279건, STEP 미생성 | LWPOLYLINE → extrude |
| 보-기둥 매입 | isolated 3,188개 | 기둥 bbox 경계로 보 트리밍 |
| XRef RC벽 오프셋 | isolated 2,189개 | INSERT 엔티티 오프셋 역적용 |

### Track 1 에이전트 (T1-A, T1-B, T1-C)

**T1-A: WALL + SLAB 솔리드 생성기**
- `members_accumulated.json` WALL/SLAB 데이터 → FreeCAD makeBox
- 완료 기준: WALL 17,057 + SLAB 279 솔리드 전수 STEP 포함

**T1-B: 보-기둥 매입 트리머**
- COLUMN bbox 추출 → BEAM 끝점이 bbox 안이면 외벽 교차점으로 트리밍
- 완료 기준: isolated `00_BEAM` 3,188 → 500 이하

**T1-C: XRef 오프셋 보정기**
- DONG DXF `INSERT` 엔티티에서 XRef 오프셋 읽기 → RC벽 좌표 역보정
- 완료 기준: DONG XRef RC벽 isolated 2,189 → 200 이하

---

## 5. Track 2 — 도면 가공 후 투입

> DXF를 그대로 쓰지 않는다. 먼저 정제한 뒤 솔리드를 만든다.
> 가공 5단계를 거치면 잡선·Z 부유·겹침이 모두 제거된 깨끗한 골조선이 나온다.

### 도면 가공 5단계 (순서 엄수)

```
Step 1. 골조선 추출
        DXF 레이어 필터 → 구조 부재 선분만 (S-*, A-WALL-RC, 00_BEAM 등)
        현재 구현: stage1_structural_filter.py + skeleton_dong/pkg_b1f.dxf ✅

Step 2. Z=0 강제
        모든 선분의 Z값을 0으로 고정 (떠있는 선 전부 바닥으로)
        현재 구현: skeleton 에이전트 적용 완료 ✅

Step 3. 겹침 제거
        양 끝점 거리 < 5mm → 중복 선분 제거
        평행 근사 겹침 (간격 < 50mm, 같은 방향) → 중간값 통합
        현재 구현: skeleton 에이전트 완료 ✅ (clean_lines 87,279개)

Step 4. 끊어진 곳 연결
        자동 연결 조건 (동시 만족 필수):
          - 방향 일치: 각도 차 < 5°
          - 갭 크기: gap < 기둥 한 변 (500~800mm)
        아무 선이나 연결하지 않는다 — 조건 미달이면 isolated로 격리
        현재 구현: 미완 ⚠️

Step 5. 부재별 2차 추출 (옵션)
        정제된 골조선을 COLUMN 위치·BEAM 방향·WALL 두께로 재분류
        members_accumulated.json과 교차 검증
        현재 구현: 미완 ⚠️
```

### 직접 그리기 (최후 수단, 이 방법이 가장 나을 수도 있다)

Step 4에서 자동 연결이 안 되는 구간이 남으면:
- 해당 구간 바운딩박스 출력
- **직접 레이어를 만들어서 인접 기둥 중심점을 연결하는 선을 그린다**
- `SKELETON_MANUAL` 레이어에 저장
- 기둥 중심점은 `members_accumulated.json`에 이미 있다 — 추측 불필요

### Track 2 에이전트 (T2-A, T2-B)

**T2-A: 끊어진 곳 연결기 (Step 4)**
- 입력: `skeleton_dong_b1f.dxf`, `skeleton_pkg_b1f.dxf`
- 조건: 방향 차 < 5° AND gap < 800mm 동시 만족할 때만 연결
- 나머지: `SKELETON_ISOLATED` 유지 + 바운딩박스 출력
- 자동 연결 후에도 남는 isolated 구간 → `SKELETON_MANUAL` 레이어에 기둥-기둥 직선 삽입
- 완료 기준: isolated 총 16,455 → 2,000 이하

**T2-B: 정제 골조선 → STEP 솔리드 빌더 (Step 5 + STEP 생성)**
- 입력: T2-A 산출 정제 DXF
- `members_accumulated.json` 단면 치수 매핑
- FreeCAD COLUMN + BEAM + WALL + SLAB 전수 솔리드
- 완료 기준: 솔리드 수 > 20,000 + BOQ 전수

---

## 6. 공통 규칙 (두 트랙 모두 적용)

### 절대 금지
- 추측값 사용 금지 — `coord_config.json` 확정값만 사용
- 대충 일부만 처리 금지 — count=0이면 반드시 FAIL 보고
- Z값 임의 지정 금지 — `stage0_levels.json` 직독
- 기존 `core/` 모듈 무단 수정 금지 — 확장만 허용

### 작업 원칙
- 느려도 좋다. 정확하게.
- 하나씩 확실하게 처리. 한꺼번에 대충 말고.
- 못 처리한 케이스는 FAIL로 명시. 숨기지 말 것.
- 각 부재 고유 ID 필수 (COL-0001, BEAM-0001, WALL-0001 형식)

---

## 7. 기술 스택

| 항목 | 값 |
|------|-----|
| Python | 3.11 |
| DXF 파싱 | ezdxf |
| 3D 솔리드 | FreeCAD 1.1 (`freecadcmd.exe`) |
| 실행 경로 | `"C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" script.py` |
| 작업 디렉토리 | `D:\Git\FreeCAD_4TH` |
| DXF_DONG | `D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf` |
| DXF_PKG | `D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf` |

---

## 8. 현재 산출물 (두 트랙 공용 자산)

```
output/
  coord_config.json          — TX/TY/TZ 확정값 (confidence=high)
  stage0_levels.json         — B2F -9,050mm / B1F -5,600mm
  members_accumulated.json   — 25,219건 부재 (ID·좌표·단면 포함)
  members_boq.json           — 타입별 BOQ
  skeleton_dong_b1f.dxf      — 101동 골조선 clean 48,803선
  skeleton_pkg_b1f.dxf       — 지하주차장 골조선 clean 38,476선
  v9_clean.step              — 현재 최신 STEP (7,411 솔리드)
```

---

## 9. 완료 기준 (Definition of Done) — 두 트랙 공통

1. **STEP**: COLUMN + BEAM + WALL + SLAB 전수 포함 (DONG + PKG, B1F + B2F)
2. **BOQ**: 부재별 고유 ID + 체적(m³) / 면적(m²) 전수, JSON + CSV
3. **좌표 정합**: verify_coords.py 오차 < 100mm
4. **누락 0건**: 모든 부재 타입 count > 0
5. **검증 증거**: "완료 추정" 금지 — 실행 결과 수치 제시 필수

---

*홍익인간이 모든 결정에 우선한다. — 이천(李蕆), 2026-05-07*
