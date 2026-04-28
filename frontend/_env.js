/**
 * 환경별 API URL 설정
 * - 로컬 개발: 빈 문자열 (FastAPI 백엔드가 같은 서버에서 /static 으로 서빙)
 * - Cloudflare Pages: N100 홈서버 URL
 *
 * 배포 시 이 값을 수정하거나 Cloudflare Pages 환경변수로 주입한다.
 * 기본값은 N100 DuckDNS 주소.
 */
window.BOQ_API_BASE = "https://freecad4th.duckdns.org";
