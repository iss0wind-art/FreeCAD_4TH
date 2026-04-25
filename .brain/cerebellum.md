# 🧠 소뇌 (Cerebellum): 정밀 제어 및 워크플로우

시스템의 세밀한 작동 원리, 알고리즘, 그리고 정합성 검증 규칙을 관리합니다.

## ⚙️ Core Logic (정밀 연산)
- **Polygon Clipping:** `core/polygon_clip.py` - 기둥과 보의 중첩 영역을 2D상에서 정밀하게 분리.
- **Mesh Generation:** `core/freecad_mesh.py` - 분리된 폴리곤을 glTF 형식의 3D 메시로 변환.

## 🔄 워크플로우 (AG-FORGE MAS)
1.  **Planner:** 입력된 JSON 데이터를 분석하여 연산 쌍(Pair) 생성.
2.  **Executor:** FreeCAD 또는 수학적 모델을 이용해 실제 3D 형상 및 물량 적산.
3.  **Reviewer:** 산출된 값의 물리적 정합성을 최종 검토.

## 🔧 자동화 스크립트
- `check.py`: 데이터 무결성 체크
- `fix.py`: 도면 데이터 보정
- Gemini CLI: 터미널 기반 유틸리티 지원
