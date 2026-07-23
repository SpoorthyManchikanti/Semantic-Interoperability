"""Patient query endpoints."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.database import engine
from app.routes.concepts import DEMO_SUBSET_PATIENT_IDS
from scripts.load_to_neo4j import SYNTHETIC_CLONE_IDS

router = APIRouter(prefix="/patients", tags=["patients"])


def _demo_subset_ids():
    """Live union of the two existing demo-subset sources — never a
    hardcoded list of our own: concepts.py's DEMO_SUBSET_PATIENT_IDS (the
    15 original demo patients + anyone appended by register_ingested_patient
    on a real /ingest run — the exact same list Admin Review filters on)
    plus load_to_neo4j.py's SYNTHETIC_CLONE_IDS (the 3 synthetic duplicate
    patients, tracked separately since they exist only for the identity-
    resolution demo). Both are references to live module-level objects, so
    this reflects additions to either immediately, with no snapshot/cache."""
    return list(DEMO_SUBSET_PATIENT_IDS) + list(SYNTHETIC_CLONE_IDS)


@router.get("/demo-subset")
def list_demo_subset_patients():
    """Patients to pin at the top of Patient Search's default (no-query)
    list — see _demo_subset_ids() for what's included and why."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT patient_id, first_name, last_name, gender, birth_date
            FROM patients
            WHERE patient_id = ANY(:ids)
            ORDER BY last_name, first_name
        """), {"ids": _demo_subset_ids()}).fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/")
def list_patients(limit: int = 10, offset: int = 0, exclude_demo_subset: bool = False):
    """List all patients. exclude_demo_subset=True drops anyone returned by
    GET /patients/demo-subset, so Patient Search's default view can show
    the pinned demo section and the "All Patients" section below it with
    no overlap."""
    with engine.connect() as conn:
        if exclude_demo_subset:
            result = conn.execute(text("""
                SELECT patient_id, first_name, last_name, gender, birth_date
                FROM patients
                WHERE patient_id != ALL(:ids)
                ORDER BY last_name, first_name
                LIMIT :limit OFFSET :offset
            """), {"ids": _demo_subset_ids(), "limit": limit, "offset": offset})
        else:
            result = conn.execute(text("""
                SELECT patient_id, first_name, last_name, gender, birth_date
                FROM patients
                ORDER BY last_name, first_name
                LIMIT :limit OFFSET :offset
            """), {"limit": limit, "offset": offset})
        return [dict(row._mapping) for row in result.fetchall()]


@router.get("/search")
def search_patients(q: str = None, first_name: str = None, last_name: str = None):
    """Search patients. `q` does a wildcard match across first name, last
    name, and patient ID; `first_name`/`last_name` filter individually.
    All matches are ILIKE (partial, case-insensitive), never exact."""
    with engine.connect() as conn:
        query = "SELECT patient_id, first_name, last_name, gender, birth_date FROM patients WHERE 1=1"
        params = {}
        if q:
            query += """ AND (
                first_name ILIKE :q
                OR last_name ILIKE :q
                OR (first_name || ' ' || last_name) ILIKE :q
                OR patient_id ILIKE :q
            )"""
            params["q"] = f"%{q}%"
        if first_name:
            query += " AND first_name ILIKE :first_name"
            params["first_name"] = f"%{first_name}%"
        if last_name:
            query += " AND last_name ILIKE :last_name"
            params["last_name"] = f"%{last_name}%"
        query += " LIMIT 25"
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result.fetchall()]


@router.get("/data-source-summary")
def get_data_source_summary():
    """Real breakdown of patients.data_source — a live query, not a
    hardcoded label. Used by pages that aren't tied to one patient
    (Dashboard, Ontology Browser) to show provenance in aggregate."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT data_source, COUNT(*) as count
            FROM patients
            GROUP BY data_source
            ORDER BY count DESC
        """)).fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/{patient_id}")
def get_patient(patient_id: str):
    """Get complete patient profile with classified concepts."""
    with engine.connect() as conn:
        patient_row = conn.execute(text("""
            SELECT patient_id, first_name, last_name, gender, birth_date, data_source,
                   merge_status, merged_into, merged_at
            FROM patients WHERE patient_id = :id
        """), {"id": patient_id}).fetchone()

        if not patient_row:
            raise HTTPException(status_code=404, detail="Patient not found")

        patient = dict(patient_row._mapping)

        # A merged-away record has no clinical data left under its own
        # patient_id (it was reassigned to merged_into) — return its merge
        # status plainly instead of a misleading "no conditions/medications
        # /observations" active-patient response.
        if patient["merge_status"] == "merged":
            return patient

        # Get conditions with concept classifications
        conditions = conn.execute(text("""
            SELECT c.condition_name, con.category, con.subcategory,
                   con.vocabulary_code as snomed_code, con.confidence,
                   con.omop_concept_id, con.omop_standard_name, con.omop_domain
            FROM conditions c
            LEFT JOIN concepts con ON con.concept_name = c.condition_name
                AND con.source_type = 'condition'
            WHERE c.patient_id = :id
        """), {"id": patient_id}).fetchall()

        # Get observations with concept classifications
        observations = conn.execute(text("""
            SELECT o.observation_name, o.observation_value,
                   con.category, con.subcategory,
                   con.vocabulary_code as loinc_code, con.confidence,
                   con.omop_concept_id, con.omop_standard_name, con.omop_domain
            FROM observations o
            LEFT JOIN concepts con ON con.concept_name = o.observation_name
                AND con.source_type = 'observation'
            WHERE o.patient_id = :id
        """), {"id": patient_id}).fetchall()

        # Get medications with concept classifications
        medications = conn.execute(text("""
            SELECT m.medication_name, con.category, con.subcategory,
                   con.vocabulary_code as rxnorm_code, con.confidence,
                   con.omop_concept_id, con.omop_standard_name, con.omop_domain
            FROM medications m
            LEFT JOIN concepts con ON con.concept_name = m.medication_name
                AND con.source_type = 'medication'
            WHERE m.patient_id = :id
        """), {"id": patient_id}).fetchall()

        patient["conditions"] = [dict(r._mapping) for r in conditions]
        patient["observations"] = [dict(r._mapping) for r in observations]
        patient["medications"] = [dict(r._mapping) for r in medications]

        return patient


@router.get("/{patient_id}/concepts")
def get_patient_concepts(patient_id: str):
    """Get all classified concepts for a patient."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT con.concept_id, con.concept_name, con.source_type,
                   con.category, con.subcategory, con.vocabulary_code,
                   con.vocabulary_id, con.confidence, con.needs_review,
                   con.classified_at, con.updated_at
            FROM patient_concepts pc
            JOIN concepts con ON con.concept_id = pc.concept_id
            WHERE pc.patient_id = :id
            ORDER BY con.classified_at NULLS LAST, con.source_type, con.category
        """), {"id": patient_id}).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="Patient not found or has no concepts")

        return [dict(r._mapping) for r in rows]


@router.get("/{patient_id}/concept-relationships")
def get_patient_concept_relationships(patient_id: str):
    """Real Athena/OMOP relationships where both ends are this patient's own
    OMOP-resolved concepts (populated by scripts/populate_concept_relationships.py).
    Read-only. Returns an empty list for a patient with no populated rows —
    not a 404, since having zero internal relationships is a legitimate
    outcome (e.g. Jesus702 Dietrich576 has none)."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT concept_id_1, concept_1_name, relationship_id,
                   concept_id_2, concept_2_name
            FROM concept_relationships
            WHERE patient_id = :id
            ORDER BY concept_1_name, relationship_id
        """), {"id": patient_id}).fetchall()
        return [dict(r._mapping) for r in rows]