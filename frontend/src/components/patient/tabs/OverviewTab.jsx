export default function OverviewTab({ patient, concepts }) {
  const flagged = concepts.filter((c) => c.status === "flagged");
  const topConditions = (patient.conditions ?? []).slice(0, 5);
  const topMedications = (patient.medications ?? []).slice(0, 5);

  return (
    <div className="overview-tab">
      <section className="data-section">
        <div className="section-head">
          <h3>Top conditions</h3>
          <span className="count-chip">{(patient.conditions ?? []).length}</span>
        </div>
        <div className="item-list">
          {topConditions.length === 0
            ? <p className="no-data">No conditions recorded</p>
            : topConditions.map((c, i) => (
              <div key={i} className="item-card">
                <span className="item-name">{typeof c === "string" ? c : c.condition_name}</span>
              </div>
            ))}
        </div>
      </section>

      <section className="data-section">
        <div className="section-head">
          <h3>Active medications</h3>
          <span className="count-chip">{(patient.medications ?? []).length}</span>
        </div>
        <div className="item-list">
          {topMedications.length === 0
            ? <p className="no-data">No medications recorded</p>
            : topMedications.map((m, i) => (
              <div key={i} className="item-card">
                <span className="item-name">{typeof m === "string" ? m : m.medication_name}</span>
              </div>
            ))}
        </div>
      </section>

      {flagged.length > 0 && (
        <div className="error-box" role="status">
          <span className="error-msg">{flagged.length} concept(s) flagged for review — see Semantic Profile.</span>
        </div>
      )}
    </div>
  );
}
