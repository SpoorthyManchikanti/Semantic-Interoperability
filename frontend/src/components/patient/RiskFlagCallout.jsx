import { useEffect, useState } from "react";
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

  useEffect(() => {
    setFlags([]);
    getPatientRiskFlags(patientId).then(setFlags).catch(() => setFlags([]));
  }, [patientId]);

  if (flags.length === 0) return null;

  return (
    <div className="risk-flag-callout" role="status">
      {flags.map((flag, i) => (
        <div key={i} className="risk-flag-row">
          <span className="risk-flag-icon">&#9888;</span>
          <span className="risk-flag-text">{flagText(flag)}</span>
        </div>
      ))}
    </div>
  );
}
