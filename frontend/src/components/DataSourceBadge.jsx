// Renders a real breakdown from patients.data_source (via
// GET /patients/data-source-summary) — not a hardcoded label. Pages that
// aren't tied to one specific patient (Dashboard, Ontology Browser) use
// this to show provenance in aggregate.
export default function DataSourceBadge({ breakdown }) {
  if (!breakdown || breakdown.length === 0) return null;

  const text = breakdown
    .map((b) => `${b.count} from ${b.data_source ?? "Unknown"}`)
    .join(", ");

  return <span className="data-source-badge">Data Source: {text}</span>;
}
