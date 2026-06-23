import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
import json
import time

from dotenv import load_dotenv
from sqlalchemy import text

from app.database import engine
from app.config import FHIR_FOLDER, FHIR_IS_URL

load_dotenv()

BATCH_SIZE = 100

CONDITION_MAPPING = {
    "Type II Diabetes": "Diabetes",
    "T2DM": "Diabetes",
    "Diabetes Mellitus": "Diabetes"
}

VOCABULARY_MAP = {
    "http://snomed.info/sct":                      "SNOMED",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm",
    "http://loinc.org":                            "LOINC",
}


def normalize_condition(condition):
    return CONDITION_MAPPING.get(condition, condition)


def extract_code(resource: dict, field: str = "code") -> tuple:
    """
    Extract (code, vocabulary_id) from a FHIR CodeableConcept field.
    Returns (None, None) if not found.
    """
    codings = resource.get(field, {}).get("coding", [])
    for coding in codings:
        system = coding.get("system", "")
        vocab = VOCABULARY_MAP.get(system)
        code = coding.get("code")
        if vocab and code:
            return code, vocab
    return None, None


def extract_patient_data(resource):
    patient_id = resource["id"]
    first_name = None
    last_name = None

    if resource.get("name"):
        first_name = resource["name"][0].get("given", [None])[0]
        last_name = resource["name"][0].get("family")

    return {
        "patient_id": patient_id,
        "first_name": first_name,
        "last_name": last_name,
        "gender": resource.get("gender"),
        "birth_date": resource.get("birthDate")
    }


def extract_condition_data(patient_id, resource):
    condition_name = resource.get("code", {}).get("text", "Unknown")
    condition_name = normalize_condition(condition_name)
    snomed_code, _ = extract_code(resource, "code")

    return {
        "patient_id": patient_id,
        "condition_name": condition_name,
        "snomed_code": snomed_code
    }


def extract_observation_data(patient_id, resource):
    observation_name = resource.get("code", {}).get("text", "Unknown")
    value = None
    if "valueQuantity" in resource:
        value = str(resource["valueQuantity"].get("value"))
    loinc_code, _ = extract_code(resource, "code")

    return {
        "patient_id": patient_id,
        "observation_name": observation_name,
        "observation_value": value,
        "loinc_code": loinc_code
    }


def extract_medication_data(patient_id, resource):
    medication_name = resource.get("medicationCodeableConcept", {}).get("text", "Unknown")
    rxnorm_code, _ = extract_code(resource, "medicationCodeableConcept")

    return {
        "patient_id": patient_id,
        "medication_name": medication_name,
        "rxnorm_code": rxnorm_code
    }


def batch_insert_patients(conn, patients_batch):
    if not patients_batch:
        return
    conn.execute(
        text("""
        INSERT INTO patients (patient_id, first_name, last_name, gender, birth_date)
        VALUES (:patient_id, :first_name, :last_name, :gender, :birth_date)
        ON CONFLICT (patient_id) DO NOTHING
        """),
        patients_batch
    )


def batch_insert_conditions(conn, conditions_batch):
    if not conditions_batch:
        return
    conn.execute(
        text("""
        INSERT INTO conditions (patient_id, condition_name, snomed_code)
        VALUES (:patient_id, :condition_name, :snomed_code)
        ON CONFLICT (patient_id, condition_name)
        DO UPDATE SET snomed_code = EXCLUDED.snomed_code
        """),
        conditions_batch
    )


def batch_insert_observations(conn, observations_batch):
    if not observations_batch:
        return
    conn.execute(
        text("""
        INSERT INTO observations (patient_id, observation_name, observation_value, loinc_code)
        VALUES (:patient_id, :observation_name, :observation_value, :loinc_code)
        ON CONFLICT (patient_id, observation_name, observation_value)
        DO UPDATE SET loinc_code = EXCLUDED.loinc_code
        """),
        observations_batch
    )


def batch_insert_medications(conn, medications_batch):
    if not medications_batch:
        return
    conn.execute(
        text("""
        INSERT INTO medications (patient_id, medication_name, rxnorm_code)
        VALUES (:patient_id, :medication_name, :rxnorm_code)
        ON CONFLICT (patient_id, medication_name)
        DO UPDATE SET rxnorm_code = EXCLUDED.rxnorm_code
        """),
        medications_batch
    )


def process_bundle(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    patients_batch = []
    conditions_batch = []
    observations_batch = []
    medications_batch = []

    patient_id = None

    with engine.begin() as conn:
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType")

            if resource_type == "Patient":
                patient_data = extract_patient_data(resource)
                patients_batch.append(patient_data)
                patient_id = patient_data["patient_id"]

                if len(patients_batch) >= BATCH_SIZE:
                    batch_insert_patients(conn, patients_batch)
                    patients_batch = []

            elif resource_type == "Condition" and patient_id:
                condition_data = extract_condition_data(patient_id, resource)
                conditions_batch.append(condition_data)

                if len(conditions_batch) >= BATCH_SIZE:
                    batch_insert_conditions(conn, conditions_batch)
                    conditions_batch = []

            elif resource_type == "Observation" and patient_id:
                observation_data = extract_observation_data(patient_id, resource)
                observations_batch.append(observation_data)

                if len(observations_batch) >= BATCH_SIZE:
                    batch_insert_observations(conn, observations_batch)
                    observations_batch = []

            elif resource_type == "MedicationRequest" and patient_id:
                medication_data = extract_medication_data(patient_id, resource)
                medications_batch.append(medication_data)

                if len(medications_batch) >= BATCH_SIZE:
                    batch_insert_medications(conn, medications_batch)
                    medications_batch = []

        batch_insert_patients(conn, patients_batch)
        batch_insert_conditions(conn, conditions_batch)
        batch_insert_observations(conn, observations_batch)
        batch_insert_medications(conn, medications_batch)


def mark_file_ingested(filename):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO ingested_files (filename) VALUES (:fn) ON CONFLICT (filename) DO NOTHING"),
            {"fn": filename}
        )


def is_file_ingested(filename):
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT 1 FROM ingested_files WHERE filename = :fn LIMIT 1"),
            {"fn": filename}
        )
        return r.first() is not None


def main():
    if FHIR_IS_URL:
        raise Exception("FHIR_DATA_PATH in .env points to a URL — run `python scripts/download_data.py` first.")

    if not FHIR_FOLDER:
        raise Exception("FHIR_DATA_PATH missing from .env")

    files = list(Path(FHIR_FOLDER).glob("*.json"))
    print(f"Found {len(files)} patient files\n")

    start_time = time.time()

    for file in files:
        if is_file_ingested(file.name):
            print(f"→ Skipping already-ingested file: {file.name}")
            continue
        try:
            file_start = time.time()
            process_bundle(file)
            mark_file_ingested(file.name)
            file_duration = time.time() - file_start
            print(f"✓ Loaded: {file.name} ({file_duration:.2f}s)")
        except Exception as e:
            print(f"✗ Failed: {file.name}")
            print(f"  Error: {e}")

    total_duration = time.time() - start_time
    print(f"\n✓ Import complete in {total_duration:.2f}s")


if __name__ == "__main__":
    main()