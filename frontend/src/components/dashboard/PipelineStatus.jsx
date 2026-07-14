const STATUS_LABEL = {
  active: "Active",
  processing: "Processing",
  planned: "Planned",
};

function Stage({ stage, isLast }) {
  return (
    <>
      <div className={`pipeline-stage stage-${stage.status}`}>
        <span className="stage-status-label">{STATUS_LABEL[stage.status]}</span>
        <span className="stage-name">{stage.label}</span>
        <span className="stage-count">{stage.records_processed.toLocaleString()}</span>
        <span className="stage-count-label">records</span>
        {stage.success_rate != null && (
          <span className="stage-success">{stage.success_rate}% success</span>
        )}
      </div>
      {!isLast && (
        <div className={`pipeline-connector connector-${stage.status}`}>
          <svg viewBox="0 0 40 2" preserveAspectRatio="none">
            <line x1="0" y1="1" x2="40" y2="1" />
          </svg>
        </div>
      )}
    </>
  );
}

export default function PipelineStatus({ pipeline }) {
  const stages = pipeline?.stages ?? [];
  return (
    <div className="pipeline-status">
      <div className="pipeline-flow">
        {stages.map((s, i) => (
          <Stage key={s.key} stage={s} isLast={i === stages.length - 1} />
        ))}
      </div>
    </div>
  );
}
