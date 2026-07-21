// Longitudinal vitals/labs (e.g. Body Height, Blood pressure panel) get one
// row per encounter in the source data, so the same concept name can appear
// dozens of times. Collapse those into a single card with an occurrence
// count instead of rendering a duplicate card per encounter.
function dedupeByName(concepts) {
  const byName = new Map();
  for (const c of concepts) {
    const existing = byName.get(c.name);
    if (existing) {
      existing.occurrences += 1;
      if (c.value != null && !existing.values.includes(c.value)) existing.values.push(c.value);
    } else {
      byName.set(c.name, { ...c, occurrences: 1, values: c.value != null ? [c.value] : [] });
    }
  }
  return [...byName.values()];
}

function SemanticCard({ concept, related, onViewOntology }) {
  const confidence = concept.confidence != null ? Math.round(concept.confidence * 100) : null;
  return (
    <div className="semantic-card">
      <div className="semantic-card-head">
        <span className="item-name">{concept.name}</span>
        {confidence != null && <span className="badge conf-badge">{confidence}%</span>}
      </div>
      <div className="semantic-card-meta">
        {concept.code && <span className="code-inline">{concept.vocabulary}: {concept.code}</span>}
        {concept.category && <span className="badge cat-badge">{concept.category}</span>}
        <span className={`badge status-badge status-${concept.status}`}>{concept.status}</span>
        {concept.occurrences > 1 && (
          <span className="badge subcat-badge">Recorded {concept.occurrences}&times;</span>
        )}
      </div>
      {concept.omopStandardName && (
        <div className="semantic-card-omop">
          <span className="omop-label">OMOP:</span>
          <span className="omop-name">{concept.omopStandardName}</span>
          {concept.omopDomain && <span className="badge omop-domain-badge">{concept.omopDomain}</span>}
        </div>
      )}
      {related.length > 0 && (
        <div className="related-concepts">
          <span className="related-label">Related concepts</span>
          <div className="related-chips">
            {related.map((r) => (
              <span key={r.id} className="badge subcat-badge">{r.name}</span>
            ))}
          </div>
        </div>
      )}
      <button className="view-ontology-btn" onClick={onViewOntology}>View ontology &#8594;</button>
    </div>
  );
}

export default function SemanticProfileTab({ concepts, onViewOntology }) {
  if (concepts.length === 0) {
    return <p className="no-data">No classified concepts for this patient yet.</p>;
  }

  const uniqueConcepts = dedupeByName(concepts);

  const byCategory = {};
  for (const c of uniqueConcepts) {
    if (!c.category) continue;
    (byCategory[c.category] ??= []).push(c);
  }

  return (
    <div className="semantic-profile-grid">
      {uniqueConcepts.map((c) => {
        const related = c.category
          ? byCategory[c.category].filter((r) => r.name !== c.name).slice(0, 3)
          : [];
        return (
          <SemanticCard key={c.id} concept={c} related={related} onViewOntology={onViewOntology} />
        );
      })}
    </div>
  );
}
