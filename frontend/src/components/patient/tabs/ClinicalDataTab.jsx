import ConditionCard from "../ConditionCard";
import MedicationCard from "../MedicationCard";
import ObservationCard from "../ObservationCard";

export default function ClinicalDataTab({ patient }) {
  const conditions = patient?.conditions ?? [];
  const medications = patient?.medications ?? [];
  const observations = patient?.observations ?? [];

  return (
    <div>
      <div className="data-grid">
        <section className="data-section">
          <div className="section-head cond-head">
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
            <h3>Observations</h3>
            <span className="count-chip">{observations.length}</span>
          </div>
          <div className="obs-grid">
            {observations.map((o, i) => <ObservationCard key={i} obs={o} />)}
          </div>
        </section>
      )}
    </div>
  );
}
