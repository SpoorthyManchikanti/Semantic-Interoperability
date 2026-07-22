const API = "http://127.0.0.1:8000";

async function getJson(path) {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

async function patchJson(path, body) {
  const response = await fetch(`${API}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

export async function getPatient(patientId) {
  return getJson(`/patients/${patientId}`);
}

export async function getPatientConcepts(patientId) {
  return getJson(`/patients/${patientId}/concepts`);
}

export async function listPatients(limit = 10, offset = 0) {
  return getJson(`/patients/?limit=${limit}&offset=${offset}`);
}

export async function searchPatients(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return getJson(`/patients/search?${qs}`);
}

export async function getDataSourceSummary() {
  return getJson(`/patients/data-source-summary`);
}

export async function getDashboardSummary() {
  return getJson(`/dashboard/summary`);
}

export async function getDashboardPipeline() {
  return getJson(`/dashboard/pipeline`);
}

export async function getActivity(limit = 20) {
  return getJson(`/dashboard/activity?limit=${limit}`);
}

export async function getGraphPreview(limit = 40) {
  return getJson(`/graph/preview?limit=${limit}`);
}

export async function getPatientRelationships(patientId) {
  return getJson(`/patients/${patientId}/relationships`);
}

export async function getPatientGraph(patientId) {
  return getJson(`/patients/${patientId}/graph`);
}

export async function getAiSummary(patientId) {
  return getJson(`/patients/${patientId}/ai-summary`);
}

export async function getConcepts() {
  return getJson(`/concepts/`);
}

export async function getNeedsReviewConcepts() {
  return getJson(`/concepts/needs-review`);
}

export async function getOmopResolution() {
  return getJson(`/concepts/omop-resolution`);
}

export async function searchConcepts(q) {
  return getJson(`/concepts/search?q=${encodeURIComponent(q)}`);
}

export async function getConceptGraph(conceptId) {
  return getJson(`/concepts/${conceptId}/graph`);
}

export async function reviewConcept(conceptId, body) {
  return patchJson(`/concepts/${conceptId}/review`, body);
}

export async function getPatientMatches() {
  return getJson(`/patients/matches`);
}

export async function reviewPatientMatch(matchId, body) {
  return patchJson(`/patients/matches/${matchId}/review`, body);
}

export async function flagPatientConceptException(patientConceptId, body) {
  return patchJson(`/patient-concepts/${patientConceptId}/exception`, body);
}
