import { useEffect, useState } from "react";
import { getAiSummary } from "../../../api";

export default function AiSummaryTab({ patientId }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
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

  return (
    <div className="ai-summary">
      {result.confidence != null && (
        <div className="ai-summary-confidence">
          <span className="badge conf-badge">Overall mapping confidence: {result.confidence}%</span>
        </div>
      )}
      <p className="ai-summary-text">{result.summary}</p>
    </div>
  );
}
