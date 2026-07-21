// Normalizes conditions/medications/observations into one flat concept list
// and derives dashboard-level stats from it. Central place so the stat row,
// concept table, and ontology graph all agree on the same shape.

export function buildConceptList(patient) {
  const conditions = patient?.conditions ?? [];
  const medications = patient?.medications ?? [];
  const observations = patient?.observations ?? [];

  const fromConditions = conditions.map((c, i) => ({
    id: `condition-${i}`,
    type: "condition",
    name: typeof c === "string" ? c : c.condition_name,
    value: null,
    code: typeof c === "object" ? c.snomed_code : null,
    vocabulary: "SNOMED",
    category: typeof c === "object" ? c.category : null,
    confidence: typeof c === "object" ? c.confidence : null,
    status: typeof c === "object" && c.status ? c.status : "mapped",
    sourceSystem: typeof c === "object" ? c.source_system ?? null : null,
    omopConceptId: typeof c === "object" ? c.omop_concept_id ?? null : null,
    omopStandardName: typeof c === "object" ? c.omop_standard_name ?? null : null,
    omopDomain: typeof c === "object" ? c.omop_domain ?? null : null,
  }));

  const fromMedications = medications.map((m, i) => ({
    id: `medication-${i}`,
    type: "medication",
    name: typeof m === "string" ? m : m.medication_name,
    value: typeof m === "object" && (m.dose || m.frequency)
      ? [m.dose, m.frequency].filter(Boolean).join(" · ")
      : null,
    code: typeof m === "object" ? m.rxnorm_code : null,
    vocabulary: "RxNorm",
    category: typeof m === "object" ? m.category : null,
    confidence: typeof m === "object" ? m.confidence : null,
    status: typeof m === "object" && m.status ? m.status : "mapped",
    sourceSystem: typeof m === "object" ? m.source_system ?? null : null,
    omopConceptId: typeof m === "object" ? m.omop_concept_id ?? null : null,
    omopStandardName: typeof m === "object" ? m.omop_standard_name ?? null : null,
    omopDomain: typeof m === "object" ? m.omop_domain ?? null : null,
  }));

  const fromObservations = observations.map((o, i) => ({
    id: `observation-${i}`,
    type: "observation",
    name: o.observation_name,
    value: o.observation_value ?? null,
    code: o.loinc_code ?? null,
    vocabulary: "LOINC",
    category: o.category ?? null,
    confidence: o.confidence ?? null,
    status: o.status ?? "mapped",
    sourceSystem: o.source_system ?? null,
    omopConceptId: o.omop_concept_id ?? null,
    omopStandardName: o.omop_standard_name ?? null,
    omopDomain: o.omop_domain ?? null,
  }));

  return [...fromConditions, ...fromMedications, ...fromObservations];
}

export function deriveStats(concepts) {
  const total = concepts.length;
  const flagged = concepts.filter((c) => c.status === "flagged");
  const mapped = concepts.filter((c) => c.status === "mapped");

  const resolutionRate = total > 0 ? (mapped.length / total) * 100 : 0;

  const avgConfidence = mapped.length > 0
    ? (mapped.reduce((sum, c) => sum + (c.confidence ?? 0), 0) / mapped.length) * 100
    : 0;

  const sourceSystems = new Set(concepts.map((c) => c.sourceSystem).filter(Boolean));
  // Falls back to 1 when no concept carries a source_system (e.g. hitting the
  // real /patients/{id} DB router today, which doesn't return that field yet).
  const sourceSystemCount = sourceSystems.size > 0 ? sourceSystems.size : (total > 0 ? 1 : 0);

  return {
    total,
    resolutionRate,
    flaggedCount: flagged.length,
    avgConfidence,
    sourceSystemCount,
  };
}
