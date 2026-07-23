import { useState } from "react";

const SEVERITY_LABEL = { success: "Success", error: "Error", info: "Info" };
const DEFAULT_LIMIT = 5;

function timeAgo(iso) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function ActivityFeed({ events }) {
  const [expanded, setExpanded] = useState(false);

  if (!events || events.length === 0) {
    return <p className="no-data">No recent platform activity.</p>;
  }

  // Events already arrive sorted most-recent-first (see GET /dashboard/activity),
  // so the default slice is naturally the latest 5 regardless of how many
  // total events were fetched.
  const hasMore = events.length > DEFAULT_LIMIT;
  const visible = expanded ? events : events.slice(0, DEFAULT_LIMIT);

  return (
    <div className="activity-feed">
      {visible.map((e, i) => (
        <div key={i} className="activity-row">
          <span className={`activity-badge activity-${e.severity}`}>{SEVERITY_LABEL[e.severity] ?? e.severity}</span>
          <div className="activity-body">
            <span className="item-name">{e.title}</span>
            <span className="activity-detail">{e.detail}</span>
          </div>
          <span className="activity-time">{timeAgo(e.timestamp)}</span>
        </div>
      ))}
      {hasMore && (
        <button
          type="button"
          className="exception-link-btn activity-toggle-btn"
          onClick={() => setExpanded((x) => !x)}
        >
          {expanded ? "Show recent 5" : `Show all (${events.length})`}
        </button>
      )}
    </div>
  );
}
