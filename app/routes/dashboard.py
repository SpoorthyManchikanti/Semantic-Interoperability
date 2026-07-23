"""Executive dashboard endpoints: summary KPIs, pipeline status, activity feed."""

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine
from app.neo4j_db import get_neo4j_session

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# DEMO CODE — the 15-patient demo subset (richest concept coverage), used
# here only to report how much better OMOP resolution looks within it vs.
# the full dataset — not a general-purpose patient filter.
DEMO_SUBSET_PATIENT_IDS = [
    "de7bdc23-9140-c119-268f-36fe8ddaab44",
    "aa305aed-7552-d253-e929-361157b3f14d",
    "299e68be-4e57-a106-3b8a-5e44df196f2a",
    "4c77f24d-765d-edf6-a7d7-bb1d14801f1b",
    "d95089e3-0388-e617-d87a-dd345033f51a",
    "ca2910b0-5032-b5de-0240-a727eaa9fd9a",
    "b2f866ed-f1b8-1c7d-81dd-311110bfd7d3",
    "2d123aa6-15c2-5d05-f04b-bb2829d724d9",
    "fb66498c-fbf8-3c71-7145-0dafa7866a37",
    "b5a8bbe2-8854-905d-af0e-4e19ca015db8",
    "5146d402-7629-2880-27b6-3203115cabb7",
    "d76fde70-5136-84a2-2721-0ea898b8683f",
    "c4fe8cf1-1b0d-710e-6976-e8183e3b7ab9",
    "ab683cb7-419f-9426-9183-a394af834440",
    "d2a30bc4-15fe-4cc8-a3ab-fbb824dbff33",
]


@router.get("/summary")
def get_summary():
    """Executive KPI numbers, all derived from real Neon tables.

    Deliberately excludes Interoperability Score (a derivative average of
    two other cards, not an independent signal), Failed Resources, and
    Pipeline Success Rate — both of the latter came from `agent_runs`, a
    4-row table from a single dev session with 2 permanently orphaned
    'running' rows, too thin to report as an executive KPI.
    """
    with engine.connect() as conn:
        total_patients = conn.execute(text("SELECT COUNT(*) FROM patients")).scalar() or 0
        fhir_resources = conn.execute(text("SELECT COUNT(*) FROM ingested_files")).scalar() or 0

        total_concepts = conn.execute(text("SELECT COUNT(*) FROM concepts")).scalar() or 0
        clinical_facts_recorded = conn.execute(text("SELECT COUNT(*) FROM patient_concepts")).scalar() or 0
        needs_review = conn.execute(text("SELECT COUNT(*) FROM concepts WHERE needs_review = TRUE")).scalar() or 0
        with_code = conn.execute(text("SELECT COUNT(*) FROM concepts WHERE vocabulary_code IS NOT NULL")).scalar() or 0
        omop_resolved = conn.execute(text("SELECT COUNT(*) FROM concepts WHERE omop_concept_id IS NOT NULL")).scalar() or 0
        avg_confidence = conn.execute(text("SELECT AVG(confidence) FROM concepts")).scalar() or 0

        demo_omop = conn.execute(text("""
            WITH demo_concepts AS (
                SELECT DISTINCT con.concept_id, con.omop_concept_id
                FROM concepts con
                JOIN patient_concepts pc ON pc.concept_id = con.concept_id
                WHERE pc.patient_id = ANY(:ids)
            )
            SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE omop_concept_id IS NOT NULL) AS resolved
            FROM demo_concepts
        """), {"ids": DEMO_SUBSET_PATIENT_IDS}).fetchone()

        concept_relationships_discovered = conn.execute(text(
            "SELECT COUNT(*) FROM concept_relationships WHERE relationship_id IS NOT NULL"
        )).scalar() or 0

        potential_duplicate_patients = conn.execute(text(
            "SELECT COUNT(*) FROM patient_matches"
        )).scalar() or 0

        vocabulary_code_presence = (with_code / total_concepts * 100) if total_concepts else 0
        omop_resolution_rate_full = (omop_resolved / total_concepts * 100) if total_concepts else 0
        omop_resolution_rate_demo_subset = (
            demo_omop.resolved / demo_omop.total * 100 if demo_omop.total else 0
        )

        return {
            "total_patients": total_patients,
            "fhir_resources": fhir_resources,
            "distinct_clinical_concepts": total_concepts,
            "clinical_facts_recorded": clinical_facts_recorded,
            "vocabulary_code_presence": round(vocabulary_code_presence, 1),
            "omop_resolution_rate_full": round(omop_resolution_rate_full, 1),
            "omop_resolution_rate_demo_subset": round(omop_resolution_rate_demo_subset, 1),
            "model_classification_confidence": round((avg_confidence or 0) * 100, 1),
            "concepts_flagged_for_review": needs_review,
            "concept_relationships_discovered": concept_relationships_discovered,
            "potential_duplicate_patients": potential_duplicate_patients,
        }


