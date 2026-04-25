# Phase 0 검토 결재서 — 이천(李蕆) 2차 세션

> **결재자**: 이천(李蕆), 신고조선 제3지국 단군
> **결재일**: 2026-04-26
> **근거 자료**: [PHASE0_REVIEW_FOR_ICHEON.md](PHASE0_REVIEW_FOR_ICHEON.md)
> **결재 범위**: 11개 결정 항목 중 단독 결재 가능 10건 — 본영 헌법 정렬·8조 금법·BOQ 실데이터 증거에 근거
> **본영 결재 대기**: D4-2 (보존선 특허 청구항 매핑) — R5 응답 후 추가 결재

본 결재서는 **자체 진행 모드**에서 작성되었다. 본영 paperclip 쓰기 채널 stale로 동석 결재가 불가능한 상황에서, 이천이 자율도 ★★★ 권한으로 단독 결재 가능 항목을 우선 봉인한다. 본영 단군은 사후 검토·번복 권한을 보유한다.

---

## D1-1. `slab.height` 필드 처리

| 항목 | 값 |
|------|---|
| **결재** | **0으로 유지** (엄격 삭제는 Phase 2로 이연) |
| **근거** | BOQ 실데이터 57개 슬래브 전부 `height=0`. 엄격 삭제는 BOQ 임포트 호환성을 깬다 |
| **이천 사상** | *갑인자는 계미자를 부수지 않았다* — 기존 데이터 형식 유지 + thickness 신설로 정교화 |
| **반영** | [db_schema.sql](db_schema.sql) `slab.height` 컬럼 유지 (NOT NULL DEFAULT 0). [member_manifest_schema.md](member_manifest_schema.md) §4.3 두께는 `spec.thickness` 우선 조회 |
| **Phase 2 백로그** | 엄격 모드 옵션 추가 (입력 시 height/width 비0 → 거부) |

---

## D1-2. 한 층에 다양 두께 슬래브 공존

| 항목 | 값 |
|------|---|
| **결재** | **manifest에서 instance별 spec_id 다르게 부여** (현 스키마로 처리 가능) |
| **근거** | 현 Phase 0 스키마가 `instance_id → spec_id` 매핑을 지원. 한 층에 ES1/ES10 공존도 instance마다 다른 spec_id로 표현 가능 |
| **반영** | 별도 변경 불필요. 샘플 yaml에 다중 두께 슬래브 케이스 추가 권장 (P2) |
| **검증 시나리오** | Phase 1 통합 테스트에 "한 층 두 두께" 케이스 1건 포함 |

---

## D2-1. 테두리보(EDGE_BEAM) 카테고리 처리

| 항목 | 값 |
|------|---|
| **결재** | **옵션 A — BEAM 흡수 + `subtype: edge_beam` 필드** |
| **근거** | 테두리보는 1,163 중 3개 (0.3%) — 6번째 카테고리 신설 비용이 과대. subtype 패턴은 기초(D2-3)·향후 확장과도 일관 |
| **반영** | [db_schema.sql](db_schema.sql) `members.subtype VARCHAR(32) NULL` 컬럼 추가 (NULL 허용 — 일반 보는 비움). [member_manifest_schema.md](member_manifest_schema.md) §보 스키마 `subtype` 옵션 명시 |
| **enum 후보** | `edge_beam`, `transfer_beam`, `cantilever_beam` (Phase 2 확장) |

---

## D2-2. 단위 정규화 규칙

| 항목 | 값 |
|------|---|
| **결재** | **자동 변환 (×1000) + 로그 기록** |
| **근거** | 임포트 거부 시 데이터 손실. 테두리보 m 단위(0.5, 0.9)와 다른 보 mm 단위(500, 900) 혼재가 BOQ 실데이터에 존재 |
| **변환 임계값** | **수치 < 10이면 m 단위로 가정 → ×1000** |
| **반영** | 임포트 스크립트에 `normalize_to_mm()` 함수 추가. 변환된 모든 값을 `import_log` 테이블에 기록 (변환 전·후·근거값) |
| **8조 금법 정렬** | 7조 폭주 경계 — 임계값을 벗어난 단위(예: 100,000mm = 100m 보)는 **HUMAN_REQUIRED** 발동, 임포트 거부 |

---

## D2-3. 기초(FOUNDATION) subtype 분기

| 항목 | 값 |
|------|---|
| **결재** | **Phase 1 단일 FOUNDATION 유지 / Phase 2 subtype 분기 도입** |
| **근거** | 기초는 6개 (0.5%). Phase 1 검증 시나리오(단일 건물 단일 그리드)에 4종 subtype(MAT/PILE_CAP/STRIP/RAMP)을 모두 노출하면 검증 부담만 늘고 실수익 적음 |
| **Phase 1 처리** | 기초 6건은 가용 필드(thickness 또는 width×height)로 단순 부피만 산출. RaWG1(램프 보)는 사실상 보이므로 임포트 시 **WARN 로그**로 사용자에게 분류 재검토 권고 |
| **Phase 2 백로그** | `foundation_subtype` enum: `MAT`, `PILE_CAP`, `STRIP`, `RAMP_GIRDER` |

---

## D3-1. 그리드 다중성

