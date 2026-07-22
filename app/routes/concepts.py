"""Semantic concepts endpoints."""

from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/concepts", tags=["concepts"])


class ConceptReviewRequest(BaseModel):
    decision: Literal["approved", "corrected"]
    corrected_category: Optional[str] = None
    corrected_subcategory: Optional[str] = None
    reviewed_by: str
    patient_concept_ids: Optional[List[int]] = None

# DEMO CODE — hardcoded to the 15-patient demo subset selected for the
# richest concept coverage; not a general-purpose patient filter.
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


# DEMO CODE — filters to the hardcoded demo subset above rather than all patients.
@router.get("/needs-review")
def list_needs_review_concepts():
    """List concepts flagged needs_review=True for the demo subset of 15
    patients, joined with patient name, category, subcategory, and
    confidence. Excludes the 'Unknown' fallback (category='General',
    subcategory='Unknown / Invalid Concept') — that's missing source
    data, not genuine classification ambiguity. Read-only — no
    reprocessing, no Agent 1 changes.

    Respects per-row approval: a patient's row drops out as soon as their
    own patient_concepts.review_decision is set (via the patient_concept_ids
    path on PATCH /concepts/{id}/review), even while concepts.needs_review
    is still true and sibling patients remain pending. The concept only
    fully disappears once every linked patient's row is resolved — at that
    point concepts.needs_review is normally also false (set by the
    concept-level path), which already excludes it via the first WHERE
    clause; pc.review_decision IS NULL is what makes per-patient dropout
    work independently of that."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                pc.id AS patient_concept_id,
                con.concept_id,
                con.concept_name,
                con.source_type,
                con.category,
                con.subcategory,
                con.confidence,
                pc.patient_id,
                p.first_name AS patient_first_name,
                p.last_name  AS patient_last_name
            FROM concepts con
            JOIN patient_concepts pc ON pc.concept_id = con.concept_id
            JOIN patients p ON p.patient_id = pc.patient_id
            WHERE con.needs_review = TRUE
              AND pc.patient_id = ANY(:patient_ids)
              AND pc.review_decision IS NULL
              AND NOT (con.category = 'General' AND con.subcategory = 'Unknown / Invalid Concept')
            ORDER BY con.confidence ASC, p.last_name, p.first_name
        """), {"patient_ids": DEMO_SUBSET_PATIENT_IDS}).fetchall()
        return [dict(row._mapping) for row in rows]


