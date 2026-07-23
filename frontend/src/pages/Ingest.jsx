import { Fragment, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { startIngestion, getIngestionStatus } from "../api";
import "./Ingest.css";

const STAGES = [
  { key: "ingest", label: "Ingest" },
  { key: "classify", label: "Classify" },
  { key: "standardize_relate", label: "Standardize & Relate" },
  { key: "identity_check", label: "Identity Check" },
  { key: "graph_sync", label: "Graph Sync" },
  { key: "complete", label: "Complete" },
];

const STATUS_LABEL = {
  planned: "Planned",
  running: "Running",
  success: "Success",
  failure: "Failure",
};

const QUEUE_STATUS_LABEL = {
  pending: "Pending",
  running: "Processing",
  success: "Success",
  failure: "Failure",
};

const POLL_INTERVAL_MS = 1200;
const CONNECTOR_PULSE_MS = 900;
const HOLD_BEFORE_ADVANCE_MS = 1400;

function isTerminalJob(job) {
  if (!job) return false;
  if (job.stages.complete.status === "success") return true;
  return Object.values(job.stages).some((s) => s.status === "failure");
}

function StageBox({ stage, meta }) {
  const status = stage.status;
  return (
    <div className={`flow-stage stage-${status}`}>
      <div className="flow-stage-head">
        <span className="flow-stage-status">{STATUS_LABEL[status]}</span>
        {status === "running" && <span className="flow-stage-progress" aria-hidden="true" />}
        {status === "success" && <span className="flow-check" aria-hidden="true">&#10003;</span>}
        {status === "failure" && <span className="flow-error-icon" aria-hidden="true">&#33;</span>}
      </div>
      <div className="flow-stage-name">{meta.label}</div>
      {status === "success" && stage.summary && (
        <p className="flow-stage-summary">{stage.summary}</p>
      )}
      {status === "failure" && stage.error && (
        <p className="flow-stage-error">{stage.error}</p>
      )}
    </div>
  );
}

function ActiveFlow({ file, job, pulsing }) {
  function connectorClassFor(i) {
    if (pulsing[i]) return "flow-connector pulsing";
    const fromDone = job?.stages[STAGES[i].key]?.status === "success";
    return fromDone ? "flow-connector traveled" : "flow-connector";
  }

  const overallComplete = job && job.stages.complete.status === "success";

  return (
    <div className="queue-active-block">
      <p className="queue-active-label">{file.name}</p>
      <div className="ingest-flow">
        {STAGES.map((meta, i) => (
          <Fragment key={meta.key}>
            <StageBox stage={job?.stages?.[meta.key] ?? { status: "planned" }} meta={meta} />
            {i < STAGES.length - 1 && (
              <div className={connectorClassFor(i)}>
                <div className="flow-connector-line" />
              </div>
            )}
          </Fragment>
        ))}
      </div>

      {overallComplete && (
        <div className="ingest-complete-banner">
          <p className="ingest-complete-summary">{job.stages.complete.summary}</p>
          <Link className="ingest-view-link" to={`/patients/${job.patient_id}`}>
            View Patient Record &rarr;
          </Link>
        </div>
      )}
    </div>
  );
}

function CompactQueueRow({ file, item }) {
  const { status, job, error } = item;
  return (
    <div className={`queue-row queue-${status}`}>
      <div className="queue-row-head">
        <span className="queue-status-badge">{QUEUE_STATUS_LABEL[status]}</span>
        <span className="queue-filename">{file.name}</span>
      </div>
      {status === "success" && job && (
        <div className="queue-row-summary">
          <p className="queue-summary-text">{job.stages.complete.summary}</p>
          <Link className="ingest-view-link" to={`/patients/${job.patient_id}`}>
            View Patient Record &rarr;
          </Link>
        </div>
      )}
      {status === "failure" && (
        <p className="queue-error-text">{error || "Ingestion failed."}</p>
      )}
    </div>
  );
}

export default function Ingest() {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [startError, setStartError] = useState(null);

  const [queueFiles, setQueueFiles] = useState([]);
  const [queueItems, setQueueItems] = useState([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [pulsing, setPulsing] = useState({});

  const fileInputRef = useRef(null);
  const prevJobRef = useRef(null);
  const startPromisesRef = useRef({});

  const isProcessing = queueItems.some((it) => it.status === "pending" || it.status === "running");

  function handleFiles(fileList) {
    const files = Array.from(fileList || []);
    if (files.length === 0) return;
    const invalid = files.find((f) => !f.name.toLowerCase().endsWith(".json"));
    if (invalid) {
      setStartError(`"${invalid.name}" isn't a .json file — please choose FHIR JSON bundles only.`);
      return;
    }
    setStartError(null);
    setSelectedFiles(files);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    if (isProcessing) return;
    handleFiles(e.dataTransfer.files);
  }

  function onStart() {
    if (selectedFiles.length === 0 || isProcessing) return;
    setStartError(null);
    startPromisesRef.current = {};
    setQueueFiles(selectedFiles);
    setQueueItems(selectedFiles.map(() => ({ status: "pending", jobId: null, job: null, error: null })));
    setSelectedFiles([]);
    setActiveIndex(0);
  }

  function patchQueueItem(index, partial) {
    setQueueItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...partial } : item)));
  }

  // Drives the queue one file at a time: start the file at activeIndex,
  // poll it to completion, then (unless it's the last file) advance to the
  // next index after a brief hold so the just-finished flow stays visible.
  // A failure here never stops the loop — it always advances the same way
  // a success does.
  //
  // startPromises caches the in-flight/POST-result Promise per index so
  // that React StrictMode's dev-only mount->cleanup->remount cycle can't
  // fire a second real startIngestion() call for the same file: the second
  // effect invocation sees the cached Promise (set synchronously, before
  // any await yields) and just awaits the same one instead of re-POSTing.
  function ensureStarted(index) {
    if (!startPromisesRef.current[index]) {
      startPromisesRef.current[index] = (async () => {
        patchQueueItem(index, { status: "running" });
        const res = await startIngestion(queueFiles[index]);
        patchQueueItem(index, { jobId: res.job_id });
        return res.job_id;
      })();
    }
    return startPromisesRef.current[index];
  }

  useEffect(() => {
    if (activeIndex < 0 || activeIndex >= queueFiles.length) return;

    let cancelled = false;
    prevJobRef.current = null;
    setPulsing({});

    async function run() {
      let jobId;
      try {
        jobId = await ensureStarted(activeIndex);
      } catch (err) {
        if (cancelled) return;
        patchQueueItem(activeIndex, { status: "failure", error: err.message || "Failed to start ingestion" });
        advance();
        return;
      }
      if (cancelled) return;

      async function poll() {
        if (cancelled) return;
        try {
          const data = await getIngestionStatus(jobId);
          if (cancelled) return;
          patchQueueItem(activeIndex, { job: data });
          detectPulse(data);
          if (isTerminalJob(data)) {
            const failedStage = Object.values(data.stages).find((s) => s.status === "failure");
            patchQueueItem(activeIndex, {
              status: failedStage ? "failure" : "success",
              error: failedStage?.error ?? null,
            });
            advance();
          } else {
            setTimeout(poll, POLL_INTERVAL_MS);
          }
        } catch (err) {
          if (!cancelled) {
            patchQueueItem(activeIndex, { status: "failure", error: err.message || "Lost connection to the ingestion job." });
            advance();
          }
        }
      }
      poll();
    }

    function detectPulse(job) {
      const prev = prevJobRef.current;
      if (prev) {
        STAGES.forEach((meta, i) => {
          if (i >= STAGES.length - 1) return;
          const was = prev.stages[meta.key].status === "success";
          const now = job.stages[meta.key].status === "success";
          if (!was && now) {
            setPulsing((p) => ({ ...p, [i]: true }));
            setTimeout(() => setPulsing((p) => ({ ...p, [i]: false })), CONNECTOR_PULSE_MS);
          }
        });
      }
      prevJobRef.current = job;
    }

    function advance() {
      // Leave the last file's full flow diagram on screen (same as the
      // single-file case always has) instead of collapsing it with nothing
      // left to show in its place.
      if (activeIndex < queueFiles.length - 1) {
        setTimeout(() => {
          if (!cancelled) setActiveIndex((i) => i + 1);
        }, HOLD_BEFORE_ADVANCE_MS);
      }
    }

    run();
    return () => { cancelled = true; };
  }, [activeIndex, queueFiles]);

  return (
    <div className="dashboard ingest-page">
      <h2 className="page-title">Ingest New Patients</h2>
      <p className="page-subtitle">
        Upload one or more FHIR JSON bundles to walk them through our real ingestion pipeline — ETL,
        semantic classification, OMOP standardization, relationship discovery, identity resolution, and
        graph sync — with live progress at every stage. Multiple files are processed one at a time.
      </p>

      <section className="ingest-upload">
        <div
          className={`ingest-dropzone${dragOver ? " drag-over" : ""}${isProcessing ? " disabled" : ""}`}
          onDragOver={(e) => { e.preventDefault(); if (!isProcessing) setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => !isProcessing && fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (!isProcessing && (e.key === "Enter" || e.key === " ")) fileInputRef.current?.click(); }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            multiple
            hidden
            onChange={(e) => handleFiles(e.target.files)}
            disabled={isProcessing}
          />
          {selectedFiles.length > 0
            ? (
              <span className="ingest-filename">
                {selectedFiles.length === 1 ? selectedFiles[0].name : `${selectedFiles.length} files selected`}
              </span>
            )
            : <span>Drag &amp; drop one or more FHIR JSON bundles here, or click to choose files</span>}
        </div>

        <button
          className="review-btn approve-btn ingest-start-btn"
          onClick={onStart}
          disabled={selectedFiles.length === 0 || isProcessing}
        >
          {selectedFiles.length > 1 ? `Start Ingestion (${selectedFiles.length} files)` : "Start Ingestion"}
        </button>
      </section>

      {startError && (
        <div className="error-box" role="alert"><span className="error-msg">{startError}</span></div>
      )}

      {queueFiles.length > 0 && (
        <section className="ingest-queue-section">
          <div className="ingest-queue-list">
            {queueFiles.map((file, i) => (
              i === activeIndex
                ? <ActiveFlow key={i} file={file} job={queueItems[i]?.job} pulsing={pulsing} />
                : <CompactQueueRow key={i} file={file} item={queueItems[i]} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
