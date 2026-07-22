"""Knowledge graph endpoints: dataset-wide preview and per-patient relationships.

Edges are derived from real co-occurrence in `patient_concepts` (concepts that
appear together for the same patient), not from the Athena/OMOP vocabulary CSVs.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.database import engine
from app.neo4j_db import get_neo4j_session

router = APIRouter(tags=["graph"])

# Maps the Patient->Concept relationship type stored in Neo4j back to the
# condition/medication/observation node "type" the frontend already color-codes.
CONCEPT_TYPE_BY_REL = {
    "DIAGNOSED_WITH": "condition",
    "IS_ON_MEDICATION": "medication",
    "HAS_OBSERVATION": "observation",
}


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


@router.get("/patients/{patient_id}/graph")
def get_patient_graph(patient_id: str):
    """This patient's real, Athena/OMOP-backed picture from Neo4j: their
    DIAGNOSED_WITH/IS_ON_MEDICATION/HAS_OBSERVATION concepts, each concept's
    MAPS_TO OMOP mapping, genuine clinical relationships between this
    patient's own concepts (IS_A, HAS_DUE_TO, etc. — scoped via the
    patient_id property Neo4j load put on those edges, since Concept nodes
    are shared by name across patients), and any POTENTIAL_DUPLICATE_OF
    links. Same {nodes, edges} shape as the co-occurrence endpoint above.
    """
    nodes = {}
    edges = []

    with get_neo4j_session() as session:
        patient_row = session.run("""
            MATCH (p:Patient {patient_id: $patient_id})
            RETURN p.patient_id AS patient_id, p.first_name AS first_name, p.last_name AS last_name
        """, patient_id=patient_id).single()

        if not patient_row:
            raise HTTPException(status_code=404, detail="Patient not found in graph")

        nodes[patient_id] = {
            "id": patient_id,
            "name": f"{patient_row['first_name']} {patient_row['last_name']}",
            "type": "patient",
        }

        concept_rows = session.run("""
            MATCH (p:Patient {patient_id: $patient_id})-[r]->(c:Concept)
            WHERE type(r) IN ['DIAGNOSED_WITH', 'IS_ON_MEDICATION', 'HAS_OBSERVATION']
            RETURN c.concept_id AS concept_id, c.concept_name AS concept_name, type(r) AS rel_type
        """, patient_id=patient_id).data()

        concept_ids = [row["concept_id"] for row in concept_rows]

        for row in concept_rows:
            nodes[row["concept_id"]] = {
                "id": row["concept_id"],
                "name": row["concept_name"],
                "type": CONCEPT_TYPE_BY_REL.get(row["rel_type"], "concept"),
            }
            edges.append({
                "source": patient_id,
                "target": row["concept_id"],
                "relationship": row["rel_type"].lower(),
            })

        if concept_ids:
            maps_to_rows = session.run("""
                MATCH (c:Concept)-[:MAPS_TO]->(o:OMOPConcept)
                WHERE c.concept_id IN $concept_ids
                RETURN c.concept_id AS concept_id, o.omop_concept_id AS omop_concept_id,
                       o.standard_name AS standard_name
            """, concept_ids=concept_ids).data()

            for row in maps_to_rows:
                omop_node_id = f"omop-{row['omop_concept_id']}"
                nodes[omop_node_id] = {
                    "id": omop_node_id,
                    "name": row["standard_name"],
                    "type": "omop_concept",
                }
                edges.append({
                    "source": row["concept_id"],
                    "target": omop_node_id,
                    "relationship": "maps_to",
                })

            clinical_rows = session.run("""
                MATCH (a:Concept)-[r]->(b:Concept)
                WHERE r.patient_id = $patient_id
                RETURN a.concept_id AS source_id, b.concept_id AS target_id,
                       r.relationship_id AS relationship_id
            """, patient_id=patient_id).data()

            for row in clinical_rows:
                relationship = (row["relationship_id"] or "related_to").lower().replace(" ", "_")
                edges.append({
                    "source": row["source_id"],
                    "target": row["target_id"],
                    "relationship": relationship,
                })

        duplicate_rows = session.run("""
            MATCH (p:Patient {patient_id: $patient_id})-[:POTENTIAL_DUPLICATE_OF]-(other:Patient)
            RETURN other.patient_id AS other_id, other.first_name AS first_name,
                   other.last_name AS last_name
        """, patient_id=patient_id).data()

        for row in duplicate_rows:
            nodes[row["other_id"]] = {
                "id": row["other_id"],
                "name": f"{row['first_name']} {row['last_name']}",
                "type": "patient",
            }
            edges.append({
                "source": patient_id,
                "target": row["other_id"],
                "relationship": "potential_duplicate_of",
            })

    return {"nodes": list(nodes.values()), "edges": edges}
