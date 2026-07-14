"""Knowledge graph endpoints: dataset-wide preview and per-patient relationships.

Edges are derived from real co-occurrence in `patient_concepts` (concepts that
appear together for the same patient), not from the Athena/OMOP vocabulary CSVs.
"""

from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine

router = APIRouter(tags=["graph"])


def _co_occurrence_edges(conn, patient_filter: str | None, params: dict, limit: int):
    """Shared query: concept pairs that co-occur for the same patient(s)."""
    patient_clause = "AND pc1.patient_id = :patient_id" if patient_filter else ""
    rows = conn.execute(text(f"""
        SELECT DISTINCT
            c1.concept_id as source_id, c1.concept_name as source_name, c1.source_type as source_type,
            c2.concept_id as target_id, c2.concept_name as target_name, c2.source_type as target_type
        FROM patient_concepts pc1
        JOIN patient_concepts pc2
            ON pc1.patient_id = pc2.patient_id
            AND pc1.concept_id != pc2.concept_id
        JOIN concepts c1 ON c1.concept_id = pc1.concept_id
        JOIN concepts c2 ON c2.concept_id = pc2.concept_id
        WHERE pc1.source_type < pc2.source_type
        {patient_clause}
        LIMIT :limit
    """), {**params, "limit": limit}).fetchall()
    return rows


def _relationship_type(source_type: str, target_type: str) -> str:
    pair = {source_type, target_type}
    if pair == {"condition", "medication"}:
        return "treated_by"
    if pair == {"condition", "observation"}:
        return "measured_by"
    if pair == {"medication", "observation"}:
        return "monitored_by"
    return "related_to"


@router.get("/graph/preview")
def get_graph_preview(limit: int = 40):
    """Dataset-wide sample subgraph for the dashboard knowledge graph preview."""
    with engine.connect() as conn:
        edge_rows = _co_occurrence_edges(conn, None, {}, limit)

        nodes = {}
        edges = []
        for row in edge_rows:
            nodes[row.source_id] = {"id": row.source_id, "name": row.source_name, "type": row.source_type}
            nodes[row.target_id] = {"id": row.target_id, "name": row.target_name, "type": row.target_type}
            edges.append({
                "source": row.source_id,
                "target": row.target_id,
                "relationship": _relationship_type(row.source_type, row.target_type),
            })

        return {"nodes": list(nodes.values()), "edges": edges}


@router.get("/patients/{patient_id}/relationships")
def get_patient_relationships(patient_id: str):
    """Real co-occurrence relationships between this patient's classified concepts."""
    with engine.connect() as conn:
        edge_rows = _co_occurrence_edges(conn, patient_id, {"patient_id": patient_id}, limit=200)

        nodes = {}
        edges = []
        for row in edge_rows:
            nodes[row.source_id] = {"id": row.source_id, "name": row.source_name, "type": row.source_type}
            nodes[row.target_id] = {"id": row.target_id, "name": row.target_name, "type": row.target_type}
            edges.append({
                "source": row.source_id,
                "target": row.target_id,
                "relationship": _relationship_type(row.source_type, row.target_type),
            })

        return {"nodes": list(nodes.values()), "edges": edges}
