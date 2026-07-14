"""AI-generated executive summary for a patient's semantic profile."""

import os

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from openai import AzureOpenAI
from sqlalchemy import text

from app.database import engine

load_dotenv()

router = APIRouter(tags=["ai-summary"])

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-08-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")


@router.get("/patients/{patient_id}/ai-summary")
def get_ai_summary(patient_id: str):
    """Generate a short executive summary from this patient's classified concepts."""
    with engine.connect() as conn:
        patient_row = conn.execute(text("""
            SELECT patient_id, first_name, last_name, gender FROM patients WHERE patient_id = :id
        """), {"id": patient_id}).fetchone()

        if not patient_row:
            raise HTTPException(status_code=404, detail="Patient not found")

        conditions = conn.execute(text("""
            SELECT c.condition_name, con.category, con.vocabulary_code, con.confidence
            FROM conditions c
            LEFT JOIN concepts con ON con.concept_name = c.condition_name AND con.source_type = 'condition'
            WHERE c.patient_id = :id
        """), {"id": patient_id}).fetchall()

        medications = conn.execute(text("""
            SELECT m.medication_name, con.category, con.vocabulary_code, con.confidence
            FROM medications m
            LEFT JOIN concepts con ON con.concept_name = m.medication_name AND con.source_type = 'medication'
            WHERE m.patient_id = :id
        """), {"id": patient_id}).fetchall()

        observations = conn.execute(text("""
            SELECT o.observation_name, o.observation_value, con.category, con.vocabulary_code, con.confidence
            FROM observations o
            LEFT JOIN concepts con ON con.concept_name = o.observation_name AND con.source_type = 'observation'
            WHERE o.patient_id = :id
        """), {"id": patient_id}).fetchall()

    if not conditions and not medications and not observations:
        return {
            "summary": "No classified clinical data is available yet for this patient.",
            "confidence": None,
        }

    def fmt(rows, code_label):
        lines = []
        for r in rows:
            code = f", {code_label} {r.vocabulary_code}" if r.vocabulary_code else ""
            conf = f", confidence {round(r.confidence * 100)}%" if r.confidence is not None else ""
            lines.append(f"- {r[0]} (category: {r.category or 'unclassified'}{code}{conf})")
        return "\n".join(lines) or "- none recorded"

    prompt = f"""You are a clinical informatics AI summarizing a patient's semantically
classified health record for a hospital executive audience.

Conditions:
{fmt(conditions, 'SNOMED')}

Medications:
{fmt(medications, 'RxNorm')}

Observations:
{fmt(observations, 'LOINC')}

Write a 3-4 sentence executive summary. State the patient's key conditions,
which vocabularies their diagnoses/medications/labs were mapped to, the
overall mapping confidence, and any clinically meaningful relationship
between the conditions, medications, and observations above. Do not invent
information not present above. Plain prose, no markdown, no bullet points."""

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[{"role": "user", "content": prompt}],
    )

    all_conf = [r.confidence for r in (*conditions, *medications, *observations) if r.confidence is not None]
    avg_confidence = round(sum(all_conf) / len(all_conf) * 100, 1) if all_conf else None

    return {
        "summary": response.choices[0].message.content.strip(),
        "confidence": avg_confidence,
    }
