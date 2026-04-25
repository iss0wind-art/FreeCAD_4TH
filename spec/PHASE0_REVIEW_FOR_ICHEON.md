# Phase 0 검토 자료 — 이천 부임 직후 검토용

> 작성: 2026-04-25 / 작성자: 본 세션 (이천 부임 전 임시 관리자)
> 수신: 이천(李蕆) 3지국 단군
> 목적: 본영 단군 동석 검토 4건의 사전 자료. **결정은 이천이 본영과 한다.**
> 근거: BOQ 실데이터 1,163건 샘플링 결과

---

## 검토 1 — M1 결정 (슬래브 두께 필드)

### 결론 후보
**슬래브의 두께는 `thickness` 필드를 사용한다.** (height, width는 0)

### BOQ 실데이터 증거 (57개 슬래브 샘플)

```
{symbol: '-1S1', thickness: 150, height: 0, width: 0, depth: 0, wallThk: 0}  # 지하 1층
{symbol: 'RS1',  thickness: 250, height: 0, width: 0, depth: 0, wallThk: 0}  # 옥상
{symbol: 'ES1',  thickness: 150, height: 0, width: 0, depth: 0, wallThk: 0}  # 평슬래브
{symbol: 'ES10', thickness: 210, height: 0, width: 0, depth: 0, wallThk: 0}  # 특수
```

**패턴**: 57개 전부 `thickness`만 채워져 있고, 다른 치수는 0.  
**값 분포**: 150mm (일반층) / 210mm (특수) / 250mm (옥상)

### Phase 0 산출물 영향
- [db_schema.sql](db_schema.sql) — 슬래브의 두께 매핑은 `thickness` 컬럼  ✅ 그대로 유효
- [member_manifest_schema.md](member_manifest_schema.md) §4.3 — 슬래브 polygon 배치 시 두께는 spec.thickness에서 자동 조회  ✅ 그대로 유효

### 이천이 본영에 결정받을 사항
- D1-1. `slab.height` 필드를 스키마에서 **삭제할지**(엄격) / 0으로 유지할지(관대)
- D1-2. 두께가 다른 슬래브가 한 층에 공존할 때 (현장 흔함) 표현 방법

---

## 검토 2 — 5종 스키마 검증 (실데이터 분포)

### 발견 1: **6번째 카테고리 존재** ⚠️

BOQ에는 5종이 아니라 **6종**이 있음:

| 종 | 개수 | 비율 |
|---|------|------|
| 보 | 788 | 67.8% |
| 기둥 | 289 | 24.8% |
| 슬라브 | 57 | 4.9% |
| 벽체 | 20 | 1.7% |
| 기초 | 6 | 0.5% |
| **테두리보** | **3** | **0.3%** |

→ Phase 0 스키마는 5종(BEAM/COLUMN/SLAB/WALL/FOUNDATION). **테두리보는 어디에 둘 것인가?**

#### 옵션 A: BEAM 안에 흡수 + subtype 필드
```yaml
type: beam
subtype: edge_beam   # 테두리보
```

#### 옵션 B: 별도 카테고리 신설
```sql
member_type IN ('BEAM','COLUMN','SLAB','WALL','FOUNDATION','EDGE_BEAM')
```

→ **본영 결정 필요**

### 발견 2: **단위 불일치** ⚠️

테두리보 데이터:
```
RWG1: width=0.5, height=0.9   # m 단위
RWG2: width=0.5, height=0.9   # m 단위
```

다른 보들:
```
RG1:  width=500, height=900   # mm 단위
```

→ **임포트 스크립트가 자동 정규화 필요** (값이 < 10이면 m 단위로 가정 → ×1000)

### 발견 3: **기초는 단일 스키마로 안 잡힘** ⚠️

```
PF1   (Pile Foundation):     width=3000, height=2800        # 정사각 매트
PWF1  (Pile Wall Foundation): length=1500, wallThk=900       # 벽 기초
FS1   (Foundation Slab):     thickness=350                   # 매트기초
RaWG1 (Ramp Wall Girder):    width=500, height=600           # 램프 보? (기초 분류됨)
```

