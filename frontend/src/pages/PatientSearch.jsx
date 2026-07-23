import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { searchPatients, listPatients, getDemoSubsetPatients, getPatient } from "../api";
import { buildConceptList } from "../lib/deriveConcepts";
import { useResizableWidth } from "../lib/useResizableWidth";
import "./PatientSearch.css";

const DEFAULT_LIST_LIMIT = 20;
const TOP_CONDITIONS_LIMIT = 5;
const LIST_DEFAULT_WIDTH = 340;
const LIST_MIN_WIDTH = 250;
const LIST_MAX_WIDTH = 600;

function PatientRow({ patient, active, onSelect }) {
  return (
    <button
      className={`patient-result-row${active ? " active" : ""}`}
      onClick={() => onSelect(patient)}
    >
      <div className="patient-result-row-main">
        <span className="item-name">{patient.first_name} {patient.last_name}</span>
        <span className="badge cat-badge">{patient.gender}</span>
      </div>
      <span className="code-inline mono">{patient.patient_id}</span>
    </button>
  );
}

function SearchResults({ q, selected, onSelect }) {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    searchPatients({ q })
      .then(setResults)
      .catch((err) => setError(err.message || "Search failed"))
      .finally(() => setLoading(false));
  }, [q]);

  if (error) return <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>;
  if (loading) return <p className="no-data">Searching…</p>;

  return (
    <section className="data-section full-width">
      <div className="section-head">
        <h3>Results for &ldquo;{q}&rdquo;</h3>
        <span className="count-chip">{results.length}</span>
      </div>
      <div className="item-list patient-result-list">
        {results.length === 0
          ? <p className="no-data">No patients matched. Try a shorter fragment of the name or ID.</p>
          : results.map((p) => (
            <PatientRow
              key={p.patient_id}
              patient={p}
              active={selected?.patient_id === p.patient_id}
              onSelect={onSelect}
            />
          ))}
      </div>
    </section>
  );
}

// Shown until the user searches. Two sections: demo-subset patients (the
// live list Admin Review also uses — 15 original demo patients, 3 synthetic
// clones, plus anyone ingested live via /ingest, appended automatically by
// register_ingested_patient — see GET /patients/demo-subset) pinned at the
// top, then the first 20 remaining patients by name below. Never a blank
// results area, and the pinned section updates itself with zero code
// changes as new patients are ingested.
function DefaultPatientList({ selected, onSelect }) {
  const [demoPatients, setDemoPatients] = useState(null);
  const [demoError, setDemoError] = useState(null);
  const [patients, setPatients] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getDemoSubsetPatients()
      .then(setDemoPatients)
      .catch((err) => setDemoError(err.message || "Failed to load demo patients"));
  }, []);

  useEffect(() => {
    listPatients(DEFAULT_LIST_LIMIT, 0, true)
      .then(setPatients)
      .catch((err) => setError(err.message || "Failed to load patients"));
  }, []);

  return (
    <div className="patient-default-list">
      <section className="data-section full-width">
        <div className="section-head">
          <h3>Demo Patients</h3>
          {demoPatients && <span className="count-chip">{demoPatients.length}</span>}
        </div>
        <div className="item-list patient-result-list">
          {demoError && <div className="error-box" role="alert"><span className="error-msg">{demoError}</span></div>}
          {!demoPatients && !demoError && <p className="no-data">Loading demo patients…</p>}
          {demoPatients && demoPatients.map((p) => (
            <PatientRow
              key={p.patient_id}
              patient={p}
              active={selected?.patient_id === p.patient_id}
              onSelect={onSelect}
            />
          ))}
        </div>
      </section>

      <section className="data-section full-width">
        <div className="section-head">
          <h3>All Patients</h3>
          {patients && <span className="count-chip">{patients.length}</span>}
        </div>
        <div className="item-list patient-result-list">
          {error && <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>}
          {!patients && !error && <p className="no-data">Loading patients…</p>}
          {patients && patients.map((p) => (
            <PatientRow
              key={p.patient_id}
              patient={p}
              active={selected?.patient_id === p.patient_id}
              onSelect={onSelect}
            />
          ))}
        </div>
      </section>
    </div>
  );
}

