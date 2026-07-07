import { useState } from "react";
import { getPatient } from "./api";

function App() {

  const [patientId, setPatientId] = useState("");

  const [patient, setPatient] = useState(null);

  async function lookupPatient() {

    const data = await getPatient(patientId);

    setPatient(data);

  }

  return (

    <div style={{ padding: 40 }}>

      <h1>Semantic Interoperability MVP</h1>

      <h2>Patient Lookup</h2>

      <input
        placeholder="Patient ID"
        value={patientId}
        onChange={(e) => setPatientId(e.target.value)}
      />

      <button onClick={lookupPatient}>
        Lookup
      </button>

      {patient && (

        <div>

          <hr />

          <h2>Patient Dashboard</h2>

          <p><b>Name:</b> {patient.name}</p>

          <p><b>Age:</b> {patient.age}</p>

          <h3>Conditions</h3>

          <ul>
            {patient.conditions.map(c => (
              <li key={c}>{c}</li>
            ))}
          </ul>

          <h3>Medications</h3>

          <ul>
            {patient.medications.map(m => (
              <li key={m}>{m}</li>
            ))}
          </ul>

          <h2>Relationship Graph Preview</h2>

          <ul>
            {patient.relationships.map((r, i) => (

              <li key={i}>
                {r.source} → {r.relationship} → {r.target}
              </li>

            ))}
          </ul>

        </div>

      )}

    </div>

  );

}

export default App;