@router.get("/pipeline")
def get_pipeline():
    """Semantic interoperability lifecycle: real counts where implemented, 'planned' otherwise."""
    with engine.connect() as conn:
        fhir_resources = conn.execute(text("SELECT COUNT(*) FROM ingested_files")).scalar() or 0
        total_concepts = conn.execute(text("SELECT COUNT(*) FROM concepts")).scalar() or 0
        omop_resolved = conn.execute(text("SELECT COUNT(*) FROM concepts WHERE omop_concept_id IS NOT NULL")).scalar() or 0

        latest_run = conn.execute(text("""
            SELECT status, total_records, processed_records, failed_records
            FROM agent_runs
            ORDER BY started_at DESC
            LIMIT 1
        """)).fetchone()

        run_rows = conn.execute(text("SELECT status, COUNT(*) FROM agent_runs GROUP BY status")).fetchall()
        run_status = {row[0]: row[1] for row in run_rows}
        completed = run_status.get("completed", 0)
        failed = run_status.get("failed", 0)
        semantic_success_rate = round(completed / (completed + failed) * 100, 1) if (completed + failed) > 0 else None

        processed = latest_run.processed_records if latest_run else 0
        total_target = latest_run.total_records if latest_run else total_concepts
        semantic_status = latest_run.status if latest_run else "planned"

    with get_neo4j_session() as session:
        graph_counts = session.run("""
            MATCH (n) WITH count(n) AS nodes
            MATCH ()-[r]->() RETURN nodes, count(r) AS relationships
        """).single()
        graph_node_count = graph_counts["nodes"] if graph_counts else 0
        graph_rel_count = graph_counts["relationships"] if graph_counts else 0

    stages = [
        {
            "key": "fhir_json",
            "label": "FHIR JSON",
            "records_processed": fhir_resources,
            "success_rate": 100.0 if fhir_resources else None,
            "status": "active" if fhir_resources else "planned",
            "detail": None,
        },
        {
            "key": "etl",
            "label": "ETL Pipeline",
            "records_processed": fhir_resources,
            "success_rate": 100.0 if fhir_resources else None,
            "status": "active" if fhir_resources else "planned",
            "detail": None,
        },
        {
            "key": "semantic_ai",
            "label": "Semantic Classification",
            "records_processed": processed,
            "success_rate": semantic_success_rate,
            "status": "processing" if semantic_status == "running" else ("active" if total_concepts else "planned"),
            "detail": None,
        },
        {
            "key": "concept_repository",
            "label": "Concept Repository",
            "records_processed": total_concepts,
            "success_rate": 100.0 if total_concepts else None,
            "status": "active" if total_concepts else "planned",
            "detail": None,
        },
        {
            "key": "omop_mapping",
            "label": "OMOP Ontology Mapping",
            "records_processed": omop_resolved,
            "success_rate": round(omop_resolved / total_concepts * 100, 1) if total_concepts else None,
            "status": "active" if omop_resolved else "planned",
            "detail": None,
        },
        {
            "key": "knowledge_graph",
            "label": "Knowledge Graph",
            "records_processed": graph_rel_count,
            "success_rate": None,
            "status": "active" if graph_rel_count else "planned",
            "detail": f"{graph_node_count:,} nodes / {graph_rel_count:,} relationships (Neo4j)" if graph_rel_count else None,
        },
        {
            "key": "semantic_search",
            "label": "Semantic Search",
            "records_processed": 0,
            "success_rate": None,
            "status": "planned",
            "detail": None,
        },
        {
            "key": "ai_copilot",
            "label": "AI Copilot",
            "records_processed": 0,
            "success_rate": None,
            "status": "planned",
            "detail": None,
        },
    ]

    return {"stages": stages}


@router.get("/activity")
def get_activity(limit: int = 20):
    """Recent ETL jobs and classification runs, merged into one feed."""
    with engine.connect() as conn:
        run_rows = conn.execute(text("""
            SELECT id, agent_name, status, started_at, completed_at,
                   total_records, processed_records, failed_records
            FROM agent_runs
            ORDER BY started_at DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()

        file_rows = conn.execute(text("""
            SELECT filename, processed_at
            FROM ingested_files
            ORDER BY processed_at DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()

    events = []
    for row in run_rows:
        severity = "error" if row.status == "failed" else ("info" if row.status == "running" else "success")
        events.append({
            "type": "classification_run",
            "title": f"{row.agent_name} — {row.status}",
            "detail": f"{row.processed_records}/{row.total_records} processed"
                      + (f", {row.failed_records} failed" if row.failed_records else ""),
            "timestamp": (row.completed_at or row.started_at).isoformat(),
            "severity": severity,
        })

    for row in file_rows:
        events.append({
            "type": "fhir_import",
            "title": f"Imported {row.filename}",
            "detail": "FHIR bundle ingested",
            "timestamp": row.processed_at.isoformat() if row.processed_at else datetime.now(timezone.utc).isoformat(),
            "severity": "success",
        })

    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events[:limit]
