import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getPatientRiskFlags } from "../../api";

function flagText(flag) {
  if (flag.type === "needs_review") {
    return `${flag.count} concept${flag.count === 1 ? "" : "s"} pending review`;
  }
  if (flag.type === "potential_duplicate") {
    return `Flagged as potential duplicate of ${flag.other_patient_name}`;
  }
  return flag.description;
}

export default function RiskFlagCallout({ patientId }) {
  const [flags, setFlags] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    setFlags([]);
    getPatientRiskFlags(patientId).then(setFlags).catch(() => setFlags([]));
  }, [patientId]);

  if (flags.length === 0) return null;

  return (
    <div className="risk-flag-callout" role="status">
      {flags.map((flag, i) => {
        const content = (
          <>
            <span className="risk-flag-icon">&#9888;</span>
            <span className="risk-flag-text">{flagText(flag)}</span>
          </>
        );
        // Only the needs_review flag deep-links — it's the only one with a
        // corresponding filterable view (Admin Review's Concept Review tab).
        return flag.type === "needs_review" ? (
          <button
            key={i}
            type="button"
            className="risk-flag-row risk-flag-clickable"
            onClick={() => navigate(`/admin?tab=concept-review&patient=${patientId}`)}
          >
            {content}
          </button>
        ) : (
          <div key={i} className="risk-flag-row">{content}</div>
        );
      })}
    </div>
  );
}
