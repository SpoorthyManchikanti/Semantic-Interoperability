import { useCountUp } from "../lib/useCountUp";

function StatTile({ label, value, suffix = "", decimals = 0, valueColor }) {
  const animated = useCountUp(value, 400);
  return (
    <div className="stat-tile">
      <span className="stat-label">{label}</span>
      <span className="stat-value" style={valueColor ? { color: valueColor } : undefined}>
        {animated.toFixed(decimals)}
        {suffix}
      </span>
    </div>
  );
}

export default function StatRow({ stats }) {
  const flaggedColor = stats.flaggedCount > 0 ? "var(--brass)" : "var(--teal)";

  return (
    <div className="stat-row">
      <StatTile label="Resolution rate" value={stats.resolutionRate} suffix="%" />
      <StatTile label="Flagged concepts" value={stats.flaggedCount} valueColor={flaggedColor} />
      <StatTile label="Source systems" value={stats.sourceSystemCount} />
      <StatTile label="Avg confidence" value={stats.avgConfidence} suffix="%" decimals={1} />
    </div>
  );
}
