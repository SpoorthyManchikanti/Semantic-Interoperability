export default function ObservationCard({ obs }) {
  return (
    <div className="item-card observation-card">
      <span className="item-name">
        <span className="name-text">{obs.observation_name}</span>
        {obs.loinc_code && <span className="code-inline">LOINC: {obs.loinc_code}</span>}
      </span>
      <div className="item-badges">
        {obs.observation_value && <span className="badge value-badge">{obs.observation_value}</span>}
        {obs.category && <span className="badge cat-badge">{obs.category}</span>}
        {obs.confidence != null && <span className="badge conf-badge">{Math.round(obs.confidence * 100)}%</span>}
      </div>
    </div>
  );
}
