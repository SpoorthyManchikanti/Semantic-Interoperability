import { useEffect, useState } from "react";
import { getPatientConcepts } from "../../../api";

export default function TimelineTab({ patientId }) {
  const [concepts, setConcepts] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getPatientConcepts(patientId)
      .then((rows) => {
        const withDates = rows
          .filter((r) => r.classified_at)
          .sort((a, b) => new Date(a.classified_at) - new Date(b.classified_at));
        setConcepts(withDates);
      })
      .catch((err) => setError(err.message || "Failed to load timeline"));
  }, [patientId]);

  if (error) return <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>;
  if (!concepts) return <p className="no-data">Loading timeline…</p>;
  if (concepts.length === 0) return <p className="no-data">No timestamped concepts available for this patient.</p>;

  return (
    <div>
      <p className="ontology-caption">
        Semantic processing timeline — when each concept was classified by the AI engine. This reflects data
        pipeline history, not clinical event dates (the source FHIR data doesn&rsquo;t carry onset dates today).
      </p>
      <div className="timeline">
        {concepts.map((c) => (
          <div key={c.concept_id} className="timeline-row">
            <span className="timeline-date">{new Date(c.classified_at).toLocaleString()}</span>
            <span className="timeline-dot" />
            <div className="timeline-content">
              <span className="item-name">{c.concept_name}</span>
              <span className="badge cat-badge">{c.source_type}</span>
              {c.category && <span className="badge subcat-badge">{c.category}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
