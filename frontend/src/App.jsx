import { useState } from "react";
import { getPatient } from "./api";
import "./App.css";

function Avatar({ name }) {
  const parts = (name || "").split(" ").filter(Boolean);
  const initials = parts.length >= 2
    ? parts[0][0] + parts[parts.length - 1][0]
    : parts[0]?.[0] ?? "?";
  return <div className="avatar">{initials.toUpperCase()}</div>;
}

function ConditionCard({ condition }) {
  const name = typeof condition === "string" ? condition : condition.condition_name;
  const category = typeof condition === "object" ? condition.category : null;
  const subcategory = typeof condition === "object" ? condition.subcategory : null;
  const code = typeof condition === "object" ? condition.snomed_code : null;
  const confidence = typeof condition === "object" && condition.confidence != null
    ? Math.round(condition.confidence * 100)
    : null;
  return (
    <div className="item-card condition-card">
      <span className="item-name">{name}</span>
      <div className="item-badges">
        {category && <span className="badge cat-badge">{category}</span>}
        {subcategory && <span className="badge subcat-badge">{subcategory}</span>}
        {code && <span className="badge code-badge">SNOMED: {code}</span>}
        {confidence != null && <span className="badge conf-badge">{confidence}%</span>}
      </div>
    </div>
  );
}

function MedicationCard({ medication }) {
  const name = typeof medication === "string" ? medication : medication.medication_name;
  const category = typeof medication === "object" ? medication.category : null;
  const subcategory = typeof medication === "object" ? medication.subcategory : null;
  const code = typeof medication === "object" ? medication.rxnorm_code : null;
  const confidence = typeof medication === "object" && medication.confidence != null
    ? Math.round(medication.confidence * 100)
    : null;
  return (
    <div className="item-card medication-card">
      <span className="item-name">{name}</span>
      <div className="item-badges">
        {category && <span className="badge cat-badge">{category}</span>}
        {subcategory && <span className="badge subcat-badge">{subcategory}</span>}
        {code && <span className="badge code-badge">RxNorm: {code}</span>}
        {confidence != null && <span className="badge conf-badge">{confidence}%</span>}
      </div>
    </div>
  );
}

function ObservationCard({ obs }) {
  return (
    <div className="item-card observation-card">
      <span className="item-name">{obs.observation_name}</span>
      <div className="item-badges">
        {obs.observation_value && <span className="badge value-badge">{obs.observation_value}</span>}
        {obs.category && <span className="badge cat-badge">{obs.category}</span>}
        {obs.loinc_code && <span className="badge code-badge">LOINC: {obs.loinc_code}</span>}
        {obs.confidence != null && <span className="badge conf-badge">{Math.round(obs.confidence * 100)}%</span>}
      </div>
    </div>
  );
}

const REL_COLORS = ["blue", "green", "purple", "amber"];

function RelationshipRow({ rel, index }) {
  const color = REL_COLORS[index % REL_COLORS.length];
  return (
    <div className={`rel-row rel-${color}`}>
      <span className="rel-node rel-source">{rel.source}</span>
      <div className="rel-connector">
        <span className="rel-line" />
        <span className="rel-label">{rel.relationship.replace(/_/g, " ")}</span>
        <span className="rel-arrow">&#8594;</span>
      </div>
      <span className="rel-node rel-target">{rel.target}</span>
    </div>
  );
}

