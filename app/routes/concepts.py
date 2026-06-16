"""Semantic concepts and interoperability endpoints."""

from fastapi import APIRouter
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/concepts", tags=["concepts"])


@router.get("/")
def list_concepts():
    """List all semantic concepts in the system."""
    with engine.begin() as conn:
        # Get conditions
        conditions = conn.execute(
            text("""
            SELECT DISTINCT 'condition' as type, condition_name as name
            FROM conditions
            """)
        )
        
        # Get observations
        observations = conn.execute(
            text("""
            SELECT DISTINCT 'observation' as type, observation_name as name
            FROM observations
            """)
        )
        
        # Get medications
        medications = conn.execute(
            text("""
            SELECT DISTINCT 'medication' as type, medication_name as name
            FROM medications
            """)
        )
        
        concepts = []
        for row in conditions.fetchall():
            concepts.append(dict(row._mapping))
        for row in observations.fetchall():
            concepts.append(dict(row._mapping))
        for row in medications.fetchall():
            concepts.append(dict(row._mapping))
        
        return concepts


@router.get("/profile")
def get_semantic_profile():
    """Get overall semantic profile of the dataset."""
    with engine.begin() as conn:
        patient_count = conn.execute(text("SELECT COUNT(*) FROM patients")).scalar()
        condition_count = conn.execute(text("SELECT COUNT(DISTINCT condition_name) FROM conditions")).scalar()
        observation_count = conn.execute(text("SELECT COUNT(DISTINCT observation_name) FROM observations")).scalar()
        medication_count = conn.execute(text("SELECT COUNT(DISTINCT medication_name) FROM medications")).scalar()
        
        return {
            "total_patients": patient_count,
            "unique_conditions": condition_count,
            "unique_observations": observation_count,
            "unique_medications": medication_count,
            "total_concepts": condition_count + observation_count + medication_count
        }


@router.post("/normalize")
def normalize_concept(value: str, concept_type: str):
    """Normalize a concept value to canonical form."""
    from app.semantic.normalizer import normalize_value
    
    canonical = normalize_value(value, concept_type)
    return {
        "original": value,
        "canonical": canonical,
        "concept_type": concept_type
    }
