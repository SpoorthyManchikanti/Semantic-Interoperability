import { useEffect, useMemo, useState } from "react";
import {
  getNeedsReviewConcepts,
  reviewConcept,
  flagPatientConceptException,
  getPatientMatches,
  reviewPatientMatch,
} from "../api";
import "./AdminReview.css";

const REVIEWED_BY = "Demo Reviewer";
const LOW_CONFIDENCE = 0.85;

function ConfidenceBadge({ confidence }) {
  if (confidence == null) return null;
  const pct = Math.round(confidence * 100);
  const severityClass = confidence < LOW_CONFIDENCE ? "conf-badge-critical" : "conf-badge-warning";
  return <span className={`badge ${severityClass}`}>{pct}% confidence</span>;
}

function ReviewPanel({ group, decision, onClose, onSubmitted, onExceptionFlagged }) {
  const [selectedIds, setSelectedIds] = useState(
    () => new Set(group.patients.map((p) => p.patient_concept_id))
  );
  const [category, setCategory] = useState(group.category ?? "");
  const [subcategory, setSubcategory] = useState(group.subcategory ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [flaggingId, setFlaggingId] = useState(null);
  const [exceptionNote, setExceptionNote] = useState("");

  function toggle(patientConceptId) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(patientConceptId)) next.delete(patientConceptId);
      else next.add(patientConceptId);
      return next;
    });
  }

  const allSelected = selectedIds.size === group.patients.length && group.patients.length > 0;

  function toggleAll() {
    setSelectedIds(allSelected ? new Set() : new Set(group.patients.map((p) => p.patient_concept_id)));
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (selectedIds.size === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const extra = decision === "corrected"
        ? { corrected_category: category, corrected_subcategory: subcategory }
        : {};
      await reviewConcept(group.concept_id, {
        decision,
        reviewed_by: REVIEWED_BY,
        patient_concept_ids: Array.from(selectedIds),
        ...extra,
      });
      onSubmitted(Array.from(selectedIds));
    } catch (err) {
      setError(err.message || "Review failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function onSubmitException(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await flagPatientConceptException(flaggingId, {
        note: exceptionNote.trim() || undefined,
        flagged_by: REVIEWED_BY,
      });
      onExceptionFlagged(flaggingId);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(flaggingId);
        return next;
      });
      setFlaggingId(null);
      setExceptionNote("");
    } catch (err) {
      setError(err.message || "Exception flag failed");
    } finally {
      setSubmitting(false);
    }
  }

  const actionLabel = decision === "approved" ? "Approve" : "Submit correction for";

  return (
    <>
      <div className="review-panel-backdrop" onClick={submitting ? undefined : onClose} />
      <div className="review-panel" role="dialog" aria-modal="true" aria-label={`${decision} ${group.concept_name}`}>
        <div className="review-panel-header">
          <h3>{decision === "approved" ? "Approve" : "Correct"}: {group.concept_name}</h3>
          <button className="review-panel-close" onClick={onClose} aria-label="Close panel" disabled={submitting}>
            &#10005;
          </button>
        </div>

        <form className="review-panel-body" onSubmit={onSubmit}>
          {decision === "corrected" && (
            <div className="correction-form">
              <label className="correction-field">
                Category
                <input value={category} onChange={(e) => setCategory(e.target.value)} disabled={submitting} />
              </label>
              <label className="correction-field">
                Subcategory
                <input value={subcategory} onChange={(e) => setSubcategory(e.target.value)} disabled={submitting} />
              </label>
            </div>
          )}

          <div className="review-panel-patient-list">
            <div className="review-panel-list-head">
              <span className="review-panel-label">Pending patients ({group.patients.length})</span>
              <button type="button" className="exception-link-btn" onClick={toggleAll} disabled={submitting}>
                {allSelected ? "Deselect all" : "Select all"}
              </button>
            </div>
            {group.patients.map((p) => (
              <div key={p.patient_concept_id} className="review-panel-patient-row">
                <div className="review-panel-patient-line">
                  <label className="review-panel-checkbox-row">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(p.patient_concept_id)}
                      onChange={() => toggle(p.patient_concept_id)}
                      disabled={submitting}
                    />
                    <span>{p.patient_first_name} {p.patient_last_name}</span>
                  </label>
                  {flaggingId !== p.patient_concept_id && (
                    <button
                      type="button"
                      className="exception-link-btn"
                      onClick={() => setFlaggingId(p.patient_concept_id)}
                      disabled={submitting}
                    >
                      Flag as exception
                    </button>
                  )}
                </div>
                {flaggingId === p.patient_concept_id && (
                  <form className="review-panel-exception-form" onSubmit={onSubmitException}>
                    <input
                      value={exceptionNote}
                      onChange={(e) => setExceptionNote(e.target.value)}
                      placeholder="Why is this patient different? (optional)"
                      disabled={submitting}
                      autoFocus
                    />
                    <button type="submit" className="exception-link-btn" disabled={submitting}>Submit</button>
                    <button
                      type="button"
                      className="exception-link-btn"
                      onClick={() => { setFlaggingId(null); setExceptionNote(""); }}
                      disabled={submitting}
                    >
                      Cancel
                    </button>
                  </form>
                )}
              </div>
            ))}
          </div>

          {error && (
            <div className="error-box" role="alert">
              <span className="error-msg">{error}</span>
            </div>
          )}

          <div className="review-panel-footer">
            <button
              type="submit"
              className="review-btn approve-btn"
              disabled={submitting || selectedIds.size === 0}
            >
              {submitting
                ? <span className="spinner" />
                : `${actionLabel} ${selectedIds.size} patient${selectedIds.size === 1 ? "" : "s"}`}
            </button>
            <button type="button" className="review-btn skip-btn" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </>
  );
}

