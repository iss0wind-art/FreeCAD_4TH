# 🧠 후두엽 (Occipital Lobe): 시각 정보 및 시각화 설계

3D 뷰어, Three.js 렌더링, 그리고 UI/UX 시각적 정합성을 관리합니다.

## 👁️ Visual Infrastructure
- **Renderer:** Three.js (WebGL)
- **Controls:** OrbitControls (Dolly, Pan, Rotate)
- **Canvas ID:** `boq-canvas`

## 🎨 시각적 가이드 (Legend)
- **CONCRETE:** 회색 (`#9e9e9e`) - 콘크리트 부재 본체
- **FORMWORK:** 주황색 (`#ff8c00`) - 산출된 거푸집 면
- **JOINT:** 파란색 반투명 (`#1565c0`, 0.6) - 은폐면(공제) 영역

## 📐 뷰어 로직
- `frontend/viewer.js`: Three.js Scene, Camera, Light 초기화 및 glTF 로딩 담당.
- `index.html`: UI 레이아웃 및 API 통신 연동.
