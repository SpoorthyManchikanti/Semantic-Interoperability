function statusFor(value, unit) {
  if (value == null) return "neutral";
  if (unit !== "%") return "neutral";
  if (value >= 90) return "good";
  if (value >= 70) return "warn";
  return "bad";
}

export default function KpiCard({ tag, label, value, unit = "", decimals = 0, status }) {
  const resolvedStatus = status ?? statusFor(value, unit);
  const display = value == null ? "—" : value.toFixed(decimals);
  return (
    <div className="kpi-card">
      <div className="kpi-card-top">
        <span className="kpi-tag">{tag}</span>
        <span className={`kpi-status kpi-status-${resolvedStatus}`} />
      </div>
      <span className="kpi-value">{display}{value != null ? unit : ""}</span>
      <span className="kpi-label">{label}</span>
    </div>
  );
}
