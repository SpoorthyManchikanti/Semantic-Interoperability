from sqlalchemy import *

from app.database import engine

metadata = MetaData()

# Core FHIR tables
patients = Table(
    "patients",
    metadata,

    Column("patient_id", String, primary_key=True),
    Column("first_name", String),
    Column("last_name", String),
    Column("gender", String)
)

conditions = Table(
    "conditions",
    metadata,

    Column("id", Integer, primary_key=True),
    Column("patient_id", String),
    Column("condition_name", String),
    UniqueConstraint("patient_id", "condition_name", name="uq_conditions_patient_condition")
)

observations = Table(
    "observations",
    metadata,

    Column("id", Integer, primary_key=True),
    Column("patient_id", String),
    Column("observation_name", String),
    Column("value", String),
    UniqueConstraint("patient_id", "observation_name", "value", name="uq_observations_patient_obs_value")
)

medications = Table(
    "medications",
    metadata,

    Column("id", Integer, primary_key=True),
    Column("patient_id", String),
    Column("medication_name", String),
    UniqueConstraint("patient_id", "medication_name", name="uq_medications_patient_med")
)


# Track which files (bundles) have been ingested to avoid duplicates
ingested_files = Table(
    "ingested_files",
    metadata,
    Column("filename", String, primary_key=True),
    Column("processed_at", DateTime, server_default=func.now())
)

metadata.create_all(engine)