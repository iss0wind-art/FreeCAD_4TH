# 🧠 해마 (Hippocampus): 영구 기억 및 기술 지식

프로젝트의 핵심 기술 스택, 버전 정보, 그리고 누적된 기술적 노하우를 저장합니다.

## 🛠️ Core Tech Stack (v1.0.0)
- **Frontend:** Next.js 16.1.6 / Three.js 기반 커스텀 뷰어
- **Backend:** Python (FastAPI, LangGraph)
- **Database:** Turso (LibSQL), SQLite (Fallback)
- **Library:** Shapely, NumPy, pygltflib

## 🏛️ 주요 기술적 결정
1.  **2D-3D 하이브리드:** 2D에서 정밀 불리언(Boolean) 연산을 수행한 후 3D로 돌출(Extrude)하여 속도와 정확도를 동시에 확보.
2.  **MAS (Multi-Agent System):** Planner, Executor, Reviewer를 통한 단계별 물량 산출.
3.  **Edge-First DB:** Turso를 사용하여 응답 속도 및 데이터 정합성 보장.

## 📌 환경 설정 (Environment)
- `.env` 파일을 통한 제미나이 API 키 및 DB 토큰 관리.
- `/static` 경로를 통한 정적 자원(viewer.js, api.js) 서빙.
- `cspell.json`: 프로젝트 특화 기술 용어(BOQ, Turso, FreeCAD 등) 맞춤법 검사 예외 처리 설정.