// Quick preview for the selected row — real data via the same GET
// /patients/{id} the full detail page uses, just summarized instead of
// rendering every tab. omop resolution is computed directly from each
// concept's omop_concept_id rather than reusing deriveStats()'s
// resolutionRate, which is keyed off a `status` field the DB-backed
// /patients/{id} response doesn't populate (it would always read 100%).
function PatientPreviewPanel({ patient }) {
  const [full, setFull] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setFull(null);
    setLoading(true);
    setError(null);
    getPatient(patient.patient_id)
      .then(setFull)
      .catch((err) => setError(err.message || "Failed to load patient"))
      .finally(() => setLoading(false));
  }, [patient.patient_id]);

  if (error) return <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>;
  if (loading || !full) return <p className="no-data">Loading preview…</p>;

  const conditions = full.conditions ?? [];
  const medications = full.medications ?? [];
  const topConditions = conditions.slice(0, TOP_CONDITIONS_LIMIT);

  const concepts = buildConceptList(full);
  const resolvedCount = concepts.filter((c) => c.omopConceptId).length;
  const resolutionRate = concepts.length > 0 ? Math.round((resolvedCount / concepts.length) * 100) : null;

  return (
    <div className="patient-preview">
      <div className="explorer-detail-header">
        <h3>{full.first_name} {full.last_name}</h3>
        <div className="item-badges">
          <span className="badge cat-badge">{full.gender}</span>
          {full.birth_date && <span className="badge subcat-badge">DOB {full.birth_date}</span>}
          <span className="code-inline mono">{full.patient_id}</span>
        </div>
      </div>

      <div className="patient-preview-stats">
        <div className="patient-preview-stat">
          <span className="stat-value">{medications.length}</span>
          <span className="stat-label">Medications</span>
        </div>
        <div className="patient-preview-stat">
          <span className="stat-value">{resolutionRate != null ? `${resolutionRate}%` : "—"}</span>
          <span className="stat-label">OMOP resolution rate</span>
        </div>
      </div>

      <div className="patient-preview-conditions">
        <span className="review-panel-label">
          Top conditions {conditions.length > TOP_CONDITIONS_LIMIT ? `(${TOP_CONDITIONS_LIMIT} of ${conditions.length})` : ""}
        </span>
        {topConditions.length === 0
          ? <p className="no-data">No conditions recorded</p>
          : (
            <div className="item-list">
              {topConditions.map((c, i) => (
                <div key={i} className="item-card">
                  <span className="item-name">{c.condition_name}</span>
                </div>
              ))}
            </div>
          )}
      </div>

      <Link className="ingest-view-link" to={`/patients/${full.patient_id}`}>
        View full record &rarr;
      </Link>
    </div>
  );
}

export default function PatientSearch() {
  const [searchParams] = useSearchParams();
  const q = searchParams.get("q") ?? "";
  const [query, setQuery] = useState(q);
  const [selected, setSelected] = useState(null);
  const navigate = useNavigate();
  const { width: listWidth, dividerProps } = useResizableWidth(LIST_DEFAULT_WIDTH, LIST_MIN_WIDTH, LIST_MAX_WIDTH);

  function onSearch(e) {
    e.preventDefault();
    const value = query.trim();
    if (!value) return;
    navigate(`/patients?q=${encodeURIComponent(value)}`);
  }

  return (
    <div className="patient-search-page">
      <section className="search-section">
        <h2 className="page-title">Patient search</h2>
        <p className="page-subtitle">
          Search by full or partial name, or patient ID — matches anywhere in the field, not just exact.
        </p>
        <form className="search-bar" onSubmit={onSearch}>
          <input
            className="search-input"
            placeholder="Search by name or patient ID..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          <button className="search-btn" type="submit" disabled={!query.trim()}>
            Search
          </button>
        </form>
      </section>

      <div className="patient-search-layout" style={{ "--list-width": `${listWidth}px` }}>
        {q
          ? <SearchResults key={q} q={q} selected={selected} onSelect={setSelected} />
          : <DefaultPatientList selected={selected} onSelect={setSelected} />}

        <div
          className="resizable-divider"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize results panel"
          tabIndex={0}
          {...dividerProps}
        />

        <section className="patient-search-detail data-section">
          {!selected
            ? <p className="no-data">Select a patient from the list to see a quick preview.</p>
            : <PatientPreviewPanel key={selected.patient_id} patient={selected} />}
        </section>
      </div>
    </div>
  );
}