@router.patch("/{concept_id}/review")
def review_concept(concept_id: str, body: ConceptReviewRequest):
    """Record a human review decision for a concept.

    Two modes, chosen by whether patient_concept_ids is provided:

    - Omitted (default, unchanged behavior): writes to `concepts` —
      needs_review/review_decision/reviewed_by/reviewed_at/human_corrected_*
      — which has one row per concept_id shared across every patient who
      has it. Affects every patient sharing that concept at once.

    - Provided: writes the same review fields onto only the given
      patient_concepts rows (validated to belong to this concept_id),
      leaving every other patient's row — and the concepts table itself —
      untouched. Different patients can end up with different review
      outcomes for the same concept this way. Note: concepts.needs_review
      is not touched in this mode, so GET /concepts/needs-review will keep
      listing the still-pending patient rows for this concept until every
      patient sharing it has been reviewed (there's no automatic concept-
      level rollup yet)."""
    with engine.begin() as conn:
        existing = conn.execute(text(
            "SELECT concept_id FROM concepts WHERE concept_id = :id"
        ), {"id": concept_id}).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Concept not found")

        reviewed_at = datetime.now(timezone.utc)

        if body.patient_concept_ids is not None:
            matched = conn.execute(text("""
                SELECT id FROM patient_concepts
                WHERE concept_id = :concept_id AND id = ANY(:ids)
            """), {"concept_id": concept_id, "ids": body.patient_concept_ids}).fetchall()
            matched_ids = {r.id for r in matched}
            missing_ids = set(body.patient_concept_ids) - matched_ids
            if missing_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"patient_concept_ids not linked to concept {concept_id}: {sorted(missing_ids)}",
                )

            conn.execute(text("""
                UPDATE patient_concepts
                SET review_decision             = :decision,
                    reviewed_by                 = :reviewed_by,
                    reviewed_at                 = :reviewed_at,
                    human_corrected_category    = CASE WHEN :decision = 'corrected'
                        THEN COALESCE(:corrected_category, human_corrected_category)
                        ELSE human_corrected_category END,
                    human_corrected_subcategory = CASE WHEN :decision = 'corrected'
                        THEN COALESCE(:corrected_subcategory, human_corrected_subcategory)
                        ELSE human_corrected_subcategory END
                WHERE id = ANY(:ids)
            """), {
                "decision": body.decision,
                "reviewed_by": body.reviewed_by,
                "reviewed_at": reviewed_at,
                "corrected_category": body.corrected_category,
                "corrected_subcategory": body.corrected_subcategory,
                "ids": body.patient_concept_ids,
            })

            rows = conn.execute(text("""
                SELECT id AS patient_concept_id, patient_id, review_decision,
                       reviewed_by, reviewed_at, human_corrected_category,
                       human_corrected_subcategory
                FROM patient_concepts WHERE id = ANY(:ids)
                ORDER BY id
            """), {"ids": body.patient_concept_ids}).fetchall()
            return {
                "concept_id": concept_id,
                "scope": "patient_concept_ids",
                "updated_rows": [dict(r._mapping) for r in rows],
            }

        if body.decision == "approved":
            conn.execute(text("""
                UPDATE concepts
                SET needs_review    = FALSE,
                    review_decision = :decision,
                    reviewed_by     = :reviewed_by,
                    reviewed_at     = :reviewed_at
                WHERE concept_id = :concept_id
            """), {
                "decision": body.decision,
                "reviewed_by": body.reviewed_by,
                "reviewed_at": reviewed_at,
                "concept_id": concept_id,
            })
        else:  # corrected
            conn.execute(text("""
                UPDATE concepts
                SET needs_review               = FALSE,
                    review_decision             = :decision,
                    reviewed_by                 = :reviewed_by,
                    reviewed_at                 = :reviewed_at,
                    human_corrected_category    = COALESCE(:corrected_category, human_corrected_category),
                    human_corrected_subcategory = COALESCE(:corrected_subcategory, human_corrected_subcategory)
                WHERE concept_id = :concept_id
            """), {
                "decision": body.decision,
                "reviewed_by": body.reviewed_by,
                "reviewed_at": reviewed_at,
                "corrected_category": body.corrected_category,
                "corrected_subcategory": body.corrected_subcategory,
                "concept_id": concept_id,
            })

        row = conn.execute(text("""
            SELECT concept_id, concept_name, category, subcategory,
                   human_corrected_category, human_corrected_subcategory,
                   needs_review, review_decision, reviewed_by, reviewed_at
            FROM concepts WHERE concept_id = :concept_id
        """), {"concept_id": concept_id}).fetchone()
        return {"scope": "concept", **dict(row._mapping)}


