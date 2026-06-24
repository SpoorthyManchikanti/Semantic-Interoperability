"""Condition query endpoints."""

from fastapi import APIRouter
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/conditions", tags=["conditions"])


@router.get("/")
def list_conditions(limit: int = 50):
    """List all unique conditions with patient counts and OMOP codes."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                c.concept_name as condition_name,
                c.category,
                c.subcategory,
                c.vocabulary_code as snomed_code,
                c.confidence,
                COUNT(DISTINCT pc.patient_id) as patient_count
            FROM concepts c
            JOIN patient_concepts pc ON c.concept_id = pc.concept_id
            WHERE c.source_type = 'condition'
            GROUP BY c.concept_id, c.concept_name, c.category, c.subcategory, c.vocabulary_code, c.confidence
            ORDER BY patient_count DESC
            LIMIT :limit
        """), {"limit": limit})
        return [dict(row._mapping) for row in result.fetchall()]


@router.get("/{condition_name}/patients")
def get_patients_with_condition(condition_name: str):
    """Get all patients with a specific condition."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT DISTINCT p.patient_id, p.first_name, p.last_name, p.gender
            FROM patients p
            JOIN conditions c ON p.patient_id = c.patient_id
            WHERE c.condition_name = :condition_name
        """), {"condition_name": condition_name})
        return [dict(row._mapping) for row in result.fetchall()]