# API Contract v2 — Phase 0 산출물

> 신규 엔드포인트 명세. 기존 `/api/boq/*`는 그대로 유지(하위 호환).

## 베이스 URL

```
http://localhost:8000/api
```

## 인증

Phase 1: 없음 (로컬 단독). Phase 4+ 도입 예정.

---

## 1. Member Specs (부재 표준 스펙)

### `GET /api/specs`
부재 스펙 목록 조회.

**쿼리 파라미터**:
| 이름 | 타입 | 기본 | 설명 |
|------|------|------|------|
| `type` | string | - | BEAM\|COLUMN\|SLAB\|WALL\|FOUNDATION |
| `scope` | string | `global` | 프로젝트 ID 또는 `global` |
| `symbol` | string | - | LIKE 검색 (`RG%`) |
| `limit` | int | 100 | 최대 1000 |
| `offset` | int | 0 | |

**응답 200**:
```json
{
  "items": [
    {
      "symbol": "RG1",
      "member_type": "BEAM",
      "width": 500,
      "height": 900,
      "depth": 0,
      "thickness": 0,
      "length": 0,
      "wall_thickness": 0,
      "project_scope": "global",
      "remark": "",
      "source": "BOQ_IMPORT"
    }
  ],
  "total": 1163,
  "limit": 100,
  "offset": 0
}
```

### `GET /api/specs/{symbol}`
단건 조회. 쿼리 `?scope=global` 가능.

**응답 200**: 단일 spec 객체.  
**응답 404**: 존재하지 않음.

### `POST /api/specs`
신규 등록 (커스텀 스펙).

**요청 본문**:
```json
{
  "symbol": "RG_CUSTOM_1",
  "member_type": "BEAM",
  "width": 450,
  "height": 850,
  "project_scope": "PROJ-2026-001",
  "remark": "현장 특수 보"
}
```

**응답 201**: 생성된 spec.  
**응답 409**: `(symbol, project_scope)` 중복.

### `PUT /api/specs/{symbol}`
수정. `?scope=...` 필수.

### `DELETE /api/specs/{symbol}`
삭제. `?scope=...` 필수. `global` 스코프는 관리자 모드에서만(Phase 1: 무제한).

---

## 2. Projects (프로젝트)

### `POST /api/projects`
Manifest YAML 업로드 → 프로젝트 생성.

**요청 (multipart/form-data 또는 application/x-yaml)**:
```yaml
# project.boq.yaml 파일 본문
$schema: "..."
version: "1.0"
project: { ... }
...
```

**응답 201**:
```json
{
  "project_id": "PROJ-2026-001",
  "name": "5층 사무동",
  "manifest_hash": "sha256:abc...",
  "stats": {
    "floors": 1,
    "members": 8,
    "by_type": { "COLUMN": 4, "BEAM": 4 }
  },
  "warnings": []
}
```

**응답 400**: 검증 실패. `errors[]`에 상세 사유.

### `GET /api/projects/{project_id}`
프로젝트 메타 + 통계.

### `GET /api/projects/{project_id}/manifest`
원본 YAML 다운로드. `Content-Type: application/x-yaml`.

### `PUT /api/projects/{project_id}/manifest`
Manifest 갱신 (전체 교체). 기존 `member_instances` 재생성.

---

## 3. BOQ Calculation (기존 + 신규)

### `POST /api/projects/{project_id}/calculate` (신규)
Manifest 기반 계산. 내부적으로:
1. `member_instances` 조회
2. 그리드 좌표 → 절대 좌표 변환
3. `MemberInput[]` 생성
4. 기존 `run_boq_pipeline()` 호출
5. 결과 `boq_jobs`에 저장

**응답**: 기존 `BOQCalculateResponse`와 동일 형식.

### `POST /api/boq/calculate` (기존, 유지)
직접 `MemberInput[]` 입력. 변경 없음.

---

## 4. 에러 응답 표준

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "spec 'XYZ' not found in catalog",
    "details": [
      { "field": "members[3].spec", "issue": "unknown_symbol" }
    ]
  }
}
```

| 코드 | HTTP | 의미 |
|------|------|------|
| `VALIDATION_ERROR` | 400 | 입력 스키마 위반 |
| `NOT_FOUND` | 404 | 리소스 없음 |
| `CONFLICT` | 409 | 중복/충돌 |
| `MANIFEST_ERROR` | 422 | Manifest 의미적 오류 (참조 무효 등) |
| `INTERNAL_ERROR` | 500 | 서버 오류 |

---

## 5. Phase 1 구현 우선순위

| 엔드포인트 | 우선순위 | 트랙 |
|-----------|---------|------|
| `GET /api/specs` | P0 | Track D |
| `GET /api/specs/{symbol}` | P0 | Track D |
| `POST /api/projects` | P0 | Track D |
| `POST /api/projects/{id}/calculate` | P0 | Track D + 통합 |
| `POST/PUT/DELETE /api/specs` | P1 | Track D |
| `GET /api/projects/{id}` | P1 | Track D |
| `PUT /api/projects/{id}/manifest` | P2 | 후순위 |