function ConceptGroupCard({ group, onOpenPanel }) {
  const patientCount = group.patients.length;
  return (
    <div className="item-card review-card">
      <div className="review-card-head">
        <span className="item-name">
          <span className="name-text">{group.concept_name}</span>
        </span>
        <ConfidenceBadge confidence={group.confidence} />
      </div>

      <div className="item-badges">
        <span className="badge cat-badge">{group.category || "Uncategorized"}</span>
        {group.subcategory && <span className="badge subcat-badge">{group.subcategory}</span>}
        <span className="badge subcat-badge">
          Shared by {patientCount} patient{patientCount === 1 ? "" : "s"}
        </span>
      </div>

      <div className="review-actions">
        <button className="review-btn approve-btn" onClick={() => onOpenPanel(group, "approved")}>
          Approve
        </button>
        <button className="review-btn correct-btn" onClick={() => onOpenPanel(group, "corrected")}>
          Correct
        </button>
      </div>
    </div>
  );
}

function ConceptReviewTab() {
  const [concepts, setConcepts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exceptionCount, setExceptionCount] = useState(0);
  const [panel, setPanel] = useState(null); // { conceptId, decision } | null

  useEffect(() => {
    getNeedsReviewConcepts()
      .then(setConcepts)
      .catch((err) => setError(err.message || "Failed to load review queue"))
      .finally(() => setLoading(false));
  }, []);

  function onPatientsResolved(patientConceptIds) {
    // Removes exactly the submitted rows — siblings the reviewer unchecked
    // in the panel stay in the queue untouched, since GET /concepts/needs-review
    // now drops a row as soon as its own patient_concepts.review_decision is
    // set, independent of whether the rest of the concept is resolved.
    const idSet = new Set(patientConceptIds);
    setConcepts((prev) => prev.filter((c) => !idSet.has(c.patient_concept_id)));
    setPanel(null);
  }

  function onExceptionFlagged(patientConceptId) {
    setConcepts((prev) => prev.filter((c) => c.patient_concept_id !== patientConceptId));
    setExceptionCount((prev) => prev + 1);
  }

  // Group the flat per-(patient, concept) rows into one entry per concept_id.
  // Recomputed from the live queue on every change, so a card's patient count
  // is always the current pending count, and a card disappears entirely once
  // its last patient is resolved (concepts.map naturally stops producing it).
  const groups = useMemo(() => {
    const map = new Map();
    for (const c of concepts ?? []) {
      if (!map.has(c.concept_id)) {
        map.set(c.concept_id, {
          concept_id: c.concept_id,
          concept_name: c.concept_name,
          category: c.category,
          subcategory: c.subcategory,
          confidence: c.confidence,
          patients: [],
        });
      }
      map.get(c.concept_id).patients.push({
        patient_concept_id: c.patient_concept_id,
        patient_id: c.patient_id,
        patient_first_name: c.patient_first_name,
        patient_last_name: c.patient_last_name,
      });
    }
    return Array.from(map.values());
  }, [concepts]);

  // Derived live from `groups` rather than snapshotted at open time, so a
  // patient flagged as an exception from inside the panel disappears from
  // the checkbox list immediately instead of lingering until reopened.
  const panelGroup = panel ? groups.find((g) => g.concept_id === panel.conceptId) : null;

  useEffect(() => {
    // If every patient in the open group gets exceptioned out from under it,
    // close the panel instead of leaving it stuck open with nothing to show.
    if (panel && !panelGroup) setPanel(null);
  }, [panel, panelGroup]);

  if (error) return <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>;
  if (loading) return <p className="no-data">Loading review queue…</p>;

  return (
    <section className="data-section full-width">
      <div className="section-head">
        <h3>Concepts needing review</h3>
        <span className="count-chip">{groups.length}</span>
      </div>
      {exceptionCount > 0 && (
        <p className="no-data exception-summary">
          {exceptionCount} flagged as patient-specific exceptions
        </p>
      )}
      <div className="item-list">
        {groups.length === 0
          ? <p className="no-data">No concepts pending review — queue is empty.</p>
          : groups.map((g) => (
            <ConceptGroupCard
              key={g.concept_id}
              group={g}
              onOpenPanel={(group, decision) => setPanel({ conceptId: group.concept_id, decision })}
            />
          ))}
      </div>

      {panel && panelGroup && (
        <ReviewPanel
          group={panelGroup}
          decision={panel.decision}
          onClose={() => setPanel(null)}
          onSubmitted={onPatientsResolved}
          onExceptionFlagged={onExceptionFlagged}
        />
      )}
    </section>
  );
}

