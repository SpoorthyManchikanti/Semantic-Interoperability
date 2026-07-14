function Avatar({ name }) {
  const parts = (name || "").split(" ").filter(Boolean);
  const initials = parts.length >= 2
    ? parts[0][0] + parts[parts.length - 1][0]
    : parts[0]?.[0] ?? "?";
  return <div className="avatar">{initials.toUpperCase()}</div>;
}

export default function PatientHeader({ patient, displayName, onClose }) {
  return (
    <div className="patient-card patient-card-anim">
      <Avatar name={displayName} />
      <div className="patient-info">
        <h2 className="patient-name">{displayName}</h2>
        <div className="patient-meta">
          <span className="meta-chip mono">MRN: {patient.id ?? patient.patient_id}</span>
          {patient.age != null && <span className="meta-chip">Age: {patient.age}</span>}
          {patient.gender && <span className="meta-chip capitalize">{patient.gender}</span>}
        </div>
      </div>
      {/* Backend does not return a last-encounter date on GET /patients/{id} today.
          Once it does (e.g. patient.last_encounter_date), render it here. */}
      {patient.last_encounter_date && (
        <div className="patient-encounter">
          <span className="encounter-label">Last encounter</span>
          <span className="encounter-date">{patient.last_encounter_date}</span>
        </div>
      )}
      {onClose && (
        <button className="close-btn" onClick={onClose} aria-label="Clear patient">&#10005;</button>
      )}
    </div>
  );
}
