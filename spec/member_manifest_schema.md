# Member Manifest Schema v1.0

> Phase 0 산출물 — Phase 1 모든 트랙의 입력 계약(contract)

## 철학

**데이터가 진실의 원천(SoT). 도면은 데이터에서 파생되는 뷰일 뿐.**

- DXF/SVG에 데이터 박아넣기 ❌ (DXF의 실수 반복)
- 정형 데이터 + 다중 뷰 ✅ (Figma/Notion 패턴)

## 파일 형식

- 확장자: `.boq.yaml` (YAML 1.2, UTF-8)
- 단일 파일 = 단일 프로젝트
- Git 친화적 (텍스트, diff 가능)

## Top-level 구조

```yaml
$schema: "https://boq.local/schemas/manifest/v1"
version: "1.0"

project:    { ... }   # 프로젝트 메타
grid:       { ... }   # 그리드 시스템 (선택)
floors:     [ ... ]   # 층 정의
members:    [ ... ]   # 부재 배치 인스턴스
```

---

## 1. `project` (필수)

```yaml
project:
  id: "PROJ-2026-001"           # 영문/숫자/하이픈, 1-64자, PK
  name: "5층 사무동"             # 표시명, 1-200자
  units: mm                     # mm | m, 기본 mm
  default_concrete_grade: "C24" # 선택, 기본값 콘크리트 강도
```

### 검증 규칙
- `id`: `^[A-Za-z0-9-_]{1,64}$`
- `units`: enum, 내부 처리는 항상 mm로 정규화

---

## 2. `grid` (선택, 권장)

그리드가 있으면 멤버 배치를 `grid: ["A", "1"]` 형식으로 가능.

```yaml
grid:
  origin: [0, 0]              # A1의 절대 좌표 [x, y] (mm)
  rotation: 0                 # 그리드 회전각 (도, 기본 0)
  x_lines:                    # X축 라인 (예: A, B, C, ...)
    A: 0
    B: 6000
    C: 12000
    D: 18000
  y_lines:                    # Y축 라인 (예: 1, 2, 3, ...)
    "1": 0
    "2": 8000
    "3": 16000
```

### 검증 규칙
- `x_lines` / `y_lines` 키는 알파벳/숫자, 값은 mm 단위 절대 위치
- 그리드가 없으면 모든 멤버는 `xy:` 절대 좌표 사용 필수

---

## 3. `floors` (필수, 1개 이상)

```yaml
floors:
  - id: "1F"
    z_base: 0          # mm, 슬래브 윗면 기준
    height: 4500       # mm, 다음 층 슬래브 윗면까지

  - id: "2F"
    z_base: 4500
    height: 3500
```

### 검증 규칙
- `id`: 1-32자, 프로젝트 내 유니크
- `z_base`, `height`: `>= 0` (mm)
- 층은 `z_base` 오름차순 권장 (강제 아님)

---

## 4. `members` (필수, 1개 이상)

부재 종류별 4가지 배치 패턴:

### 4.1 Point 배치 (기둥)

```yaml
- id: "C-A1-1F"            # 인스턴스 ID, 프로젝트 내 유니크
  spec: "TC1"              # member_specs DB의 symbol 참조
  type: column             # column | beam | slab | wall | foundation
  floor: "1F"              # floors[].id 참조
  at:
    grid: ["A", "1"]       # 또는 xy: [0, 0]
  rotation: 0              # 도, 기본 0 (단면 회전)
  z_offset: 0              # mm, floor.z_base에 더할 오프셋
```

### 4.2 Line 배치 (보)

```yaml
- id: "B-A1-A2-1F"
  spec: "RG1"
  type: beam
  floor: "1F"
  from:
    grid: ["A", "1"]       # 또는 xy: [0, 0]
  to:
    grid: ["A", "2"]
  z_offset: -100           # 슬래브 아래로 100mm
  # 보의 폭/춤은 spec(RG1)에서 자동 조회
```

### 4.3 Polygon 배치 (슬래브, 벽 — Phase 2+)

```yaml
- id: "S-1F-Bay1"
  spec: "SL1"
  type: slab
  floor: "1F"
  polygon:
    - grid: ["A", "1"]
    - grid: ["B", "1"]
    - grid: ["B", "2"]
    - grid: ["A", "2"]
  z_offset: 0
  # 슬래브 두께는 spec에서 조회
```

### 4.4 Free 배치 (자유 다각형)

```yaml
- id: "C-FREE-1"
  spec: "TC2"
  type: column
  floor: "1F"
  vertices_2d:               # 직접 다각형 정의 (그리드/spec 무시)
    - [3500, 4200]
    - [4100, 4200]
    - [4100, 4800]
    - [3500, 4800]
```

### 검증 규칙

| 필드 | 제약 |
|------|------|
| `id` | `^[A-Za-z0-9-_]{1,64}$`, 프로젝트 내 유니크 |
| `spec` | DB `member_specs.symbol`에 존재해야 함 |
| `type` | spec의 `member_type`과 일치해야 함 |
| `floor` | `floors[].id` 중 하나 |
| `at` / `from`+`to` / `polygon` / `vertices_2d` | 정확히 1개 사용 |
| `grid: [x, y]` | `grid.x_lines`와 `grid.y_lines`에 존재 |
| `z_offset` | -10000 ~ +10000 (mm) |

---

## 5. 좌표 해석 규칙

**그리드 좌표 → 절대 좌표 변환 (어댑터가 수행)**:

```
input: grid: ["B", "2"], grid.origin = [0, 0]
       grid.x_lines.B = 6000
       grid.y_lines."2" = 8000

result: xy = [6000, 8000]   (origin 가산, rotation 적용 후)
```

**Z 좌표**:
```
z = floor.z_base + member.z_offset
```

---

## 6. 알려진 한계 (Phase 1 시점)

| 기능 | 상태 | 비고 |
|------|------|------|
| Beam, Column 배치 | ✅ Phase 1 | 기존 파이프라인 호환 |
| Slab 배치 | ⚠️ 스키마 정의됨, 구현 Phase 2 | polygon 입력 |
| Wall 배치 | ⚠️ 스키마 정의됨, 구현 Phase 2 | polygon + height |
| Foundation 배치 | ⚠️ 스키마 정의됨, 구현 Phase 3+ | 매트/줄/파일 분기 |
| 보-보 교차 | ❌ 미구현 | 현재 기둥-보 쌍만 |
| 다중 그리드 시스템 | ❌ Phase 4+ | 단일 그리드만 |
| 곡선 부재 | ❌ 미정 | 직선만 |

---

## 7. 변경 이력

| 버전 | 날짜 | 변경 |
|------|------|------|
| 1.0 | 2026-04-25 | 초안 (Phase 0) |
