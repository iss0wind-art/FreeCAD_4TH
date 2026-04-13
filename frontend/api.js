/**
 * BOQ API 클라이언트
 * FastAPI 백엔드와 통신 (POST /api/boq/calculate, GET /api/boq/{id})
 */

const BOQ_API_BASE = window.BOQ_API_BASE || "";

/**
 * BOQ 물량 산출 요청
 * @param {string} projectId
 * @param {Array} members - MemberInputDTO 배열
 * @returns {Promise<Object>} BOQCalculateResponse
 */
async function calculateBOQ(projectId, members) {
  const resp = await fetch(`${BOQ_API_BASE}/api/boq/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId, members }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(`BOQ 산출 실패: ${JSON.stringify(err.detail)}`);
  }
  return resp.json();
}

/**
 * 저장된 BOQ 작업 조회
 * @param {string} jobId
 * @returns {Promise<Object>} BOQJobResponse
 */
async function getBOQJob(jobId) {
  const resp = await fetch(`${BOQ_API_BASE}/api/boq/${jobId}`);
  if (resp.status === 404) throw new Error(`작업 없음: ${jobId}`);
  if (!resp.ok) throw new Error(`조회 실패: ${resp.statusText}`);
  return resp.json();
}

export { calculateBOQ, getBOQJob };
