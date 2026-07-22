import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { getOmopResolution, getDataSourceSummary } from "../api";
import KpiCard from "../components/dashboard/KpiCard";
import DataSourceBadge from "../components/DataSourceBadge";
import "./Dashboard.css";
import "./OntologyBrowser.css";

const SOURCE_TYPE_LABELS = {
  condition: "Condition",
  medication: "Medication",
  observation: "Observation",
};

// The demo's full patient cohort — the denominator for the mini
// proportion bar next to "Affects N patients".
const DEMO_COHORT_SIZE = 15;

function ChevronIcon({ expanded }) {
  return (
    <svg
      className={`chevron-icon${expanded ? " expanded" : ""}`}
      width="10"
      height="10"
      viewBox="0 0 10 10"
      fill="none"
      aria-hidden="true"
    >
      <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function UnresolvedGroupCard({ group }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  const patientCount = group.patients.length;
  const proportionPct = Math.min(100, Math.round((patientCount / DEMO_COHORT_SIZE) * 100));
  const severity = group.vocabulary_mismatch ? "mismatch" : "missing";

  return (
    <div className="unresolved-group-card">
      <div className="unresolved-card-head">
        <span className="unresolved-concept-name">{group.concept_name}</span>
        {group.vocabulary_mismatch
          ? <span className="badge mismatch-badge">Vocabulary Mismatch</span>
          : <span className="badge missing-data-badge">Missing Source Data</span>}
      </div>

      <div className="unresolved-meta-row">
        {group.vocabulary_code && (
          <span className="unresolved-meta-item">{group.vocabulary_id}: {group.vocabulary_code}</span>
        )}
        <span className="unresolved-meta-item">
          Affects {patientCount} patient{patientCount === 1 ? "" : "s"}
        </span>
        <span
          className="metric-bar-track unresolved-mini-track"
          title={`${patientCount} of ${DEMO_COHORT_SIZE} demo patients`}
        >
          <span
            className={`metric-bar-fill unresolved-mini-fill fill-${severity}`}
            style={{ width: `${proportionPct}%` }}
          />
        </span>
      </div>

      <p className="unresolved-reason">{group.reason}</p>

      <div className="unresolved-card-actions">
        <button
          className="expand-toggle-btn"
          onClick={() => setExpanded((e) => !e)}
          aria-expanded={expanded}
        >
          <ChevronIcon expanded={expanded} />
          {expanded ? "Hide patients" : "Show patients"}
        </button>

        {group.vocabulary_mismatch && (
          <button
            className="view-ontology-btn"
            onClick={() => navigate(`/admin?tab=data-quality&concept=${group.concept_id}`)}
          >
            Resolve in Admin Review &#8594;
          </button>
        )}
      </div>

      {expanded && (
        <div className="unresolved-patient-list">
          {group.patients.map((name, i) => (
            <span key={i} className="badge subcat-badge">{name}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function OntologyBrowser() {
  const [data, setData] = useState(null);
  const [dataSourceBreakdown, setDataSourceBreakdown] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getOmopResolution()
      .then(setData)
      .catch((err) => setError(err.message || "Failed to load OMOP resolution data"));

    // Fetched separately — a failure here shouldn't block the rest of the page.
    getDataSourceSummary().then(setDataSourceBreakdown).catch(() => setDataSourceBreakdown([]));
  }, []);

  // Group the flat (concept, patient) rows by distinct issue — same
  // concept_name + reason — so a concept shared by many patients (e.g. the
  // Unknown fallback, shared by all 15) shows as one entry with an
  // expandable patient list, not one repeated row per patient.
  const unresolvedGroups = useMemo(() => {
    if (!data) return [];
    const map = new Map();
    for (const row of data.unresolved_details) {
      const key = `${row.concept_name}||${row.reason}`;
      if (!map.has(key)) {
        map.set(key, {
          concept_id: row.concept_id,
          concept_name: row.concept_name,
          vocabulary_id: row.vocabulary_id,
          vocabulary_code: row.vocabulary_code,
          vocabulary_mismatch: row.vocabulary_mismatch,
          reason: row.reason,
          patients: [],
        });
      }
      map.get(key).patients.push(`${row.patient_first_name} ${row.patient_last_name}`);
    }
    return Array.from(map.values());
  }, [data]);

  if (error) {
    return <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>;
  }

  if (!data) {
    return <p className="no-data">Loading OMOP resolution data…</p>;
  }

  const chartData = data.breakdown_by_source_type.map((row) => ({
    source_type: SOURCE_TYPE_LABELS[row.source_type] ?? row.source_type,
    resolved: row.resolved,
    not_resolved: row.not_resolved,
  }));

  return (
    <div className="dashboard-page ontology-browser-page">
      <div className="dashboard-header">
        <h2 className="page-title">Ontology Browser</h2>
        <p className="page-subtitle">
          How many of Agent 1's classified concepts resolve to a real Athena/OMOP standard
          concept — read-only cross-reference, no reprocessing, no Agent 1 changes.
        </p>
        <DataSourceBadge breakdown={dataSourceBreakdown} />
      </div>

      <div className="kpi-grid">
        <KpiCard tag="TC" label="Total Concepts" value={data.total_concepts} />
        <KpiCard tag="RC" label="Resolved Count" value={data.resolved_count} />
        <KpiCard
          tag="RP"
          label="Resolution Percentage"
          value={data.resolution_percentage}
          unit="%"
          decimals={1}
        />
        <KpiCard
          tag="DQ"
          label="Data Quality Findings"
          value={unresolvedGroups.length}
          status={unresolvedGroups.length > 0 ? "warn" : "good"}
        />
      </div>

      <section className="dashboard-section">
        <h3 className="dashboard-section-title">Resolution by source type</h3>
        <div className="ontology-chart">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--rule-light)" />
              <XAxis dataKey="source_type" stroke="var(--text)" tick={{ fontSize: 12 }} />
              <YAxis stroke="var(--text)" tick={{ fontSize: 12 }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--rule)", fontSize: 12 }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="resolved" name="Resolved" fill="var(--teal)" radius={[3, 3, 0, 0]} />
              <Bar dataKey="not_resolved" name="Not resolved" fill="var(--critical)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="data-section full-width">
        <div className="section-head">
          <h3>Unresolved concepts</h3>
          <span className="count-chip">{unresolvedGroups.length}</span>
        </div>
        <div className="item-list">
          {unresolvedGroups.length === 0
            ? <p className="no-data">Every concept resolved — nothing to show.</p>
            : unresolvedGroups.map((group, i) => (
              <UnresolvedGroupCard key={i} group={group} />
            ))}
        </div>
      </section>
    </div>
  );
}
