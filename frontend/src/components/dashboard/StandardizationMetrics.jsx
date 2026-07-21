import { PieChart, Pie, Cell } from "recharts";

const COLORS = ["#4A6670", "#B08D57", "#A2493D", "#DEDBD2"];

function Bar({ label, value, total, color }) {
  const pct = total ? Math.round((value / total) * 100) : 0;
  return (
    <div className="metric-bar-row">
      <span className="metric-bar-label">{label}</span>
      <div className="metric-bar-track">
        <div className="metric-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="metric-bar-value">{value} ({pct}%)</span>
    </div>
  );
}

export default function StandardizationMetrics({ metrics }) {
  const { total, mapped, unmapped, needsReview, duplicates } = metrics;
  const data = [
    { name: "Mapped", value: mapped },
    { name: "Unmapped", value: unmapped },
    { name: "Needs review", value: needsReview },
  ].filter((d) => d.value > 0);

  return (
    <div className="standardization-panel">
      <div className="donut-wrap">
        <PieChart width={160} height={160}>
          <Pie data={data} dataKey="value" innerRadius={50} outerRadius={72} paddingAngle={2}>
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
        </PieChart>
        <div className="donut-center">
          <span className="donut-pct">{total ? Math.round((mapped / total) * 100) : 0}%</span>
          <span className="donut-label">standardized</span>
        </div>
      </div>
      <div className="metric-bars">
        <Bar label="Mapped concepts" value={mapped} total={total} color="#4A6670" />
        <Bar label="Unmapped / missing codes" value={unmapped} total={total} color="#B08D57" />
        <Bar label="Needs review (invalid terminology)" value={needsReview} total={total} color="#A2493D" />
        <Bar label="Duplicate concept names" value={duplicates} total={total} color="#DEDBD2" />
      </div>
    </div>
  );
}
