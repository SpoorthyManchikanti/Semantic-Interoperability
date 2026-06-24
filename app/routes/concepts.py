"""Semantic concepts endpoints."""

from fastapi import APIRouter
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/concepts", tags=["concepts"])


@router.get("/")
def list_concepts():
    """List all classified concepts."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT concept_id, concept_name, source_type, category, 
                   subcategory, confidence, vocabulary_code, vocabulary_id,
                   needs_review
            FROM concepts
            ORDER BY source_type, category, concept_name
        """)).fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/profile")
def get_semantic_profile():
    """Get overall semantic profile of the dataset."""
    with engine.connect() as conn:
        patient_count = conn.execute(text("SELECT COUNT(*) FROM patients")).scalar()
        concept_count = conn.execute(text("SELECT COUNT(*) FROM concepts")).scalar()
        needs_review = conn.execute(text("SELECT COUNT(*) FROM concepts WHERE needs_review = TRUE")).scalar()

        category_dist = conn.execute(text("""
            SELECT category, COUNT(*) as count
            FROM concepts
            GROUP BY category
            ORDER BY count DESC
        """)).fetchall()

        source_dist = conn.execute(text("""
            SELECT source_type, COUNT(*) as count
            FROM concepts
            GROUP BY source_type
        """)).fetchall()

        vocab_coverage = conn.execute(text("""
            SELECT vocabulary_id, COUNT(*) as total, COUNT(vocabulary_code) as with_code
            FROM concepts
            GROUP BY vocabulary_id
        """)).fetchall()

        return {
            "total_patients": patient_count,
            "total_concepts": concept_count,
            "needs_review": needs_review,
            "category_distribution": [dict(r._mapping) for r in category_dist],
            "source_distribution": [dict(r._mapping) for r in source_dist],
            "vocabulary_coverage": [dict(r._mapping) for r in vocab_coverage]
        }