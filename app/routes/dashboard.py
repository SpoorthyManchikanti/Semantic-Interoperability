"""Executive dashboard endpoints: summary KPIs, pipeline status, activity feed."""

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_summary():
    """Executive KPI numbers, all derived from real Neon tables."""
    with engine.connect() as conn:
        total_patients = conn.execute(text("SELECT COUNT(*) FROM patients")).scalar() or 0
        total_conditions = conn.execute(text("SELECT COUNT(*) FROM conditions")).scalar() or 0
        total_medications = conn.execute(text("SELECT COUNT(*) FROM medications")).scalar() or 0
        total_observations = conn.execute(text("SELECT COUNT(*) FROM observations")).scalar() or 0
        fhir_resources = conn.execute(text("SELECT COUNT(*) FROM ingested_files")).scalar() or 0

        total_concepts = conn.execute(text("SELECT COUNT(*) FROM concepts")).scalar() or 0
        needs_review = conn.execute(text("SELECT COUNT(*) FROM concepts WHERE needs_review = TRUE")).scalar() or 0
        with_code = conn.execute(text("SELECT COUNT(*) FROM concepts WHERE vocabulary_code IS NOT NULL")).scalar() or 0
        avg_confidence = conn.execute(text("SELECT AVG(confidence) FROM concepts")).scalar() or 0

        vocab_rows = conn.execute(text("""
            SELECT vocabulary_id, COUNT(*) as total, COUNT(vocabulary_code) as with_code
            FROM concepts
            WHERE vocabulary_id IS NOT NULL
            GROUP BY vocabulary_id
        """)).fetchall()

        relationship_count = conn.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT c1.concept_id, c2.concept_id
                FROM patient_concepts c1
                JOIN patient_concepts c2
                    ON c1.patient_id = c2.patient_id
                    AND c1.source_type = 'condition'
                    AND c2.source_type = 'medication'
                    AND c1.concept_id != c2.concept_id
            ) rels
        """)).scalar() or 0

        run_rows = conn.execute(text("""
            SELECT status, COUNT(*) FROM agent_runs GROUP BY status
        """)).fetchall()
        run_status = {row[0]: row[1] for row in run_rows}
        completed = run_status.get("completed", 0)
        failed = run_status.get("failed", 0)
        pipeline_success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else None

        failed_records = conn.execute(text(
            "SELECT COALESCE(SUM(failed_records), 0) FROM agent_runs"
        )).scalar() or 0

        standardization_rate = (with_code / total_concepts * 100) if total_concepts else 0
        interoperability_score = round((standardization_rate + (avg_confidence or 0) * 100) / 2, 1)

        return {
            "total_patients": total_patients,
            "clinical_records": total_conditions + total_medications + total_observations,
            "fhir_resources": fhir_resources,
            "interoperability_score": interoperability_score,
            "standardization_rate": round(standardization_rate, 1),
            "omop_coverage": round(standardization_rate, 1),
            "ai_classification_confidence": round((avg_confidence or 0) * 100, 1),
            "semantic_relationships": relationship_count,
            "active_concepts": total_concepts,
            "failed_resources": int(failed_records),
            "data_quality_score": round(100 - (needs_review / total_concepts * 100 if total_concepts else 0), 1),
            "pipeline_success_rate": round(pipeline_success_rate, 1) if pipeline_success_rate is not None else None,
            "needs_review": needs_review,
            "vocabulary_coverage": [
                {
                    "vocabulary_id": row[0],
                    "total": row[1],
                    "with_code": row[2],
                    "coverage_pct": round(row[2] / row[1] * 100, 1) if row[1] else 0,
                }
                for row in vocab_rows
            ],
        }


@router.get("/pipeline")
def get_pipeline():
    """Semantic interoperability lifecycle: real counts where implemented, 'planned' otherwise."""
    with engine.connect() as conn:
        fhir_resources = conn.execute(text("SELECT COUNT(*) FROM ingested_files")).scalar() or 0
        total_concepts = conn.execute(text("SELECT COUNT(*) FROM concepts")).scalar() or 0
        with_code = conn.execute(text("SELECT COUNT(*) FROM concepts WHERE vocabulary_code IS NOT NULL")).scalar() or 0

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

        stages = [
            {
                "key": "fhir_json",
                "label": "FHIR JSON",
                "records_processed": fhir_resources,
                "success_rate": 100.0 if fhir_resources else None,
                "status": "active" if fhir_resources else "planned",
            },
            {
                "key": "etl",
                "label": "ETL Pipeline",
                "records_processed": fhir_resources,
                "success_rate": 100.0 if fhir_resources else None,
                "status": "active" if fhir_resources else "planned",
            },
            {
                "key": "semantic_ai",
                "label": "Semantic Classification",
                "records_processed": processed,
                "success_rate": semantic_success_rate,
                "status": "processing" if semantic_status == "running" else ("active" if total_concepts else "planned"),
            },
            {
                "key": "concept_repository",
                "label": "Concept Repository",
                "records_processed": total_concepts,
                "success_rate": 100.0 if total_concepts else None,
                "status": "active" if total_concepts else "planned",
            },
            {
                "key": "omop_mapping",
                "label": "OMOP Ontology Mapping",
                "records_processed": with_code,
                "success_rate": round(with_code / total_concepts * 100, 1) if total_concepts else None,
                "status": "active" if with_code else "planned",
            },
            {
                "key": "knowledge_graph",
                "label": "Knowledge Graph",
                "records_processed": 0,
                "success_rate": None,
                "status": "planned",
            },
            {
                "key": "semantic_search",
                "label": "Semantic Search",
                "records_processed": 0,
                "success_rate": None,
                "status": "planned",
            },
            {
                "key": "ai_copilot",
                "label": "AI Copilot",
                "records_processed": 0,
                "success_rate": None,
                "status": "planned",
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