# DEMO CODE — filters to the hardcoded demo subset above rather than all patients.
@router.get("/omop-resolution")
def get_omop_resolution():
    """OMOP/Athena cross-reference resolution summary for the demo subset of
    15 patients: total concepts, resolved count/percentage, breakdown by
    source_type, and full detail on the concepts that didn't resolve
    (vocabulary_mismatch=true rows and the Unknown fallback). Read-only."""
    with engine.connect() as conn:
        totals = conn.execute(text("""
            WITH demo_concepts AS (
                SELECT DISTINCT con.concept_id, con.omop_concept_id
                FROM concepts con
                JOIN patient_concepts pc ON pc.concept_id = con.concept_id
                WHERE pc.patient_id = ANY(:patient_ids)
            )
            SELECT
                COUNT(*) AS total_concepts,
                COUNT(*) FILTER (WHERE omop_concept_id IS NOT NULL) AS resolved_count
            FROM demo_concepts
        """), {"patient_ids": DEMO_SUBSET_PATIENT_IDS}).fetchone()

        by_source_type = conn.execute(text("""
            WITH demo_concepts AS (
                SELECT DISTINCT con.concept_id, con.source_type, con.omop_concept_id
                FROM concepts con
                JOIN patient_concepts pc ON pc.concept_id = con.concept_id
                WHERE pc.patient_id = ANY(:patient_ids)
            )
            SELECT
                source_type,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE omop_concept_id IS NOT NULL) AS resolved,
                COUNT(*) FILTER (WHERE omop_concept_id IS NULL) AS not_resolved
            FROM demo_concepts
            GROUP BY source_type
            ORDER BY source_type
        """), {"patient_ids": DEMO_SUBSET_PATIENT_IDS}).fetchall()

        unresolved_rows = conn.execute(text("""
            SELECT
                con.concept_name,
                con.source_type,
                con.vocabulary_id,
                con.vocabulary_code,
                con.vocabulary_mismatch,
                p.patient_id,
                p.first_name AS patient_first_name,
                p.last_name  AS patient_last_name,
                CASE
                    WHEN con.vocabulary_mismatch = TRUE THEN
                        'vocabulary_code ''' || COALESCE(con.vocabulary_code, '') ||
                        ''' has no matching Athena concept under vocabulary_id ''' ||
                        COALESCE(con.vocabulary_id, '') ||
                        ''' - code and vocabulary label disagree'
                    WHEN con.vocabulary_code IS NULL THEN
                        'no vocabulary_code was assigned (source concept name was missing/invalid, classified via the Unknown fallback)'
                    ELSE 'unresolved'
                END AS reason
            FROM concepts con
            JOIN patient_concepts pc ON pc.concept_id = con.concept_id
            JOIN patients p ON p.patient_id = pc.patient_id
            WHERE pc.patient_id = ANY(:patient_ids)
              AND (con.vocabulary_mismatch = TRUE OR con.concept_name = 'Unknown')
            ORDER BY con.concept_name, p.last_name, p.first_name
        """), {"patient_ids": DEMO_SUBSET_PATIENT_IDS}).fetchall()

        total_concepts = totals.total_concepts
        resolved_count = totals.resolved_count
        resolution_percentage = round(resolved_count / total_concepts * 100, 1) if total_concepts else None

        return {
            "total_concepts": total_concepts,
            "resolved_count": resolved_count,
            "resolution_percentage": resolution_percentage,
            "breakdown_by_source_type": [dict(r._mapping) for r in by_source_type],
            "unresolved_details": [dict(r._mapping) for r in unresolved_rows],
        }


@router.get("/search")
def search_concepts(q: str):
    """Search across all 542 concepts (every patient, not just the 15-patient
    demo subset) by concept name, vocabulary_code, or Athena synonym.

    Synonym matching only fires for the 341/542 concepts that have resolved
    an omop_concept_id (the other 201 simply fall back to name/code
    matching, via the LEFT JOIN below) — extending OMOP enrichment to those
    201 is a separate, slower pipeline re-run and isn't needed for search
    coverage: every concept remains matchable by name/code regardless.
    """
    if not q or not q.strip():
        return []
    term = f"%{q.strip()}%"
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                con.concept_id,
                con.concept_name,
                con.vocabulary_id,
                con.category,
                con.subcategory,
                con.omop_standard_name,
                con.omop_domain,
                COUNT(DISTINCT pc.patient_id) AS patient_count
            FROM concepts con
            LEFT JOIN patient_concepts pc ON pc.concept_id = con.concept_id
            LEFT JOIN "Athena_Concept_Synonyms" syn ON syn.concept_id = con.omop_concept_id
            WHERE con.concept_name ILIKE :term
               OR con.vocabulary_code ILIKE :term
               OR syn.concept_synonym_name ILIKE :term
            GROUP BY con.concept_id, con.concept_name, con.vocabulary_id,
                     con.category, con.subcategory, con.omop_standard_name, con.omop_domain
            ORDER BY con.concept_name
            LIMIT 50
        """), {"term": term}).fetchall()
        return [dict(r._mapping) for r in rows]


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