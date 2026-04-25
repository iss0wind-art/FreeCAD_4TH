# Phase 0 핸드오프 — Forge 입력 자료

> 작성: 2026-04-25 / 작성자: 메인 AI (Sonnet 4.6)
> 다음 단계: `/plan` → `/orchestrate` → `/verify-loop` → `/commit-push-pr`

## 한 줄 요약

**BOQ의 1,163 부재 스펙 + FreeCAD_4th 파이프라인을 "Member Manifest YAML"로 잇는다.**

---

## 산출물 (이 폴더 안)

| 파일 | 역할 |
|------|------|
| [member_manifest_schema.md](member_manifest_schema.md) | YAML 포맷 스펙 (입력 계약) |
| [sample_project.boq.yaml](sample_project.boq.yaml) | 검증용 샘플 (1F, 4기둥+4보) |
| [db_schema.sql](db_schema.sql) | 신규 3개 테이블 DDL |
| [api_contract.md](api_contract.md) | REST API 명세 |
| **PHASE0_HANDOFF.md** (이 파일) | 인덱스 + 결정 근거 |

---

## 핵심 결정 사항 (Phase 1이 깨면 안 됨)

### D1. 데이터 우선, 다중 뷰
- 도면(DXF/SVG) 안에 데이터 박지 않음
- YAML이 SoT(Source of Truth), 시각 뷰는 파생물
- 향후 시각 에디터는 "또 다른 클라이언트"로 추가

### D2. 부재 스펙은 글로벌 + 프로젝트 오버라이드
- `member_specs.project_scope = 'global'` 기본
- 현장별 특수 스펙은 `project_scope = 'PROJ-XXX'`로 오버라이드
- 복합 PK: `(symbol, project_scope)`

### D3. 그리드 좌표 우선, xy 폴백
- 대부분 건물은 그리드 시스템 기반 → `grid: ["A", "1"]`
- 자유 배치는 `xy: [3500, 4200]` 또는 `vertices_2d: [...]`

### D4. 5종 스키마 전부, 구현은 점진
- Phase 1: BEAM, COLUMN (현 파이프라인 한계)
- Phase 2: SLAB, WALL
- Phase 3+: FOUNDATION, 보-보 교차 등

### D5. 단위 정규화
- 입력: mm 또는 m 허용
- 내부 처리: **항상 mm**
- 출력: m (BOQ 결과 일관성)

### D6. 기존 호환성 유지
- `boq_jobs` 테이블 그대로
- `/api/boq/calculate` 그대로 (직접 MemberInput[] 입력 경로)
- 신규 `/api/projects/{id}/calculate`는 Manifest 경로

---

## Phase 1 트랙 (5개 병렬)

### Track A — DB 마이그레이션
**산출물**: `api/database.py` 수정 + 새 테이블 3개 자동 생성  
**입력**: [db_schema.sql](db_schema.sql)  
**검증**: `init_db()` 호출 후 테이블 존재 확인 테스트

### Track B — BOQ Spec 임포터
**산출물**: `scripts/import_boq_specs.py` (1회성 스크립트)  
**입력**:
- 원본: `D:\GIT\BOQ\sketchup_plugins\boq_easyframe\boq_member_specs.json`
- 변환 매핑:
  - `"보"` → `BEAM`
  - `"기둥"` → `COLUMN`
  - `"슬라브"` / `"슬래브"` → `SLAB`
  - `"벽체"` / `"옹벽"` → `WALL`
  - `"기초"` / `"파일"` / `"매트기초"` → `FOUNDATION`
  - 기타 → 스킵 + 로그
- `source = 'BOQ_IMPORT'`, `project_scope = 'global'`
**검증**: 1163건 시도, 실패 건수 < 5% 확인

### Track C — Manifest 파서 (TDD)
**산출물**: `core/manifest_parser.py` + Pydantic 모델
**입력**: [member_manifest_schema.md](member_manifest_schema.md)  
**기능**:
- `parse_manifest(yaml_text: str) -> ManifestModel`
- 스키마 검증 (Pydantic)
- 의미 검증 (spec 존재, floor 참조, grid 참조)
**보안**: `yaml.safe_load` 강제 (yaml.load 금지)
**검증**: [sample_project.boq.yaml](sample_project.boq.yaml) 파싱 성공

