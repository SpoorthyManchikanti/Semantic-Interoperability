const API = "http://127.0.0.1:8000";

export async function getPatient(patientId) {
    const response = await fetch(`${API}/patient/${patientId}`);
    return response.json();
}