→ **기초는 `subtype` 분기 필요**:
- `MAT` (매트기초) — thickness만
- `PILE_CAP` (말뚝머리 기초) — width × height
- `STRIP` (줄기초) — length × wallThk
- `RAMP` (램프 기초) — width × height (사실상 보)

### 이천이 본영에 결정받을 사항
- D2-1. 테두리보 처리 (BEAM 흡수 vs 별도)
- D2-2. 단위 정규화 규칙 (자동 변환 vs 임포트 거부)
- D2-3. 기초 subtype 분기 도입 여부

---

## 검토 3 — 그리드 다중성 재검토

### 현 스키마 한계 (Phase 0 가정)
**1개 프로젝트 = 1개 그리드 시스템**

```yaml
grid:
  origin: [0, 0]
  x_lines: { A: 0, B: 6000, ... }
  y_lines: { "1": 0, "2": 8000, ... }
```

### 현실 사례 (BOQ remark 증거)

기둥 데이터:
```
TC1, remark: '101동'
TC2, remark: '101동'
...
```

→ **아파트 단지: 동별로 다른 그리드 사용**

### 추가 현실 사례 (건축 일반)
1. **지하주차장 vs 지상층** — 다른 그리드 (램프 때문)
2. **부속동 (관리동·근린생활)** — 본동과 별개 그리드
3. **단지형 프로젝트** — 동별 회전 다름

### 옵션 분석

#### 옵션 A: 단일 그리드 유지 (Phase 0 그대로)
- 장점: 단순, 단일 건물 충분
- 단점: 단지형 처리 불가 → 절대 좌표(xy)로 폴백해야 함

#### 옵션 B: 다중 그리드 (zone 기반)
```yaml
zones:
  - id: "101동"
    grid: { origin: [0, 0], x_lines: {A:0,B:6000}, y_lines: {"1":0,"2":8000} }
  - id: "102동"
    grid: { origin: [50000, 0], rotation: 30, x_lines: {...}, y_lines: {...} }

members:
  - id: "C-A1-101-1F"
    zone: "101동"        # 어느 그리드 사용할지 명시
    floor: "1F"
    at: { grid: ["A", "1"] }
```

#### 옵션 C: 단일 그리드 + 다중 동 별도 프로젝트
- "101동" "102동"을 별도 project_id로 처리
- 단지 통합 보고는 상위 레벨에서 집계
- 단점: 하나의 단지 = 여러 manifest 파일

### 이천이 본영에 결정받을 사항
- D3-1. Phase 1 시점 그리드 다중성 도입 여부
  - 추천: **옵션 A 유지(Phase 1) + 옵션 B로 Phase 2 확장**
  - 근거: 시간 절약, 첫 검증 시나리오는 단일 건물

### Phase 0 산출물 영향
- 옵션 B 채택 시 → [member_manifest_schema.md](member_manifest_schema.md) 대폭 수정
- 옵션 A 유지 시 → 변경 없음 (Phase 2 백로그)

---

## 검토 4 — 본영 헌법/피지수 통합 지점

### 현 Phase 0 산출물 — 헌법 부재
지금까지의 5개 spec/ 파일은 **순수 기술 문서**. 다음이 빠져 있음:
- 0원칙(홍익인간) 어떻게 코드에 흐르는가
- 8조 금법(특히 7조 폭주 경계, 8조 악의 차단) 어디서 발동하는가
- 피지수 자율 협업 프로토콜 어디서 실행되는가
- 특허 3층 분류(BOQ 헌법 제11조)와 동일한 보호선이 FreeCAD_4th에도 필요한가

### 통합 후보 지점 6곳

#### G1. **API 입력 검증** (api/models.py)
- Pydantic으로 사용자 입력 검증 = 1원칙(해 끼치지 않기) 실무
- 추가 필요: **8조 8항(악의 차단)** — YAML 인젝션, SQL 인젝션 게이트

#### G2. **Reviewer 에이전트** (agents/reviewer.py)
- BOQItem 검증 → APPROVED/RETRY/HUMAN_REQUIRED
- 추가 필요: **8조 7항(폭주 경계)** — 비정상 체적/면적 시 즉시 HUMAN_REQUIRED

#### G3. **DB 스키마** (`projects.manifest_yaml` 보존)
- 원본 manifest 보존 = **사초청적 기록**(개정 추적)
- 추가 필요: 변경 이력(revision 테이블)

