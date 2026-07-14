const API = "http://127.0.0.1:8000";

async function getJson(path) {
  const response = await fetch(`${API}${path}`);
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

export async function getAiSummary(patientId) {
  return getJson(`/patients/${patientId}/ai-summary`);
}

export async function getConcepts() {
  return getJson(`/concepts/`);
}
