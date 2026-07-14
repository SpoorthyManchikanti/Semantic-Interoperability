import { Treemap, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const PALETTE = ["#3B4A6B", "#4A6670", "#B08D57", "#A2493D", "#6C82AD", "#7FA3AC", "#C9A26D"];

function buildHistogram(concepts) {
  const buckets = [
    { range: "<70%", min: 0, max: 0.7, count: 0 },
    { range: "70-80%", min: 0.7, max: 0.8, count: 0 },
    { range: "80-90%", min: 0.8, max: 0.9, count: 0 },
    { range: "90-95%", min: 0.9, max: 0.95, count: 0 },
    { range: "95-100%", min: 0.95, max: 1.001, count: 0 },
  ];
  for (const c of concepts) {
    if (c.confidence == null) continue;
    const b = buckets.find((b) => c.confidence >= b.min && c.confidence < b.max);
    if (b) b.count += 1;
  }
  return buckets;
}

function buildCategoryTreemap(concepts) {
  const counts = {};
  for (const c of concepts) {
    if (!c.category) continue;
    counts[c.category] = (counts[c.category] ?? 0) + 1;
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([name, size], i) => ({ name, size, fill: PALETTE[i % PALETTE.length] }));
}

export default function AiIntelligence({ concepts }) {
  const uniqueConcepts = concepts.length;
  const withConfidence = concepts.filter((c) => c.confidence != null);
  const avgConfidence = withConfidence.length
    ? Math.round((withConfidence.reduce((s, c) => s + c.confidence, 0) / withConfidence.length) * 1000) / 10
    : 0;
  const lowConfidence = concepts.filter((c) => c.confidence != null && c.confidence < 0.8).length;
  const categories = buildCategoryTreemap(concepts);
  const histogram = buildHistogram(concepts);

  return (
    <div className="ai-intel-panel">
      <div className="ai-intel-stats">
        <div className="ai-intel-stat"><span className="ai-intel-value">{uniqueConcepts}</span><span className="ai-intel-label">Unique concepts</span></div>
        <div className="ai-intel-stat"><span className="ai-intel-value">{avgConfidence}%</span><span className="ai-intel-label">Avg AI confidence</span></div>
        <div className="ai-intel-stat"><span className="ai-intel-value">{lowConfidence}</span><span className="ai-intel-label">Low-confidence concepts</span></div>
        <div className="ai-intel-stat"><span className="ai-intel-value">{categories.length}</span><span className="ai-intel-label">Categories created</span></div>
      </div>

      <div className="ai-intel-charts">
        <div className="ai-intel-chart">
          <span className="chart-title">Confidence distribution</span>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={histogram}>
              <XAxis dataKey="range" tick={{ fontSize: 10, fill: "var(--text)" }} axisLine={{ stroke: "var(--rule)" }} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "var(--text)" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ fontSize: 12, background: "var(--surface)", border: "1px solid var(--rule)" }} />
              <Bar dataKey="count" fill="#3B4A6B" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="ai-intel-chart">
          <span className="chart-title">Top clinical categories</span>
          <ResponsiveContainer width="100%" height={160}>
            <Treemap data={categories} dataKey="size" stroke="var(--bg)" isAnimationActive={false} />
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