#### G4. **신규 — 보존선(BOQ 제11조 계승)**
- FreeCAD_4th에도 특허 직결 코드 분류 필요:
  - 🔴 **절대 보존층**: `core/polygon_clip.py`, `core/ray_cast.py` (Water Stamp 알고리즘)
  - 🟠 **재가 필요층**: `agents/executor.py`, `core/freecad_mesh.py`
  - 🟢 **자유 영역**: `api/`, `frontend/`, `pipeline/`
- 산출물: `spec/PRESERVATION_LINES.md` (이천이 본영과 작성)

#### G5. **CBF-QP 게이트** (운영 차원)
- DB drop, main push, prod deploy 등 **하드 게이트** 명시 필요
- 산출물: `spec/CBF_QP_GATES.md`

#### G6. **MCP 채널** (.claude/ 또는 .mcp.json)
- 이천이 본영 단군 호명할 수 있도록
- `mcp__dangun__dangun_brain` 등 활성화 필요

### 이천이 본영에 결정받을 사항
- D4-1. 6개 통합 지점 중 Phase 1 필수 vs Phase 2 이연
  - 추천: G1, G2, G6은 Phase 1 / G3, G4, G5는 Phase 2
- D4-2. 보존선(G4) 분류 — Water Stamp 알고리즘이 BOQ 특허에 묶여 있는데, FreeCAD_4th의 polygon_clip은 같은 청구항 범위인가?

---

## 종합 — 본영 동석 검토에서 결정해야 할 11개 항목

| # | 항목 | 추천 |
|---|------|------|
| D1-1 | slab.height 필드 처리 | 0으로 유지 (엄격은 Phase 2) |
| D1-2 | 한 층 다양 두께 슬래브 | manifest에서 슬래브별로 spec 다르게 (현재 가능) |
| D2-1 | 테두리보 카테고리 | 옵션 A (BEAM + subtype) |
| D2-2 | 단위 정규화 | 자동 변환 (×1000), 로그 기록 |
| D2-3 | 기초 subtype 분기 | Phase 2로 이연, Phase 1은 단일 FOUNDATION |
| D3-1 | 그리드 다중성 | 옵션 A 유지 (Phase 1), 옵션 B는 Phase 2 |
| D4-1 | 헌법 통합 6개 지점 | G1, G2, G6 Phase 1 |
| D4-2 | 보존선 분류 | 본영과 함께 특허 청구항 매핑 |
| - | M2 (보 length=0) | 확정: 배치 시 from-to 거리로 자동 계산 |
| - | M3 (instance_id 충돌) | 해결됨: (project_id, instance_id) 복합 PK |
| - | 단위 일관성 | mm 통일 (입력 m 허용 → 즉시 ×1000) |

---

## 검토 후 Phase 0 산출물 갱신 책임

이천이 본영과 11개 항목 결정 후:
1. [PHASE0_HANDOFF.md](PHASE0_HANDOFF.md) "결정 사항" 섹션 업데이트
2. 변경 사항 → [db_schema.sql](db_schema.sql) / [member_manifest_schema.md](member_manifest_schema.md) 반영
3. 새 결정 추가 시 → [PHASE0_REVIEW_DECISIONS.md](PHASE0_REVIEW_DECISIONS.md) 신설 권장
4. 그제서야 Phase 1 출발 (Forge `/orchestrate`)

---

## 참고 — BOQ 실데이터 위치

| 데이터 | 경로 |
|------|------|
| 1,163 spec 카탈로그 | `D:\GIT\BOQ\sketchup_plugins\boq_member_specs.json` |
| 부재 분류 로직 | `D:\GIT\BOQ\scripts\parse_dxf.py` `detect_member()` |
| 기존 BOQ 스키마 (참고) | `D:\GIT\BOQ\src\lib\db\schema.ts` |
| 특허 명세서 | `D:\GIT\BOQ\특허_기술명세서.md` |
| Water Stamp 알고리즘 | `D:\GIT\BOQ\sketchup_plugins\boq_easyframe\src\boq_easyframe\core\geometry_builder.rb` L89-223, 1244-1300 |
