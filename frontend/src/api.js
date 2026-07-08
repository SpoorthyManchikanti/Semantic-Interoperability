const API = "http://127.0.0.1:8000";

export async function getPatient(patientId) {
  const response = await fetch(`${API}/patient/${patientId}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Patient not found (${response.status})`);
  }
  return response.json();
}

export async function listPatients(limit = 10, offset = 0) {
  const response = await fetch(`${API}/patients/?limit=${limit}&offset=${offset}`);
  if (!response.ok) throw new Error("Failed to fetch patient list");
  return response.json();
}

export async function searchPatients(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const response = await fetch(`${API}/patients/search?${qs}`);
  if (!response.ok) throw new Error("Search failed");
  return response.json();
}
