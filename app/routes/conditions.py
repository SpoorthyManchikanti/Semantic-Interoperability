"""Condition query endpoints."""

from fastapi import APIRouter
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/conditions", tags=["conditions"])


@router.get("/")
def list_conditions(limit: int = 50):
    """List all unique conditions in the system."""
    with engine.begin() as conn:
        result = conn.execute(
            text("""
            SELECT DISTINCT condition_name, COUNT(*) as patient_count
            FROM conditions
            GROUP BY condition_name
            ORDER BY patient_count DESC
            LIMIT :limit
            """),
            {"limit": limit}
        )
        return [dict(row._mapping) for row in result.fetchall()]


@router.get("/{condition_name}/patients")
def get_patients_with_condition(condition_name: str):
    """Get all patients with a specific condition."""
    with engine.begin() as conn:
        result = conn.execute(
            text("""
            SELECT DISTINCT p.patient_id, p.first_name, p.last_name
            FROM patients p
            JOIN conditions c ON p.patient_id = c.patient_id
            WHERE c.condition_name = :condition_name
            """),
            {"condition_name": condition_name}
        )
        return [dict(row._mapping) for row in result.fetchall()]


@router.get("/canonical/{concept_id}/variants")
def get_condition_variants(concept_id: str):
    """Get all known variants of a canonical concept."""
    # This will be populated once we build the semantic layer
    return {
        "concept_id": concept_id,
        "variants": [],
        "note": "Semantic mapping not yet implemented"
    }
