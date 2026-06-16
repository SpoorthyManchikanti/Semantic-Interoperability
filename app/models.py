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

# Semantic interoperability tables
semantic_concepts = Table(
    "semantic_concepts",
    metadata,

    Column("concept_id", String, primary_key=True),
    Column("concept_name", String, unique=True),
    Column("concept_type", String),  # "condition", "observation", "medication"
    Column("description", String, nullable=True),
    Column("created_at", DateTime, default="now()")
)

concept_mappings = Table(
    "concept_mappings",
    metadata,

    Column("mapping_id", Integer, primary_key=True),
    Column("concept_id", String, ForeignKey("semantic_concepts.concept_id")),
    Column("source_value", String),  # Raw FHIR value
    Column("source_system", String, default="FHIR"),
    Column("confidence", Float, default=1.0),
    Column("created_at", DateTime, default="now()")
)

patient_semantic_profile = Table(
    "patient_semantic_profile",
    metadata,

    Column("profile_id", Integer, primary_key=True),
    Column("patient_id", String, ForeignKey("patients.patient_id")),
    Column("condition_concepts", String),  # JSON array of canonical condition IDs
    Column("observation_concepts", String),  # JSON array of canonical observation IDs
    Column("medication_concepts", String),  # JSON array of canonical medication IDs
    Column("quality_score", Float),
    Column("updated_at", DateTime, default="now()")
)

metadata.create_all(engine)