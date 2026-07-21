"""Patient identity-resolution match endpoints."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/patients", tags=["patient-matches"])


class MatchReviewRequest(BaseModel):
    decision: Literal["confirmed", "rejected"]
    reviewed_by: str


@router.get("/matches")
def list_patient_matches():
    """List all flagged potential-duplicate patient pairs, joined with both
    patients' names/DOB for readability. Flags only — never auto-merged."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                pm.id,
                pm.patient_id_1,
                p1.first_name AS patient_1_first_name,
                p1.last_name  AS patient_1_last_name,
                p1.birth_date AS patient_1_birth_date,
                pm.patient_id_2,
                p2.first_name AS patient_2_first_name,
                p2.last_name  AS patient_2_last_name,
                p2.birth_date AS patient_2_birth_date,
                pm.match_confidence,
                pm.matched_on,
                pm.reviewed,
                pm.created_at
            FROM patient_matches pm
            JOIN patients p1 ON p1.patient_id = pm.patient_id_1
            JOIN patients p2 ON p2.patient_id = pm.patient_id_2
            ORDER BY pm.match_confidence DESC
        """)).fetchall()
        return [dict(row._mapping) for row in rows]


def _select_survivor(conn, patient_id_1: str, patient_id_2: str) -> tuple[str, str]:
    """Determine (survivor_id, duplicate_id) for a confirmed match.

    Resolution order, each level only consulted if the previous one ties:
      1. Older patients.created_at wins.
      2. Tie -> higher patient_concepts row count wins (more associated
         clinical data).
      3. Tie -> alphabetically smaller patient_id wins (guarantees a
         result every time, zero ambiguity).

    Never assumes patient_id_1 is the survivor — both IDs are looked up
    and compared symmetrically."""
    created_at_rows = conn.execute(text("""
        SELECT patient_id, created_at FROM patients WHERE patient_id IN (:p1, :p2)
    """), {"p1": patient_id_1, "p2": patient_id_2}).fetchall()
    created_at = {r.patient_id: r.created_at for r in created_at_rows}

    if created_at[patient_id_1] != created_at[patient_id_2]:
        return (patient_id_1, patient_id_2) if created_at[patient_id_1] < created_at[patient_id_2] \
            else (patient_id_2, patient_id_1)

    def concept_count(pid: str) -> int:
        return conn.execute(text(
            "SELECT COUNT(*) FROM patient_concepts WHERE patient_id = :pid"
        ), {"pid": pid}).scalar()

    count_1, count_2 = concept_count(patient_id_1), concept_count(patient_id_2)

    if count_1 != count_2:
        return (patient_id_1, patient_id_2) if count_1 > count_2 else (patient_id_2, patient_id_1)

    return (patient_id_1, patient_id_2) if patient_id_1 < patient_id_2 else (patient_id_2, patient_id_1)


def _merge_patient(conn, duplicate_id: str, original_id: str, merged_at):
    """Reassign every row referencing duplicate_id over to original_id,
    across every table that has a patient_id column, then mark the
    duplicate row merged (never deleted — reversible/auditable)."""
    for table in ("conditions", "medications", "observations", "patient_concepts"):
        conn.execute(text(f"""
            UPDATE {table} SET patient_id = :original_id WHERE patient_id = :duplicate_id
        """), {"original_id": original_id, "duplicate_id": duplicate_id})

    # patient_profiles has a UNIQUE(patient_id) — the original may already
    # have its own cached AI summary, so don't clobber it if one exists.
    conn.execute(text("""
        UPDATE patient_profiles SET patient_id = :original_id
        WHERE patient_id = :duplicate_id
          AND NOT EXISTS (SELECT 1 FROM patient_profiles WHERE patient_id = :original_id)
    """), {"original_id": original_id, "duplicate_id": duplicate_id})

    conn.execute(text("""
        UPDATE patients
        SET merge_status = 'merged',
            merged_into  = :original_id,
            merged_at    = :merged_at
        WHERE patient_id = :duplicate_id
    """), {"original_id": original_id, "duplicate_id": duplicate_id, "merged_at": merged_at})


@router.patch("/matches/{match_id}/review")
def review_patient_match(match_id: int, body: MatchReviewRequest):
    """Record a human review decision for a potential-duplicate pair.
    'rejected' only writes to patient_matches. 'confirmed' additionally
    triggers a real merge: the survivor is chosen dynamically by
    _select_survivor() (older created_at, then patient_concepts count,
    then alphabetical patient_id — never assumed to be patient_id_1), every
    patient_concepts/conditions/medications/observations row belonging to
    the duplicate is reassigned to the survivor, and the duplicate is
    marked merge_status='merged' — never deleted. The whole operation is
    one transaction: if any step fails, everything rolls back, no
    half-merged state. review_decision is recorded as
    'confirmed_and_merged' in this case, distinct from a plain 'confirmed'
    review with no merge."""
    with engine.begin() as conn:
        match_row = conn.execute(text(
            "SELECT id, patient_id_1, patient_id_2 FROM patient_matches WHERE id = :id"
        ), {"id": match_id}).fetchone()
        if not match_row:
            raise HTTPException(status_code=404, detail="Match not found")

        reviewed_at = datetime.now(timezone.utc)
        recorded_decision = body.decision

        if body.decision == "confirmed":
            survivor_id, duplicate_id = _select_survivor(conn, match_row.patient_id_1, match_row.patient_id_2)
            _merge_patient(conn, duplicate_id, survivor_id, reviewed_at)
            recorded_decision = "confirmed_and_merged"

        conn.execute(text("""
            UPDATE patient_matches
            SET reviewed        = TRUE,
                review_decision = :decision,
                reviewed_by     = :reviewed_by,
                reviewed_at     = :reviewed_at
            WHERE id = :match_id
        """), {
            "decision": recorded_decision,
            "reviewed_by": body.reviewed_by,
            "reviewed_at": reviewed_at,
            "match_id": match_id,
        })

        row = conn.execute(text("""
            SELECT id, patient_id_1, patient_id_2, match_confidence,
                   reviewed, review_decision, reviewed_by, reviewed_at
            FROM patient_matches WHERE id = :match_id
        """), {"match_id": match_id}).fetchone()
        return dict(row._mapping)