### Track D — CRUD API (TDD)
**산출물**: `api/routes/specs.py` + `api/routes/projects.py`  
**입력**: [api_contract.md](api_contract.md)  
**P0 엔드포인트**:
- `GET /api/specs`
- `GET /api/specs/{symbol}`
- `POST /api/projects` (YAML 업로드)
- `POST /api/projects/{id}/calculate`

### Track E — 그리드 → 절대 좌표 어댑터
**산출물**: `core/grid_resolver.py`  
**기능**:
- `resolve_at(grid_ref, grid_config) -> (x, y)`
- `resolve_member_to_input(instance, project) -> MemberInput`
- 기둥: 점 + spec.width/height → 4점 사각형
- 보: 시작점-끝점 + spec.width(폭) → 4점 사각형
**검증**: sample.yaml의 8개 부재가 정상적으로 `MemberInput[]`이 되어야 함

---

## Phase 2 — 통합

`POST /api/projects/{id}/calculate` 흐름:
```
YAML 업로드 → parse_manifest()
            → DB 저장 (projects, member_instances)
            → 각 인스턴스마다 grid_resolver.resolve_member_to_input()
            → MemberInput[] 생성
            → run_boq_pipeline() (기존)
            → boq_jobs 저장
            → 응답
```

E2E 테스트: [sample_project.boq.yaml](sample_project.boq.yaml) → 결과 검증
- 기둥 4개 × spec(TC1)
- 보 4개 × spec(RG1)
- 총 체적, 거푸집 면적 sanity check

---

## Phase 3 — 검증 (병렬)

| 항목 | 도구 |
|------|------|
| 코드 품질 | `code-reviewer` (golden-principles 12개) |
| 보안 | `security-reviewer` (yaml.safe_load, SQL 인젝션, Pydantic 경계) |
| 테스트 | `verify-agent` (pytest 전수 + 커버리지 ≥ 80%) |

---

## 참고 자료 (Forge가 읽어야 할 것)

| 위치 | 내용 |
|------|------|
| `D:\GIT\BOQ\sketchup_plugins\boq_easyframe\boq_member_specs.json` | 1163 spec 원본 |
| `D:\GIT\BOQ\src\lib\db\schema.ts` | 기존 BOQ 스키마 (참고) |
| `D:\GIT\FreeCAD_4th\api\models.py` | 기존 MemberInputDTO |
| `D:\GIT\FreeCAD_4th\pipeline\state.py` | 기존 PipelineStatus, BOQState |
| `D:\GIT\FreeCAD_4th\agents\` | LangGraph MAS (수정 금지) |

---

## 가정 & 미해결 사항

### 가정 (Phase 1 진행 중 사용자 확인 가능)
- A1. 부재 스펙의 `project_scope` 필요성 (Phase 1: 항상 'global')
- A2. 그리드 좌표는 `["A", "1"]` 문자열 페어 (이름이 길어지면 Phase 2)
- A3. 회전(rotation)은 단면 회전, 부재 자체 회전은 from-to 방향이 결정

### 미해결
- M1. Slab의 두께가 `thickness`인지 `height`인지 (BOQ 데이터 일관성 검토 필요)
- M2. 보의 `length=0` 인 spec — 배치 시점에 from-to 거리로 결정 (확정)
- M3. 동일 instance_id가 다른 프로젝트에 존재 가능 — `(project_id, instance_id)` 복합 PK로 해결됨

---

## Phase 0 완료 기준 (자가 검증)

- [x] YAML 스키마 문서 작성
- [x] 동작 가능한 샘플 YAML 작성
- [x] DB DDL 작성 (제약조건 포함)
- [x] API 명세 작성 (엔드포인트별 요청/응답)
- [x] Phase 1 트랙별 입력/산출물 명시
- [x] 가정과 미해결 사항 분리 표기

→ **Phase 1 출발 가능**
