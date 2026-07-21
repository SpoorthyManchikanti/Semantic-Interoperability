"""Per-patient exception flagging for a single patient's occurrence of a concept."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/patient-concepts", tags=["patient-concepts"])


class ExceptionFlagRequest(BaseModel):
    note: Optional[str] = None
    flagged_by: str


@router.patch("/{patient_concept_id}/exception")
def flag_exception(patient_concept_id: int, body: ExceptionFlagRequest):
    """Flag one specific patient's occurrence of a concept as an exception.

    Scoped entirely to this single patient_concepts row — never touches the
    concepts table, and never affects any other patient sharing the same
    concept_id. This is the patient-scoped counterpart to the concept-level
    Approve/Correct actions on /concepts/{concept_id}/review."""
    with engine.begin() as conn:
        existing = conn.execute(text(
            "SELECT id FROM patient_concepts WHERE id = :id"
        ), {"id": patient_concept_id}).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Patient-concept row not found")

        conn.execute(text("""
            UPDATE patient_concepts
            SET exception_flag = TRUE,
                exception_note  = :note,
                flagged_by      = :flagged_by,
                flagged_at      = :flagged_at
            WHERE id = :patient_concept_id
        """), {
            "note": body.note,
            "flagged_by": body.flagged_by,
            "flagged_at": datetime.now(timezone.utc),
            "patient_concept_id": patient_concept_id,
        })

        row = conn.execute(text("""
            SELECT id, patient_id, concept_id, exception_flag,
                   exception_note, flagged_by, flagged_at
            FROM patient_concepts WHERE id = :patient_concept_id
        """), {"patient_concept_id": patient_concept_id}).fetchone()
        return dict(row._mapping)
