# 🧠 개팀장 브레인 (Brain.md)

> **프로젝트**: FreeCAD BOQ 자동화 시스템  
> **총괄**: 개팀장 (20년차 베테랑)  
> **상태**: 저장소 클론 완료 및 환경 분석 중  

---

## 📌 1. 현재 상황 요약 (Executive Summary)
- **리포지토리 클론 완료**: `https://github.com/iss0wind-art/FreeCAD_4TH` -> `e:\Git\FREECAD_BOQ`
- **[Track 1] 완료**: `members_accumulated.json` (25,219건) 기반 솔리드화 성공.
  - 산출물: `final_track1.step` (194MB), BOQ(JSON/CSV).
  - 성공률: 99.9% (25,215/25,219 - 기초 제외 전수 성공).

## 2. 프로젝트 상태 및 핵심 의사결정 (2026-05-07)
*   **긴급 피벗(Pivot)**: 기존 파싱 데이터(`members_accumulated.json` 등) 전면 폐기. "가공된 데이터는 틀렸다"는 방부장님의 판단 하에 **제로 베이스(Zero-Base) 원본 DXF 직접 파싱**으로 노선 변경.
*   **핵심 기술: Top-Down(역산) 컷팅**: 
    *   기존: 1층 기둥 → 보 → 슬라브 순서로 그리며 겹치는 부분을 수학적으로 공제 (오류 확률 높음).
    *   **신규(특허급 로직)**: 슬라브와 보를 상부에 먼저 그리고, 아래에서 기둥/벽체를 쏘아 올려 수평부재에 닿으면 멈추는(Boolean Cut) 방식.
    *   이 방식을 통해 FreeCAD C++ 기하학 엔진이 교차부를 자동 공제하며, **정확한 거푸집(Formwork) 측면 면적 산출**이 가능해짐을 파일럿 테스트로 완벽 검증 완료.
*   **멀티 에이전트 체제 (11 Agents)**: 
    *   Agent 1: 개팀장 (지휘 및 최종 Boolean 로직)
    *   Agent 2: 수직부재 봇 (S-COL, S-WAL 원시 폴리곤 채굴)
    *   Agent 3: 수평부재 봇 (S-BEM, S-SLB 위상 스캔 및 생성)
    *   Agent 4: 좌표 정렬 봇 (E/V, Grid 기반 도면 통일)
    *   Agent 5: 레벨/층고 봇 (SL 텍스트 파싱)
*   **현재 진행**: Agent 3을 통한 수평부재(보 5,200개, 슬라브 142개) 위상 추출 완료. 이를 수직부재와 결합하는 Top-Down 2차 테스트 준비 중.

---

## 🏗️ 2. 시스템 아키텍처 및 주요 모듈 (Current State)
- **Core**: `core/pipeline/member_data.py` (통합 데이터 모델), `core/pipeline/boq_solid_builder.py` (통합 빌더)
- **Infrastructure**: FreeCAD 1.1 Python 기반 3D 엔진 연동 완료.

---

## 🎯 3. 핵심 작업 트랙 (Active Tracks)
1. **[Track 1] 환경 설정 및 의존성 검토**: Python `requirements.txt` 및 Node.js 패키지 정합성 확인.
2. **[Track 2] 기존 '신고조선' 유산 통합**: `.brain/` 하위의 해마, 소뇌 등 기존 지식을 '개팀장' 스타일로 재구성.
3. **[Track 3] DXF 정밀 정합 (E/V 코어)**: 현재 70% 수준인 좌표 정합도를 100%로 끌어올리는 로직 최적화.

---

## 🧠 4. 세부 지식 보관소 (Sub-Brains)
- [기억해] [history_context.md](.brain/history_context.md) — 기존 신고조선(이천) 맥락 보존
- [기억해] [tech_stack.md](.brain/tech_stack.md) — 핵심 기술 스택 및 라이브러리 규격
- [기억해] [flow_log.md](.brain/flow_log.md) — 작업 진행 상세 로그

---

## 👔 개팀장 지시사항
- **결재 필수**: 모든 주요 로직 수정 및 라이브러리 추가는 방부장(USER)의 승인 후 실행.
- **실무 중심**: 이론적인 접근보다 현장에서 즉시 사용 가능한 물량 산출(BOQ) 무결성 확보에 집중.

---
*2026-05-07 - 개팀장 부임 및 클론 보고 완료.*
