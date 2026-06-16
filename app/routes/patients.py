"""Patient query endpoints."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.database import engine
from app.semantic.schemas import PatientProfile, PatientCondition, PatientObservation, PatientMedication

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/")
def list_patients(limit: int = 10, offset: int = 0):
    """List all patients."""
    with engine.begin() as conn:
        result = conn.execute(
            text("""
            SELECT patient_id, first_name, last_name, gender
            FROM patients
            LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset}
        )
        patients = result.fetchall()
        return [dict(row._mapping) for row in patients]


@router.get("/{patient_id}")
def get_patient(patient_id: str):
    """Get complete patient profile with conditions, observations, medications."""
    with engine.begin() as conn:
        # Get patient
        patient_result = conn.execute(
            text("SELECT * FROM patients WHERE patient_id = :id"),
            {"id": patient_id}
        )
        patient_row = patient_result.fetchone()
        
        if not patient_row:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        patient = dict(patient_row._mapping)
        
        # Get conditions
        conditions_result = conn.execute(
            text("""
            SELECT id, condition_name 
            FROM conditions WHERE patient_id = :id
            """),
            {"id": patient_id}
        )
        conditions = [
            {"condition_id": row.id, "condition_name": row.condition_name, "canonical_concept": None}
            for row in conditions_result.fetchall()
        ]
        
        # Get observations
        observations_result = conn.execute(
            text("""
            SELECT id, observation_name, value 
            FROM observations WHERE patient_id = :id
            """),
            {"id": patient_id}
        )
        observations = [
            {
                "observation_id": row.id,
                "observation_name": row.observation_name,
                "observation_value": row.value,
                "canonical_concept": None
            }
            for row in observations_result.fetchall()
        ]
        
        # Get medications
        medications_result = conn.execute(
            text("""
            SELECT id, medication_name 
            FROM medications WHERE patient_id = :id
            """),
            {"id": patient_id}
        )
        medications = [
            {"medication_id": row.id, "medication_name": row.medication_name, "canonical_concept": None}
            for row in medications_result.fetchall()
        ]
        
        patient["conditions"] = conditions
        patient["observations"] = observations
        patient["medications"] = medications
        
        return patient


@router.get("/search/")
def search_patients(first_name: str = None, last_name: str = None):
    """Search patients by name."""
    with engine.begin() as conn:
        query = "SELECT * FROM patients WHERE 1=1"
        params = {}
        
        if first_name:
            query += " AND first_name ILIKE :first_name"
            params["first_name"] = f"%{first_name}%"
        
        if last_name:
            query += " AND last_name ILIKE :last_name"
            params["last_name"] = f"%{last_name}%"
        
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result.fetchall()]
