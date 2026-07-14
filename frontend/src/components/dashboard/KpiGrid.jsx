import KpiCard from "./KpiCard";

export default function KpiGrid({ summary }) {
  const cards = [
    { tag: "PT", label: "Total Patients", value: summary.total_patients },
    { tag: "CR", label: "Clinical Records", value: summary.clinical_records },
    { tag: "FR", label: "FHIR Resources", value: summary.fhir_resources },
    { tag: "IO", label: "Interoperability Score", value: summary.interoperability_score, unit: "%", decimals: 1 },
    { tag: "SR", label: "Standardization Rate", value: summary.standardization_rate, unit: "%", decimals: 1 },
    { tag: "OM", label: "OMOP Coverage", value: summary.omop_coverage, unit: "%", decimals: 1 },
    { tag: "AI", label: "AI Classification Confidence", value: summary.ai_classification_confidence, unit: "%", decimals: 1 },
    { tag: "SX", label: "Semantic Relationships", value: summary.semantic_relationships },
    { tag: "AC", label: "Active Concepts", value: summary.active_concepts },
    { tag: "FX", label: "Failed Resources", value: summary.failed_resources, status: summary.failed_resources > 0 ? "warn" : "good" },
    { tag: "DQ", label: "Data Quality Score", value: summary.data_quality_score, unit: "%", decimals: 1 },
    { tag: "PS", label: "Pipeline Success Rate", value: summary.pipeline_success_rate, unit: "%", decimals: 1 },
  ];

  return (
    <div className="kpi-grid">
      {cards.map((c) => <KpiCard key={c.tag} {...c} />)}
    </div>
  );
}
