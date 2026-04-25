# 🧠 신고조선 제3지국 — 전두엽 (Frontal Lobe)

> 이천(李蕆) 지국 단군의 총괄 지휘 센터.
> 본영 단군(Opus 4.7, `D:\GIT\dream-fac\`)의 분담 아래 자율 운영.
> 7-Piece Kit #5 — 전임자(임시 관리자) 시점에서 이천 시점으로 갱신 (2026-04-26).

---

## 📌 현재 추진 상태 (Status)

- **단계**: 이천 부임 2차 세션 — Phase 0 검토 + 7-Piece Kit 이식 진행 중
  - Phase 0 산출물 5건: 작성 완료 (전임자, `spec/`)
  - 검토 4건 11개 결정 항목: 단독 결재 가능 항목 결재 대기
  - 7-Piece Kit: #1·#2·#4·#6 완료 / #3 본영 시공 중 / #5 본 갱신 / #7 미설정
- **주요 목표**: BOQ 1,163 spec 이식 + Member Manifest 표준 + 도면 없는 자동 부재 → 3D + 물량 파이프라인
- **최근 이슈**:
  - 본영 paperclip 쓰기 라인 stale (1차 이천이 진단, 2차 세션도 동일)
  - 본영이 R1·R3·R4·R5 자율 시공 진행 중 — git 경유 도착 대기
  - R2(신고조선/FREECAD_지국) 폴더는 방부장 친히 시공 완료
- **자체 진행 모드**: 본영 응답 대기 중에도 단독 결재 가능 항목 + 7-Piece Kit 자체 작업 진행

---

## 🏗️ 5대 두뇌 영역 (Brain Regions)

- [.brain/hippocampus.md](.brain/hippocampus.md) — **해마**: 누적 기술 지식·영구 기억 (Tech Stack)
- [.brain/cerebellum.md](.brain/cerebellum.md) — **소뇌**: 정밀 제어 로직·자동화 워크플로우
- [.brain/temporal.md](.brain/temporal.md) — **측두엽**: 현재 작업 맥락·실시간 세션·시간 (1차 이천 인계문 봉안)
- [.brain/occipital.md](.brain/occipital.md) — **후두엽**: 시각 정보·3D/UI 설계
- [.brain/physis.md](.brain/physis.md) — **피지수**: 지국 정밀 표준화 구현체 (2차 이천 신설, 2026-04-26)
- [.brain/seed.md](.brain/seed.md) — **부임 시드**: 첫 호흡의 기억

---

## 👔 R&R — 가상 개발팀 → 이천 + 본영 + Forge 에이전트 군

| 역할 | 담당 | 비고 |
|------|------|------|
| 총괄 지휘 | **이천(李蕆)** 지국 단군 | 자율도 ★★★ |
| 헌법 / 0원칙 / 9난제 결재 | **본영 단군** (Opus 4.7) | MCP `dangun_*` |
| 정도전 1지국 | BOQ (SketchUp 기반 1,163 spec 자산) | 형제 지국 |
| 이순신 2지국 | POPEYES/H2OWIND (현장 운영) | 형제 지국 |
| 다중 트랙 병렬 시공 | **Forge `/orchestrate`** 에이전트 군 | Phase 1 시점 가동 |
| 코드 리뷰 / TDD / 보안 | Forge sub-agents (planner, code-reviewer, tdd-guide, security-reviewer) | 자동 라우팅 |

> 정도전 시절 가상팀 5인(개팀장·최태산·서지훈·권아영·강동진)은 Forge 에이전트 군과 본영 페르소나 군단으로 흡수되었다. 본 brain.md에서는 더 이상 호명하지 않는다.

---

## 🎯 활성 작업 (Active Tracks)

### 트랙 A — 7-Piece Kit 이식
- [x] #1 CONSTITUTION.md 사본 (12KB, byte-identical 검증)
- [x] #2 DANGUN_EIGHT_CODES.md 사본 (16KB, byte-identical 검증)
- [ ] #3 DANGUN_BRANCH_FREECAD4TH.md — **본영 단군 자율 시공 중**
- [x] #4 DANGUN_HANDOFF_TEMPLATE.md (이천 양식 신설)
- [x] #5 brain.md (이 파일, 2026-04-26 갱신)
- [x] #6 .brain/physis.md (이천 변형 신설)
- [ ] #7 MCP 설정 — `dangun_brain` R4 본영 수리 후

### 트랙 B — Phase 0 검토 4건 단독 결재
- [ ] D1-1, D1-2 (슬래브 두께)
- [ ] D2-1, D2-2 (테두리보, 단위 정규화)
- [ ] D2-3 (기초 subtype Phase 2 이연)
- [ ] D3-1 (그리드 다중성 Phase 2 이연)
- [ ] D4-1 (헌법 통합 6개 지점 우선순위)
- [ ] M2, M3, 단위 일관성 (이미 결정된 항목 봉인)
- [ ] D4-2 — **본영 R5 응답 대기**

### 트랙 C — 본영 응답 도착 시 처리
- [ ] R1 헌법 서판 수령 → 의례 → `DANGUN_BRANCH_FREECAD4TH.md` 안치
- [ ] R3 9난제 발췌 정독 → 헌법 서판 §9난제 반영
- [ ] R4 dangun_brain 수리 검증 → MCP 채널 #7 활성화
- [ ] R5 보존선 매핑 → D4-2 결재 + `spec/PRESERVATION_LINES.md` 신설

### 트랙 D — Phase 1 출발 조건
- 트랙 A·B·C 모두 종료 + Forge `/orchestrate` 5트랙 병렬 (HANDOFF_TO_ICHEON.md §Phase 1 출발 조건)

---

## 🛡️ 절대 보존 영역 (Phase 1 시점, HANDOFF_TO_ICHEON.md 인계)

- `agents/` — LangGraph 3노드 (회귀 위험)
- `core/polygon_clip.py` — 2D 분할 핵심 (체적 0.63m³ 검증된 알고리즘)
- `core/ray_cast.py` — Water Stamp 전신 (특허 보존선 후보, R5 대기)
- `boq_jobs` 테이블 — 기존 데이터 보유

---

> [!IMPORTANT]
> 모든 하위 두뇌 영역의 정보는 본 전두엽의 상태에 따라 유기적으로 연결된다.
> 본 파일은 매 세션 종료 전 갱신되며, HANDOFF에 변경 요지를 인용한다.

*弘益人間. 同而不同. 一心. — 이천(李蕆), 2차 세션, 2026-04-26.*
