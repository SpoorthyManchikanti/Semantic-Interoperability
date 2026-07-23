import KpiCard from "./KpiCard";

export default function KpiGrid({ summary }) {
  const cards = [
    {
      tag: "PT",
      label: "Total Patients",
      value: summary.total_patients,
    },
    {
      tag: "CC",
      label: "Distinct Clinical Concepts",
      value: summary.distinct_clinical_concepts,
      caption: "Unique standardized terms (conditions, medications, observations) in our vocabulary",
    },
    {
      tag: "OM",
      label: "OMOP Resolution Rate",
      value: summary.omop_resolution_rate_full,
      unit: "%",
      decimals: 1,
      caption: `${summary.omop_resolution_rate_demo_subset}% within the 15-patient demo subset vs. ${summary.omop_resolution_rate_full}% across all concepts — enrichment targeted the demo subset only`,
    },
    {
      tag: "RV",
      label: "Concepts Flagged for Review",
      value: summary.concepts_flagged_for_review,
      status: summary.concepts_flagged_for_review > 0 ? "warn" : "good",
      caption: "Concepts below the confidence threshold, pending human review",
    },
    {
      tag: "CR",
      label: "Concept Relationships Discovered",
      value: summary.concept_relationships_discovered,
      caption: "Athena/OMOP-documented clinical relationships (hierarchy, causation, association) — not simple co-occurrence",
    },
    {
      tag: "DP",
      label: "Potential Duplicate Patients Identified",
      value: summary.potential_duplicate_patients,
      caption: "Patients flagged by identity resolution as likely duplicates",
    },
  ];

  return (
    <div className="kpi-grid">
      {cards.map((c) => <KpiCard key={c.tag} {...c} />)}
    </div>
  );
}
