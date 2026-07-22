import { useEffect, useState } from "react";
import { getAiSummary } from "../../../api";

const PRIORITY_META = {
  high: { label: "High Priority", className: "priority-high" },
  medium: { label: "Medium Priority", className: "priority-medium" },
  low: { label: "Low Priority", className: "priority-low" },
};

function ProblemGroup({ priority, problems }) {
  const [collapsed, setCollapsed] = useState(priority === "low");
  const meta = PRIORITY_META[priority];

  if (problems.length === 0) return null;

  return (
    <div className={`problem-group ${meta.className}`}>
      <div className="problem-group-head">
        <span className="problem-group-title">{meta.label}</span>
        <span className="count-chip">{problems.length}</span>
        {priority === "low" && (
          <button
            type="button"
            className="exception-link-btn"
            onClick={() => setCollapsed((c) => !c)}
          >
            {collapsed ? "Show" : "Hide"}
          </button>
        )}
      </div>
      {!collapsed && (
        <div className="item-list">
          {problems.map((p, i) => (
            <div key={i} className="item-card problem-item">
              <span className="item-name">{p.name}</span>
              {p.confidence != null && (
                <span className="badge conf-badge">{p.confidence}% confidence</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AiSummaryTab({ patientId }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setResult(null);
    setError(null);
    getAiSummary(patientId)
      .then(setResult)
      .catch((err) => setError(err.message || "Failed to generate summary"));
  }, [patientId]);

  if (error) return <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>;

  if (!result) {
    return (
      <div className="ai-summary-skeleton">
        <div className="skeleton-line" style={{ width: "100%" }} />
        <div className="skeleton-line" style={{ width: "92%" }} />
        <div className="skeleton-line" style={{ width: "85%" }} />
        <div className="skeleton-line" style={{ width: "60%" }} />
        <p className="no-data" style={{ marginTop: 12 }}>Generating executive summary…</p>
      </div>
    );
  }

  const structured = result.structured;

  // No classified data yet — result.summary already carries that message.
  if (!structured) {
    return <p className="no-data">{result.summary}</p>;
  }

  const byPriority = { high: [], medium: [], low: [] };
  for (const p of structured.active_problems ?? []) {
    (byPriority[p.priority] ?? byPriority.medium).push(p);
  }

  // Belt-and-suspenders: Step B no longer appends a "Source: ..." line, but
  // strip one defensively in case an older cached narrative is still being
  // served — data provenance now only shows via the patient header badge.
  const narrative = (result.summary || "").replace(/\n+Source:.*$/i, "").trim();

  return (
    <div className="ai-summary">
      {result.confidence != null && (
        <div className="ai-summary-confidence">
          <span className="badge conf-badge">Overall mapping confidence: {result.confidence}%</span>
        </div>
      )}

      {structured.chief_complaints?.length > 0 && (
        <section className="ai-summary-section">
          <h4 className="ai-summary-section-title">Chief Complaints</h4>
          <ul className="ai-summary-bullet-list">
            {structured.chief_complaints.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </section>
      )}

      {(structured.active_problems?.length ?? 0) > 0 && (
        <section className="ai-summary-section">
          <h4 className="ai-summary-section-title">Active Problems</h4>
          <ProblemGroup priority="high" problems={byPriority.high} />
          <ProblemGroup priority="medium" problems={byPriority.medium} />
          <ProblemGroup priority="low" problems={byPriority.low} />
        </section>
      )}

      {structured.active_medications?.length > 0 && (
        <section className="ai-summary-section">
          <h4 className="ai-summary-section-title">Active Medications</h4>
          <ul className="ai-summary-bullet-list">
            {structured.active_medications.map((m, i) => (
              <li key={i}>
                {m.name}
                {m.omop_standard_name && (
                  <span className="ai-summary-med-omop"> — OMOP: {m.omop_standard_name}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Risk flags are already shown page-level via RiskFlagCallout, above
          the KPI row on every tab (including this one) — deliberately not
          duplicated here. */}

      {narrative && (
        <section className="ai-summary-section ai-summary-narrative">
          <h4 className="ai-summary-section-title">Summary</h4>
          <p className="ai-summary-text">{narrative}</p>
        </section>
      )}
    </div>
  );
}
