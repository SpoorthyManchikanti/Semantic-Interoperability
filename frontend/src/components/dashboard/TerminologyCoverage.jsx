import { RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";

const ORDER = ["SNOMED", "LOINC", "RxNorm", "ICD-10"];
const COLOR = { SNOMED: "#A2493D", LOINC: "#4A6670", RxNorm: "#3B4A6B", "ICD-10": "#B08D57" };

function CoverageDial({ vocab, entry }) {
  if (!entry) {
    return (
      <div className="coverage-dial">
        <span className="coverage-dial-title">{vocab}</span>
        <p className="no-data" style={{ padding: "24px 0" }}>No data ingested</p>
      </div>
    );
  }
  const data = [{ name: vocab, value: entry.coverage_pct, fill: COLOR[vocab] }];
  return (
    <div className="coverage-dial">
      <span className="coverage-dial-title">{vocab}</span>
      <div className="coverage-dial-chart">
        <RadialBarChart
          width={140}
          height={140}
          cx="50%"
          cy="50%"
          innerRadius="70%"
          outerRadius="100%"
          data={data}
          startAngle={90}
          endAngle={-270}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
          <RadialBar background={{ fill: "var(--rule-light)" }} dataKey="value" cornerRadius={8} />
        </RadialBarChart>
        <span className="coverage-dial-pct">{entry.coverage_pct}%</span>
      </div>
      <span className="coverage-dial-detail">{entry.with_code} / {entry.total} mapped</span>
      <span className="coverage-dial-detail muted">{entry.total - entry.with_code} unmapped</span>
    </div>
  );
}

export default function TerminologyCoverage({ vocabularyCoverage }) {
  const byVocab = Object.fromEntries((vocabularyCoverage ?? []).map((v) => [v.vocabulary_id, v]));
  return (
    <div className="coverage-grid">
      {ORDER.map((v) => <CoverageDial key={v} vocab={v} entry={byVocab[v]} />)}
    </div>
  );
}
