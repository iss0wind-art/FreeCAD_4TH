/**
 * 환경별 API URL 설정
 * - 로컬 개발: 빈 문자열 (FastAPI 백엔드가 같은 서버에서 /static 으로 서빙)
 * - Cloudflare Pages: N100 홈서버 URL
 *
 * 배포 시 이 값을 수정하거나 Cloudflare Pages 환경변수로 주입한다.
 * 기본값은 N100 DuckDNS 주소.
 */
// 나스 상주 서버(:3103, freecad.iss0wind.kr)가 프론트·API를 한 오리진에서 서빙 → 빈 문자열
window.BOQ_API_BASE = "";
