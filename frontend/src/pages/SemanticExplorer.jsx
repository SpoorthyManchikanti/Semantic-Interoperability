import { useEffect, useState } from "react";
import { searchConcepts, getFeaturedConcepts, getConceptGraph } from "../api";
import RelationshipGraph from "../components/graph/RelationshipGraph";
import { useResizableWidth } from "../lib/useResizableWidth";
import "./SemanticExplorer.css";

const LIST_DEFAULT_WIDTH = 340;
const LIST_MIN_WIDTH = 250;
const LIST_MAX_WIDTH = 600;

// Stable reference so RelationshipGraph's useMemo doesn't see a new array
// identity on every render.
const CONCEPT_GRAPH_EXCLUDE_TYPES = ["patient"];

function ResultRow({ concept, active, onSelect }) {
  return (
    <button
      className={`explorer-result-row${active ? " active" : ""}`}
      onClick={() => onSelect(concept)}
    >
      <span className="item-name"><span className="name-text">{concept.concept_name}</span></span>
      <div className="item-badges">
        <span className="badge cat-badge">{concept.vocabulary_id}</span>
        {concept.category && <span className="badge subcat-badge">{concept.category}</span>}
        <span className="badge subcat-badge">
          {concept.patient_count} patient{concept.patient_count === 1 ? "" : "s"}
        </span>
      </div>
    </button>
  );
}

function ConceptDetailPanel({ concept }) {
  const [graphMeta, setGraphMeta] = useState(null);
  const [patientListOpen, setPatientListOpen] = useState(false);

  useEffect(() => {
    setGraphMeta(null);
    setPatientListOpen(false);
  }, [concept.concept_id]);

  const shownPatients = graphMeta ? graphMeta.nodes.filter((n) => n.type === "patient") : [];

  return (
    <div>
      <div className="explorer-detail-header">
        <h3>{concept.concept_name}</h3>
        <div className="item-badges">
          <span className="badge cat-badge">{concept.vocabulary_id}</span>
          {concept.category && <span className="badge subcat-badge">{concept.category}</span>}
          {concept.subcategory && <span className="badge subcat-badge">{concept.subcategory}</span>}
        </div>
        <p className="explorer-omop-line">
          {concept.omop_standard_name
            ? <>Maps to OMOP: <strong>{concept.omop_standard_name}</strong> ({concept.omop_domain})</>
            : "Not yet resolved to OMOP"}
        </p>
      </div>

      {graphMeta && (
        <p className="explorer-patient-count-line">
          {shownPatients.length} of {graphMeta.total_patient_count} total patient
          {graphMeta.total_patient_count === 1 ? "" : "s"} shown in graph below
        </p>
      )}

      {graphMeta && shownPatients.length > 0 && (
        <div className="explorer-patient-list">
          <button
            type="button"
            className="exception-link-btn"
            onClick={() => setPatientListOpen((open) => !open)}
          >
            {patientListOpen ? "Hide" : "Show"} patient list ({shownPatients.length})
          </button>
          {patientListOpen && (
            <div className="explorer-patient-rows">
              {shownPatients.map((p) => (
                <div key={p.id} className="explorer-patient-row">{p.name}</div>
              ))}
            </div>
          )}
        </div>
      )}

      <RelationshipGraph
        reloadKey={concept.concept_id}
        fetchGraph={() => getConceptGraph(concept.concept_id)}
        onLoaded={setGraphMeta}
        excludeNodeTypes={CONCEPT_GRAPH_EXCLUDE_TYPES}
        caption={
          <>
            This concept&rsquo;s mapping to a standard OMOP concept, and genuine clinical relationships to other
            concepts (is-a hierarchy, due-to, associated-finding, etc.) — documented in the OMOP vocabulary. Which
            patients have this concept is shown above, not as graph nodes here.
          </>
        }
        emptyMessage="No documented clinical relationships for this concept."
      />
    </div>
  );
}

export default function SemanticExplorer() {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  // Landing state (no query typed yet) — same row shape/shared components as
  // real search results, so clicking one behaves identically either way.
  const [featured, setFeatured] = useState(null);
  const [featuredError, setFeaturedError] = useState(null);

  useEffect(() => {
    getFeaturedConcepts(20)
      .then(setFeatured)
      .catch((err) => setFeaturedError(err.message || "Failed to load featured concepts"));
  }, []);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(query.trim()), 350);
    return () => clearTimeout(id);
  }, [query]);

  useEffect(() => {
    if (!debounced) {
      setResults(null);
      setError(null);
      return;
    }
    setLoading(true);
    searchConcepts(debounced)
      .then(setResults)
      .catch((err) => setError(err.message || "Search failed"))
      .finally(() => setLoading(false));
  }, [debounced]);

  const showingFeatured = !debounced;
  const listedConcepts = showingFeatured ? featured : results;

  const { width: listWidth, dividerProps } = useResizableWidth(LIST_DEFAULT_WIDTH, LIST_MIN_WIDTH, LIST_MAX_WIDTH);

  return (
    <div className="explorer-page">
      <h2 className="page-title">Semantic Explorer</h2>
      <p className="page-subtitle">
        Search clinical concepts directly — SNOMED/LOINC/RxNorm names, codes, and Athena synonyms — instead of
        starting from a patient. Select a result to see its OMOP mapping, linked patients, and relationship graph.
      </p>

      <div className="explorer-search">
        <input
          className="search-input"
          placeholder="Search concept name, code, or synonym…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
      </div>

      <div className="explorer-layout" style={{ "--list-width": `${listWidth}px` }}>
        <section className="explorer-results data-section">
          <div className="section-head">
            <h3>{showingFeatured ? "Featured concepts" : "Results"}</h3>
            {listedConcepts && <span className="count-chip">{listedConcepts.length}</span>}
          </div>
          <div className="item-list explorer-result-list">
            {showingFeatured && featuredError && (
              <div className="error-box" role="alert"><span className="error-msg">{featuredError}</span></div>
            )}
            {showingFeatured && !featured && !featuredError && <p className="no-data">Loading featured concepts…</p>}
            {loading && <p className="no-data">Searching…</p>}
            {error && <div className="error-box" role="alert"><span className="error-msg">{error}</span></div>}
            {!showingFeatured && results && results.length === 0 && (
              <p className="no-data">No concepts matched &ldquo;{debounced}&rdquo;.</p>
            )}
            {listedConcepts && listedConcepts.map((c) => (
              <ResultRow
                key={c.concept_id}
                concept={c}
                active={selected?.concept_id === c.concept_id}
                onSelect={setSelected}
              />
            ))}
          </div>
        </section>

        <div
          className="resizable-divider"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize results panel"
          tabIndex={0}
          {...dividerProps}
        />

        <section className="explorer-detail data-section">
          {!selected
            ? <p className="no-data">Select a concept from the results to see its details and relationship graph.</p>
            : <ConceptDetailPanel concept={selected} />}
        </section>
      </div>
    </div>
  );
}
