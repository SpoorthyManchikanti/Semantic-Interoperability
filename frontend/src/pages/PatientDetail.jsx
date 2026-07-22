import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { getPatient } from "../api";
import PatientHeader from "../components/PatientHeader";
import StatRow from "../components/StatRow";
import RiskFlagCallout from "../components/patient/RiskFlagCallout";
import { buildConceptList, deriveStats } from "../lib/deriveConcepts";
import OverviewTab from "../components/patient/tabs/OverviewTab";
import ClinicalDataTab from "../components/patient/tabs/ClinicalDataTab";
import SemanticProfileTab from "../components/patient/tabs/SemanticProfileTab";
import OntologyTab from "../components/patient/tabs/OntologyTab";
import TimelineTab from "../components/patient/tabs/TimelineTab";
import AiSummaryTab from "../components/patient/tabs/AiSummaryTab";
import "./PatientDetail.css";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "clinical", label: "Clinical Data" },
  { key: "semantic", label: "Semantic Profile" },
  { key: "ontology", label: "Ontology Relationships" },
  { key: "timeline", label: "Timeline" },
  { key: "ai-summary", label: "AI Summary" },
];

export default function PatientDetail() {
  const { patientId } = useParams();
  // Keyed on patientId so switching patients fully remounts this view,
  // giving every piece of state (including nested tabs) a clean slate
  // instead of manually resetting each one inside an effect.
  return <PatientDetailView key={patientId} patientId={patientId} />;
}

function PatientDetailView({ patientId }) {
  const [patient, setPatient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("overview");

  useEffect(() => {
    getPatient(patientId)
      .then(setPatient)
      .catch((err) => setError(err.message || "Failed to fetch patient."))
      .finally(() => setLoading(false));
  }, [patientId]);

  const displayName = patient
    ? (patient.name || `${patient.first_name ?? ""} ${patient.last_name ?? ""}`.trim() || "Unknown")
    : "";

  const concepts = useMemo(() => buildConceptList(patient), [patient]);
  const stats = useMemo(() => deriveStats(concepts), [concepts]);

  if (loading) return <p className="no-data">Loading patient…</p>;

  if (error) {
    return (
      <div className="error-box" role="alert">
        <span className="error-msg">{error}</span>
      </div>
    );
  }

  if (!patient) return null;

  return (
    <div className="dashboard patient-detail">
      <PatientHeader patient={patient} displayName={displayName} onClose={null} />
      <RiskFlagCallout patientId={patientId} />
      <StatRow stats={stats} />

      <div className="tab-bar" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            className={`tab-item${tab === t.key ? " active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="tab-panel">
        {tab === "overview" && <OverviewTab patient={patient} concepts={concepts} />}
        {tab === "clinical" && <ClinicalDataTab patient={patient} />}
        {tab === "semantic" && <SemanticProfileTab concepts={concepts} onViewOntology={() => setTab("ontology")} />}
        {tab === "ontology" && <OntologyTab patientId={patientId} />}
        {tab === "timeline" && <TimelineTab patientId={patientId} />}
        {tab === "ai-summary" && <AiSummaryTab patientId={patientId} />}
      </div>
    </div>
  );
}
