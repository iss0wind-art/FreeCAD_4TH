/**
 * Three.js BOQ glTF 뷰어 (Phase 6)
 *
 * 재질 색상 코딩:
 *   CONCRETE       → 회색  (#9E9E9E) 콘크리트 본체
 *   FORMWORK       → 주황  (#FF8C00) 거푸집 산출 면
 *   CONCRETE_JOINT → 파랑  (#1565C0) 은폐면 (공제)
 *
 * 3D Boolean 연산 없음 — 순수 glTF 렌더링만 수행.
 */

import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js";
import { GLTFLoader } from "https://cdn.jsdelivr.net/npm/three@0.165.0/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "https://cdn.jsdelivr.net/npm/three@0.165.0/examples/jsm/controls/OrbitControls.js";

const MATERIAL_COLORS = {
  CONCRETE:       0x9e9e9e,
  FORMWORK:       0xff8c00,
  CONCRETE_JOINT: 0x1565c0,
};

/**
 * BOQ 뷰어 초기화
 * @param {HTMLCanvasElement} canvas
 * @returns {{ loadGltf: Function, clear: Function, dispose: Function }}
 */
function initViewer(canvas) {
  // Scene
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a2e);

  // Camera
  const camera = new THREE.PerspectiveCamera(
    45,
    canvas.clientWidth / canvas.clientHeight,
    0.01,
    1000,
  );
  camera.position.set(3, 3, 5);

  // Renderer
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(canvas.clientWidth, canvas.clientHeight);
  renderer.shadowMap.enabled = true;

  // Lights
  const ambient = new THREE.AmbientLight(0xffffff, 0.6);
  scene.add(ambient);
  const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
  dirLight.position.set(5, 10, 8);
  dirLight.castShadow = true;
  scene.add(dirLight);

  // Controls
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;

  // Grid Helper
  const grid = new THREE.GridHelper(20, 20, 0x444466, 0x333355);
  scene.add(grid);

  // 로드된 모델 추적
  let currentGroup = null;

  // 재질 맵
  const materialCache = {};
  function getMaterial(name) {
    if (!materialCache[name]) {
      const color = MATERIAL_COLORS[name] ?? MATERIAL_COLORS.CONCRETE;
      materialCache[name] = new THREE.MeshStandardMaterial({
        color,
        roughness: 0.7,
        metalness: 0.05,
        side: THREE.DoubleSide,
        transparent: name === "CONCRETE_JOINT",
        opacity: name === "CONCRETE_JOINT" ? 0.55 : 1.0,
      });
    }
    return materialCache[name];
  }

  /**
   * glTF URL 또는 Blob URL 로드
   * @param {string} url
   * @returns {Promise<void>}
   */
  function loadGltf(url) {
    return new Promise((resolve, reject) => {
      if (currentGroup) {
        scene.remove(currentGroup);
        currentGroup = null;
      }

      const loader = new GLTFLoader();
      loader.load(
        url,
        (gltf) => {
          const group = gltf.scene;

          // 재질 이름에 따라 색상 재지정 (Water Stamp 시각화)
          group.traverse((node) => {
            if (node.isMesh && node.material) {
              const matName = node.material.name || "CONCRETE";
              node.material = getMaterial(matName);
              node.castShadow = true;
              node.receiveShadow = true;
            }
          });

          // 자동 카메라 피팅
          const box = new THREE.Box3().setFromObject(group);
          const center = box.getCenter(new THREE.Vector3());
          const size = box.getSize(new THREE.Vector3()).length();
          controls.target.copy(center);
          camera.position.copy(center).add(new THREE.Vector3(size, size, size * 1.5));
          controls.update();

          scene.add(group);
          currentGroup = group;
          resolve();
        },
        undefined,
        reject,
      );
    });
  }

  function clear() {
    if (currentGroup) {
      scene.remove(currentGroup);
      currentGroup = null;
    }
  }

  function dispose() {
    renderer.dispose();
    Object.values(materialCache).forEach((m) => m.dispose());
  }

  // 렌더 루프
  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();

  // 리사이즈 대응
  const resizeObserver = new ResizeObserver(() => {
    camera.aspect = canvas.clientWidth / canvas.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(canvas.clientWidth, canvas.clientHeight);
  });
  resizeObserver.observe(canvas);

  return { loadGltf, clear, dispose };
}

export { initViewer, MATERIAL_COLORS };