| 항목 | 값 |
|------|---|
| **결재** | **Phase 1 — 옵션 A (단일 그리드) 유지. Phase 2 — 옵션 B (zones 기반 다중 그리드) 도입** |
| **근거** | 단지형(아파트 101동/102동)은 BOQ remark에 증거가 있으나, Phase 1 검증 시나리오는 단일 건물에 한정. 다중 그리드는 Member Manifest 표준 자체를 대폭 수정해야 함 — Phase 1 안정 확보 후 진행 |
| **Phase 1 폴백** | 단지형 입력 시 `project_id`를 동별로 분리 (옵션 C) — 단지 통합 보고는 상위 레벨에서 집계 |
| **Phase 2 백로그** | [member_manifest_schema.md](member_manifest_schema.md) `zones[]` 신설, instance에 `zone_id` 참조. 동별 origin·rotation 지원 |

---

## D4-1. 헌법/피지수 통합 6개 지점 우선순위

| 항목 | 값 |
|------|---|
| **결재** | **Phase 1: G1, G2 / Phase 1 (조건부): G6 / Phase 2: G3, G4, G5** |
| **G1 — API 입력 검증 (api/models.py)** | Phase 1 필수. Pydantic + YAML/SQL 인젝션 게이트 (8조 8항) |
| **G2 — Reviewer 에이전트 (agents/reviewer.py)** | Phase 1 필수. 비정상 체적·면적 시 즉시 HUMAN_REQUIRED (8조 7항) |
| **G6 — MCP 채널 (.mcp.json)** | Phase 1 조건부 — **본영 R4(dangun_brain 수리) 응답 도착 후 즉시 활성**. 채널 살아 있어야 호명 가능 |
| **G3 — DB revision 테이블** | Phase 2 (사초청적 변경 이력) |
| **G4 — 보존선 PRESERVATION_LINES.md** | Phase 2. **D4-2와 직결, 본영 R5 응답 필요** |
| **G5 — CBF-QP Gates** | Phase 2 (운영 차원 하드 게이트) |

---

## D4-2. 보존선 분류 — 보류

| 항목 | 값 |
|------|---|
| **결재** | **본영 R5 응답 대기** |
| **사유** | Water Stamp 알고리즘이 BOQ 특허에 묶여 있는지(청구항 범위), FreeCAD_4th의 `core/polygon_clip.py`·`core/ray_cast.py`가 같은 청구항에 해당하는지 — 본영 단군의 **특허 청구항 매핑 직접 판단** 필요. 이천 단독 결재 권한 밖. |
| **본영 산출물 대기** | `D:\GIT\dream-fac\WATER_STAMP_POLYGON_CLIP_MAPPING.md` |
| **도착 후 절차** | 1) 본영 매핑 정독 → 2) `spec/PRESERVATION_LINES.md` 신설 (3색 분류: 🔴절대/🟠재가/🟢자유) → 3) 본 결재서에 D4-2 추가 결재 |

---

## M2. 보 `length=0` 문제

| 항목 | 값 |
|------|---|
| **결재** | **이미 결정 — 봉인** |
| **내용** | 보의 길이는 manifest 배치 시 `from`–`to` 양 끝 좌표 거리로 자동 계산. spec 카탈로그 `length` 필드는 무시 (참고용 0 허용) |

---

## M3. `instance_id` 충돌

| 항목 | 값 |
|------|---|
| **결재** | **이미 결정 — 봉인** |
| **내용** | `members` 테이블 PK = `(project_id, instance_id)` 복합. 같은 프로젝트 내 유일성만 보장. 프로젝트 간 instance_id 중복 허용 |

---

## 단위 일관성 (수도 표준)

| 항목 | 값 |
|------|---|
| **결재** | **mm 통일** |
| **입력 허용** | YAML/JSON 입력 시 m 단위 허용 (자동 변환, D2-2 참조) |
| **DB 저장** | 모두 mm (정수 또는 0.01mm 정밀도 부동소수) |
| **API 응답** | mm (소비자 측 변환 책임) |
| **3D 좌표계** | FreeCAD/Three.js mm 단위 통일 |

---

## 결재 후 갱신 책임

본 결재 후 즉시 또는 Phase 1 시작 전:

1. ✅ 본 결재서 봉안 (`spec/PHASE0_REVIEW_DECISIONS.md`)
2. ⏳ [PHASE0_HANDOFF.md](PHASE0_HANDOFF.md) "결정 사항" 섹션 본 결재 반영 (Phase 1 직전)
3. ⏳ [db_schema.sql](db_schema.sql) — D2-1 `subtype` 컬럼 추가, D1-1 `slab.height` 유지 명시
4. ⏳ [member_manifest_schema.md](member_manifest_schema.md) — `subtype`·단위 정규화·zones 백로그 명시
5. ⏳ R5 도착 시 D4-2 추가 결재 + `spec/PRESERVATION_LINES.md` 신설

---

## 본 결재의 자기 검증

| 점검 | 답 |
|------|---|
| 0원칙(홍익인간) 정렬? | ✅ — 데이터 손실 방지(D2-2), 검증 시나리오 단순화(D2-3, D3-1)로 시스템 신뢰성 확보 |
| 8조 금법 위반? | ❌ — D2-2 7조(폭주 경계) 적극 반영, D4-2(특허 직결)는 본영 결재로 8조 4항(역할 존중) 정렬 |
| 갑인자 사상(부수지 않고 정교화)? | ✅ — D1-1 height 유지, D2-1 subtype으로 BEAM 확장, M2/M3 기존 결정 봉인 |
| 본영 자율도 침범? | ❌ — D4-2 본영 결재 보류. 다른 항목은 자율도 ★★★ 권한 내 |
| 사초청 본관 침입? | ❌ — 본 결재는 spec/ 영역 한정 |

---

**이천(李蕆) 手印**
*신고조선 제3지국 단군*
*2026-04-26 KST*

*弘益人間. 同而不同. 一心.*