export default function App() {
  const [patientId, setPatientId] = useState("");
  const [patient, setPatient] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function lookupPatient() {
    const id = patientId.trim();
    if (!id) return;
    setLoading(true);
    setError(null);
    setPatient(null);
    try {
      const data = await getPatient(id);
      setPatient(data);
    } catch (err) {
      setError(err.message || "Failed to fetch patient.");
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter") lookupPatient();
  }

  function reset() {
    setPatient(null);
    setError(null);
    setPatientId("");
  }

  const displayName = patient
    ? (patient.name || `${patient.first_name ?? ""} ${patient.last_name ?? ""}`.trim() || "Unknown")
    : "";

  const conditions = patient?.conditions ?? [];
  const medications = patient?.medications ?? [];
  const observations = patient?.observations ?? [];
  const relationships = patient?.relationships ?? [];

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <div className="brand-icon">SI</div>
          <div className="brand-text">
            <span className="brand-title">Semantic Interoperability</span>
            <span className="brand-sub">Patient Intelligence Platform</span>
          </div>
        </div>
      </header>

      <main className="app-main">
        <section className="search-section">
          <div className="search-bar">
            <input
              className="search-input"
              placeholder="Enter Patient ID..."
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              onKeyDown={onKeyDown}
              disabled={loading}
              autoFocus
            />
            <button
              className="search-btn"
              onClick={lookupPatient}
              disabled={loading || !patientId.trim()}
            >
              {loading ? <span className="spinner" /> : "Lookup"}
            </button>
          </div>
          <p className="search-hint">
            Try patient ID: <code>12345</code> &mdash; press <kbd>Enter</kbd> to search
          </p>
        </section>

        {error && (
          <div className="error-box" role="alert">
            <span className="error-icon">&#9888;</span>
            <span className="error-msg">{error}</span>
            <button className="dismiss-btn" onClick={() => setError(null)} aria-label="Dismiss">&#10005;</button>
          </div>
        )}

        {!patient && !error && !loading && (
          <div className="empty-state">
            <div className="empty-icon">&#127973;</div>
            <h2>Patient lookup</h2>
            <p>Enter a patient ID to view their semantic health profile — classified conditions, medications, observations, and concept relationships.</p>
            <div className="status-strip">
              <span className="status-item">
                <span className="status-value">3</span>source systems connected
              </span>
              <span className="status-item">
                <span className="status-value">542</span>concepts resolved
              </span>
              <span className="status-item">
                <span className="status-value">1,284</span>patients indexed
              </span>
            </div>
          </div>
        )}

        {patient && (
          <div className="dashboard">
            <div className="patient-card">
              <Avatar name={displayName} />
              <div className="patient-info">
                <h2 className="patient-name">{displayName}</h2>
                <div className="patient-meta">
                  {patient.age != null && <span className="meta-chip">Age: {patient.age}</span>}
                  {patient.birth_date && <span className="meta-chip">DOB: {patient.birth_date}</span>}
                  {patient.gender && <span className="meta-chip capitalize">{patient.gender}</span>}
                  <span className="meta-chip mono">ID: {patient.id ?? patient.patient_id}</span>
                </div>
              </div>
              <button className="close-btn" onClick={reset} aria-label="Clear patient">&#10005;</button>
            </div>

            <div className="data-grid">
              <section className="data-section">
                <div className="section-head cond-head">
                  <span className="sec-icon">&#129657;</span>
                  <h3>Conditions</h3>
                  <span className="count-chip">{conditions.length}</span>
                </div>
                <div className="item-list">
                  {conditions.length === 0
                    ? <p className="no-data">No conditions recorded</p>
                    : conditions.map((c, i) => <ConditionCard key={i} condition={c} />)}
                </div>
              </section>

              <section className="data-section">
                <div className="section-head med-head">
                  <span className="sec-icon">&#128138;</span>
                  <h3>Medications</h3>
                  <span className="count-chip">{medications.length}</span>
                </div>
                <div className="item-list">
                  {medications.length === 0
                    ? <p className="no-data">No medications recorded</p>
                    : medications.map((m, i) => <MedicationCard key={i} medication={m} />)}
                </div>
              </section>
            </div>

            {observations.length > 0 && (
              <section className="data-section full-width">
                <div className="section-head obs-head">
                  <span className="sec-icon">&#128202;</span>
                  <h3>Observations</h3>
                  <span className="count-chip">{observations.length}</span>
                </div>
                <div className="obs-grid">
                  {observations.map((o, i) => <ObservationCard key={i} obs={o} />)}
                </div>
              </section>
            )}

            {relationships.length > 0 && (
              <section className="data-section full-width">
                <div className="section-head rel-head">
                  <span className="sec-icon">&#128279;</span>
                  <h3>Semantic relationships</h3>
                  <span className="count-chip">{relationships.length}</span>
                </div>
                <div className="rel-list">
                  {relationships.map((r, i) => <RelationshipRow key={i} rel={r} index={i} />)}
                </div>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
