import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  getNeedsReviewConcepts,
  reviewConcept,
  flagPatientConceptException,
  getPatientMatches,
  reviewPatientMatch,
  getVocabularyMismatches,
  reviewVocabularyMismatch,
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

  // Independent filters — patient-deep-link (from the URL, e.g. arriving via
  // Patient Detail's "N concepts pending review" callout), free-text concept
  // name search, category dropdown, and a confidence % range. All combine
  // with AND, so e.g. a patient deep-link plus a search term narrows further.
  const [searchParams, setSearchParams] = useSearchParams();
  const patientFilterId = searchParams.get("patient");
  const [searchText, setSearchText] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [confidenceMin, setConfidenceMin] = useState(0);
  const [confidenceMax, setConfidenceMax] = useState(100);

  function clearPatientFilter() {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("patient");
      return next;
    });
  }

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

  // Distinct categories actually present in the queue right now — options
  // are always drawn from the full unfiltered `groups`, not the narrowed
  // result, so picking a category never removes other categories from the
  // dropdown out from under the user.
  const categories = useMemo(() => {
    return [...new Set(groups.map((g) => g.category).filter(Boolean))].sort();
  }, [groups]);

  // Resolved from the queue data itself (no extra API call) — the first
  // matching patient's name found across any group.
  const patientFilterName = useMemo(() => {
    if (!patientFilterId) return null;
    for (const g of groups) {
      const match = g.patients.find((p) => p.patient_id === patientFilterId);
      if (match) return `${match.patient_first_name} ${match.patient_last_name}`;
    }
    return null;
  }, [groups, patientFilterId]);

  // All filters combine with AND.
  const filteredGroups = useMemo(() => {
    const term = searchText.trim().toLowerCase();
    return groups.filter((g) => {
      if (patientFilterId && !g.patients.some((p) => p.patient_id === patientFilterId)) return false;
      if (term && !g.concept_name.toLowerCase().includes(term)) return false;
      if (categoryFilter && g.category !== categoryFilter) return false;
      if (g.confidence != null) {
        const pct = g.confidence * 100;
        if (pct < confidenceMin || pct > confidenceMax) return false;
      }
      return true;
    });
  }, [groups, patientFilterId, searchText, categoryFilter, confidenceMin, confidenceMax]);

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
        <span className="count-chip">Showing {filteredGroups.length} of {groups.length} concepts</span>
      </div>
      {exceptionCount > 0 && (
        <p className="no-data exception-summary">
          {exceptionCount} flagged as patient-specific exceptions
        </p>
      )}

      {patientFilterId && (
        <div className="concept-patient-filter-banner">
          <span>Showing concepts for <strong>{patientFilterName || "selected patient"}</strong></span>
          <button type="button" className="exception-link-btn" onClick={clearPatientFilter}>
            Clear filter
          </button>
        </div>
      )}

      <div className="concept-filter-bar">
        <input
          type="text"
          className="search-input concept-filter-search"
          placeholder="Search concept name..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
        <select
          className="concept-filter-select"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <div className="concept-filter-confidence">
          <label>
            Min confidence
            <input
              type="number"
              min={0}
              max={100}
              value={confidenceMin}
              onChange={(e) => setConfidenceMin(Number(e.target.value))}
            />
          </label>
          <span className="concept-filter-confidence-sep">–</span>
          <label>
            Max confidence
            <input
              type="number"
              min={0}
              max={100}
              value={confidenceMax}
              onChange={(e) => setConfidenceMax(Number(e.target.value))}
            />
          </label>
        </div>
      </div>

      <div className="item-list">
        {filteredGroups.length === 0
          ? (
            <p className="no-data">
              {groups.length === 0
                ? "No concepts pending review — queue is empty."
                : "No concepts match the current filters."}
            </p>
          )
          : filteredGroups.map((g) => (
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

function DataQualityCard({ item, highlighted, onResolved }) {
  const [correcting, setCorrecting] = useState(false);
  const [vocabularyId, setVocabularyId] = useState(item.vocabulary_id ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function submitAcknowledge() {
    setSubmitting(true);
    setError(null);
    try {
      await reviewVocabularyMismatch(item.concept_id, { decision: "acknowledged", reviewed_by: REVIEWED_BY });
      onResolved(item.concept_id);
    } catch (err) {
      setError(err.message || "Failed to acknowledge");
      setSubmitting(false);
    }
  }

  async function submitCorrection(e) {
    e.preventDefault();
    if (!vocabularyId.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await reviewVocabularyMismatch(item.concept_id, {
        decision: "corrected",
        corrected_vocabulary_id: vocabularyId.trim(),
        reviewed_by: REVIEWED_BY,
      });
      onResolved(item.concept_id);
    } catch (err) {
      setError(err.message || "Failed to submit correction");
      setSubmitting(false);
    }
  }

  return (
    <div
      id={`concept-${item.concept_id}`}
      className={`item-card review-card${highlighted ? " dq-card-highlighted" : ""}`}
    >
      <div className="review-card-head">
        <span className="item-name"><span className="name-text">{item.concept_name}</span></span>
      </div>

      <div className="item-badges">
        <span className="badge cat-badge">{item.vocabulary_id}: {item.vocabulary_code}</span>
        <span className="badge subcat-badge">
          Affects {item.affected_patient_count} patient{item.affected_patient_count === 1 ? "" : "s"}
        </span>
      </div>

      <p className="dq-reason">{item.reason}</p>

      {error && (
        <div className="error-box" role="alert">
          <span className="error-msg">{error}</span>
        </div>
      )}

      {!correcting ? (
        <div className="review-actions">
          <button className="review-btn approve-btn" onClick={submitAcknowledge} disabled={submitting}>
            {submitting ? <span className="spinner" /> : "Acknowledge — known issue"}
          </button>
          <button className="review-btn correct-btn" onClick={() => setCorrecting(true)} disabled={submitting}>
            Correct vocabulary tag
          </button>
        </div>
      ) : (
        <form className="correction-form" onSubmit={submitCorrection}>
          <label className="correction-field">
            Correct vocabulary_id
            <input
              value={vocabularyId}
              onChange={(e) => setVocabularyId(e.target.value)}
              disabled={submitting}
              autoFocus
            />
          </label>
          <div className="review-actions">
            <button type="submit" className="review-btn approve-btn" disabled={submitting || !vocabularyId.trim()}>
              {submitting ? <span className="spinner" /> : "Submit correction"}
            </button>
            <button
              type="button"
              className="review-btn skip-btn"
              onClick={() => setCorrecting(false)}
              disabled={submitting}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function DataQualityReviewTab({ highlightConceptId }) {
  const [items, setItems] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getVocabularyMismatches()
      .then(setItems)
      .catch((err) => setError(err.message || "Failed to load data quality queue"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!highlightConceptId || !items) return;
    const el = document.getElementById(`concept-${highlightConceptId}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightConceptId, items]);

  function onResolved(conceptId) {
    setItems((prev) => prev.filter((i) => i.concept_id !== conceptId));
  }

  if (error) return <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>;
  if (loading) return <p className="no-data">Loading data quality queue…</p>;

  return (
    <section className="data-section full-width">
      <div className="section-head">
        <h3>Vocabulary mismatches</h3>
        <span className="count-chip">{items.length}</span>
      </div>
      <p className="no-data" style={{ marginBottom: 12 }}>
        Concepts where the source code doesn&rsquo;t match its assigned vocabulary under Athena — separate from
        the needs_review queue in Concept Review; reviewing here never touches that flag.
      </p>
      <div className="item-list">
        {items.length === 0
          ? <p className="no-data">No vocabulary mismatches pending review.</p>
          : items.map((item) => (
            <DataQualityCard
              key={item.concept_id}
              item={item}
              highlighted={item.concept_id === highlightConceptId}
              onResolved={onResolved}
            />
          ))}
      </div>
    </section>
  );
}

const TABS = [
  { key: "concept-review", label: "Concept Review" },
  { key: "duplicates", label: "Duplicate Review" },
  { key: "data-quality", label: "Data Quality Review" },
];

export default function AdminReview() {
  const [searchParams] = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const highlightConceptId = searchParams.get("concept");
  const [tab, setTab] = useState(
    TABS.some((t) => t.key === requestedTab) ? requestedTab : "concept-review"
  );

  return (
    <div className="dashboard admin-review">
      <h2 className="page-title">Admin Review</h2>
      <p className="page-subtitle">
        Human-in-the-loop queue for AI mappings below the confidence threshold, potential-duplicate patients
        flagged by identity resolution, and vocabulary mismatches found during OMOP standardization.
        Corrections preserve the original AI decision alongside any human override; confirming a duplicate
        performs a real, auditable merge — never a silent overwrite.
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
        {tab === "concept-review" && <ConceptReviewTab />}
        {tab === "duplicates" && <DuplicateReviewTab />}
        {tab === "data-quality" && <DataQualityReviewTab highlightConceptId={highlightConceptId} />}
      </div>
    </div>
  );
}