function MatchIndicator({ label, matched }) {
  return (
    <span className={`badge match-indicator ${matched ? "match-yes" : "match-no"}`}>
      {matched ? "✓" : "✗"} {label}
    </span>
  );
}

function DuplicateReviewCard({ match, onResolved }) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function submit(decision) {
    setSubmitting(true);
    setError(null);
    try {
      await reviewPatientMatch(match.id, { decision, reviewed_by: REVIEWED_BY });
      onResolved(match.id);
    } catch (err) {
      setError(err.message || "Review failed");
      setSubmitting(false);
    }
  }

  const confidencePct = Math.round(match.match_confidence * 100);
  const nameSimPct = match.matched_on?.name_similarity != null
    ? Math.round(match.matched_on.name_similarity * 100)
    : null;

  return (
    <div className="item-card duplicate-card">
      <div className="duplicate-pair">
        <div className="duplicate-patient">
          <span className="item-name">{match.patient_1_first_name} {match.patient_1_last_name}</span>
          <span className="code-inline">DOB {match.patient_1_birth_date}</span>
        </div>
        <span className="duplicate-vs">vs</span>
        <div className="duplicate-patient">
          <span className="item-name">{match.patient_2_first_name} {match.patient_2_last_name}</span>
          <span className="code-inline">DOB {match.patient_2_birth_date}</span>
        </div>
      </div>

      <div className="item-badges">
        <span className="badge conf-badge">{confidencePct}% match confidence</span>
        {match.matched_on && (
          <>
            <MatchIndicator label="DOB" matched={match.matched_on.dob_match} />
            <MatchIndicator label="Gender" matched={match.matched_on.gender_match} />
            {nameSimPct != null && (
              <span className="badge subcat-badge">Name similarity {nameSimPct}%</span>
            )}
          </>
        )}
      </div>

      {error && (
        <div className="error-box" role="alert">
          <span className="error-msg">{error}</span>
        </div>
      )}

      <div className="review-actions">
        <button className="review-btn approve-btn" onClick={() => submit("confirmed")} disabled={submitting}>
          {submitting ? <span className="spinner" /> : "Confirm duplicate"}
        </button>
        <button className="review-btn reject-btn" onClick={() => submit("rejected")} disabled={submitting}>
          Reject match
        </button>
      </div>
    </div>
  );
}

function DuplicateReviewTab() {
  const [matches, setMatches] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getPatientMatches()
      .then(setMatches)
      .catch((err) => setError(err.message || "Failed to load duplicate queue"))
      .finally(() => setLoading(false));
  }, []);

  function onResolved(matchId) {
    setMatches((prev) => prev.filter((m) => m.id !== matchId));
  }

  if (error) return <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>;
  if (loading) return <p className="no-data">Loading duplicate queue…</p>;

  // GET /patients/matches returns every pair regardless of review status;
  // this queue only shows what's still pending a decision.
  const pending = matches.filter((m) => !m.reviewed);

  return (
    <section className="data-section full-width">
      <div className="section-head">
        <h3>Potential duplicate patients</h3>
        <span className="count-chip">{pending.length}</span>
      </div>
      <div className="item-list">
        {pending.length === 0
          ? <p className="no-data">No potential duplicates pending review.</p>
          : pending.map((m) => (
            <DuplicateReviewCard key={m.id} match={m} onResolved={onResolved} />
          ))}
      </div>
    </section>
  );
}

const TABS = [
  { key: "concepts", label: "Concept Review" },
  { key: "duplicates", label: "Duplicate Review" },
];

export default function AdminReview() {
  const [tab, setTab] = useState("concepts");

  return (
    <div className="dashboard admin-review">
      <h2 className="page-title">Admin Review</h2>
      <p className="page-subtitle">
        Human-in-the-loop queue for AI mappings below the confidence threshold, and potential-duplicate
        patient identities flagged by identity resolution. Reviewing here never re-runs classification
        or merges patient records — it only records a decision.
      </p>

      <div className="tab-bar" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            className={`tab-item${tab === t.key ? " active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="tab-panel">
        {tab === "concepts" && <ConceptReviewTab />}
        {tab === "duplicates" && <DuplicateReviewTab />}
      </div>
    </div>
  );
}
