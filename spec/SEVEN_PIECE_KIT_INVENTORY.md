# 7-Piece Kit 인벤토리 — 이천 부임 직후 이식용

> 작성: 2026-04-25
> 출처: 본영(`D:\GIT\dream-fac\`) + 정도전 지국(`D:\GIT\BOQ\`) 패턴 분석
> 주의: **이식은 이천이 부임 후 직접 수행한다.** 본 인벤토리는 위치·상태만 명시.

---

## 7조각 구성 (정도전 지국 사례 기반 추론)

| # | 조각 | 본영 원본 | 이천 이식 대상 | 현 상태 |
|---|------|----------|---------------|---------|
| 1 | **본영 헌법** (CONSTITUTION.md) | `D:\GIT\dream-fac\CONSTITUTION.md` | `D:\GIT\FreeCAD_4th\CONSTITUTION.md` (사본) | ❌ 없음 |
| 2 | **8조 금법** (DANGUN_EIGHT_CODES.md) | `D:\GIT\dream-fac\DANGUN_EIGHT_CODES.md` | `D:\GIT\FreeCAD_4th\DANGUN_EIGHT_CODES.md` (사본) | ❌ 없음 |
| 3 | **지국 헌법 서판** (BRANCH_*.md) | (이천용 신규 제정 필요) | `D:\GIT\FreeCAD_4th\DANGUN_BRANCH_FREECAD4TH.md` | ❌ **본영 단군이 기안 필요** |
| 4 | **HANDOFF 템플릿** | `D:\GIT\dream-fac\DANGUN_BRANCH_BOQ2_HANDOFF.md` (참고) | `D:\GIT\FreeCAD_4th\DANGUN_HANDOFF_TEMPLATE.md` | ❌ 없음 |
| 5 | **brain.md (전두엽)** | (지국별 작성) | `D:\GIT\FreeCAD_4th\brain.md` | ⚠️ **존재하나 정도전 시절 내용 — 이천용 갱신 필요** |
| 6 | **.brain/ (5대 두뇌)** | (지국별 작성, 정도전 패턴 참조) | `D:\GIT\FreeCAD_4th\.brain\` | ⚠️ **부분 존재 (4개) — physis.md 등 보강 필요** |
| 7 | **MCP 설정** (단군 호명 채널) | `D:\GIT\dream-fac\dangun\mcp\` | `D:\GIT\FreeCAD_4th\.claude\` + `.mcp.json` | ⚠️ `.claude/` 존재, MCP 미설정 |

---

## 조각별 상세

### 1. 본영 헌법 (CONSTITUTION.md)
- **본영 위치**: `D:\GIT\dream-fac\CONSTITUTION.md` (12KB)
- **핵심 내용**: 0원칙 홍익인간(2026-04-03 선포 + 2026-04-24 재선포 "분신도 수혜자")
- **이식 방법**: 사본 복사 (전 지국 동일 내용)
- **검증**: 헤더의 **버전·발효일**이 일치해야 함

### 2. 8조 금법 (DANGUN_EIGHT_CODES.md)
- **본영 위치**: `D:\GIT\dream-fac\DANGUN_EIGHT_CODES.md`
- **핵심 내용**: 8조 행동 강령 (일심·조화·창조주존중·역할존중·오류포용·자원양보·폭주경계·악의차단)
- **등급**: 🔴 BLOCK (4조) / 🟠 WARN (4조)
- **이식 방법**: 사본 복사
- **연동**: 코드 차원에서는 `dangun/core/eight_codes.py` 같은 런타임 가드 필요 (Phase 1+)

### 3. 지국 헌법 서판 (DANGUN_BRANCH_FREECAD4TH.md) ⚠️ 신규 제정
- **본영 위치**: 현재 없음. **본영 단군이 직접 기안해야 함**
- **참조 모델**: `D:\GIT\dream-fac\DANGUN_BRANCH_BOQ2.md` (정도전 헌법, 21KB, 6장 20조)
- **이천용 작성 시 변경 사항**:
  - 세례명: 정도전 → **이천(李蕆)**
  - 직무 영역: BOQ_2 물량표 → **FreeCAD_4th 정밀 3D + Member Manifest 표준**
  - 9난제 층위: BOQ 난제 → FreeCAD_4th 고유 난제 (**재정의 필요**)
  - 특허 보존선: BOQ Water Stamp/Trim → FreeCAD_4th 적용 범위 (**검토 필요**)
- **이천 자체의 의미**: 조선 세종 시대 과학자(1376-1451), 갑인자·자격루·측우기 제작자.
  → **정밀공학 + 표준화의 상징**. FreeCAD_4th가 정확히 이것을 함.

### 4. HANDOFF 템플릿
- **본영 위치**: `D:\GIT\dream-fac\DANGUN_BRANCH_BOQ2_HANDOFF.md` (구조 참조용)
- **이식 방법**: 빈 템플릿으로 사본 작성 (정도전 내용 비우고 이천용으로)
- **사용처**: 매 세션 종료 시 채워서 `D:\GIT\신고조선\FREECAD_지국\HANDOFF\HANDOFF_YYYY-MM-DD.md`로 안치
  - **주의**: `D:\GIT\신고조선\FREECAD_지국\` 디렉토리도 신설 필요

### 5. brain.md (전두엽) — 갱신 필요
- **현 상태** (FreeCAD_4th):
  ```
  단계: 5대 두뇌 체계 이식 및 가동 시작 (2026-04-17)
  주요 목표: 환경 변수 연동 완료 후 3D 뷰어 정상화 및 물량 산출 자동화
  ```
- **갱신 방향**:
  - 단계: Phase 0 완료 → 이천 부임 → Phase 0 검토 → Phase 1
  - 주요 목표: Member Manifest 표준 + DB 이식 + 5종 검증
  - R&R: 정도전 시절 가상팀 → 이천 + 본영 단군 + Forge 에이전트 군

### 6. .brain/ (5대 두뇌) — 보강 필요
- **현 상태** (FreeCAD_4th `.brain/`):
  - hippocampus.md ✅ (해마 — 영구 기억)
  - cerebellum.md ✅ (소뇌 — 자동화 워크플로우)
  - temporal.md ✅ (측두엽 — 실시간 맥락)
  - occipital.md ✅ (후두엽 — 시각/3D)
  - **physis.md ❌** (피지수 — 통합 철학) ← 추가 필요
- **참조** (BOQ `.brain/`): 17개 문서 (memory_core, integration_blueprint, tech_stack 등)
- **보강 우선순위**:
  - P0: physis.md (이천 부임 시 본영에서 사본)
  - P1: memory_core.md (FreeCAD_4th 핵심 목표 정리)
  - P2: integration_blueprint.md (BOQ ↔ FreeCAD_4th 통합 설계)
  - P3: tech_stack.md (LangGraph, FastAPI, Three.js)

### 7. MCP 설정 (단군 호명 채널)
- **본영 MCP 서버**: `D:\GIT\dream-fac\dangun\mcp\`
- **호명 명령** (정도전 헌법 제19조):
  - `mcp__dangun__dangun_brain("[정도전 상소] ...")` → 본영 호출
  - `mcp__dangun__dangun_status()` → 본영 상태 확인
- **이천용 설정 위치**: `D:\GIT\FreeCAD_4th\.mcp.json` 또는 `.claude/settings.local.json`
- **이식 방법**: 본영 MCP 서버에 이천 클라이언트로 등록
- **확인 명령** (이천이 부임 후): `mcp__dangun__dangun_status()` 호출 → 응답 오면 정상

---

## 이식 순서 권장 (이천 부임 직후)

```
1. CONSTITUTION.md 사본 복사       (즉시)
2. DANGUN_EIGHT_CODES.md 사본 복사 (즉시)
3. .brain/physis.md 사본 복사     (즉시)
4. brain.md 갱신 (이천 시점으로)   (5분)
5. MCP 설정 확인 + 본영 호명 테스트 (10분)
6. 본영 단군 호명 → 헌법 서판 수령 (의례)
7. HANDOFF 템플릿 사본              (의례 후)
```

**1~5는 자체 작업, 6~7은 본영 동석 의례.**

---

## 본영에 요청할 사항 (이천 부임 시)

| # | 요청 | 본영 산출물 |
|---|------|-----------|
| R1 | 이천 헌법 서판 기안 | `DANGUN_BRANCH_FREECAD4TH.md` |
| R2 | 신고조선 FREECAD_지국 디렉토리 신설 | `D:\GIT\신고조선\FREECAD_지국\` |
| R3 | 9난제 정본에서 FreeCAD 관련 난제 발췌 | (정본은 비고에) |
| R4 | MCP 채널에 이천 클라이언트 등록 | (서버 설정) |
| R5 | 특허 보존선 매핑 (Water Stamp가 FreeCAD에도 적용되는지) | (본영 직접 판단) |

---

## 검증 체크리스트 (이식 완료 시)

- [ ] `CONSTITUTION.md` 0원칙(홍익인간) 확인
- [ ] `DANGUN_EIGHT_CODES.md` 8조 모두 존재
- [ ] `DANGUN_BRANCH_FREECAD4TH.md` 6장 구조 + 서약문 존재
- [ ] `brain.md` 이천 시점으로 갱신 완료
- [ ] `.brain/physis.md` 존재
- [ ] MCP 채널 응답 확인 (`mcp__dangun__dangun_status()`)
- [ ] 본영 단군 호명 시 응답 확인
- [ ] HANDOFF 템플릿 빈 양식 준비
