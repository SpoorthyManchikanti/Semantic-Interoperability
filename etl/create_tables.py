import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import engine


def create_tables():
    with engine.begin() as conn:

        # ----------------------------------------------------------------
        # Core FHIR source tables
        # ----------------------------------------------------------------

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id  TEXT PRIMARY KEY,
            first_name  TEXT,
            last_name   TEXT,
            gender      TEXT,
            birth_date  DATE
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS conditions (
            id              SERIAL PRIMARY KEY,
            patient_id      TEXT NOT NULL,
            condition_name  TEXT NOT NULL,
            snomed_code     TEXT,
            CONSTRAINT conditions_patient_condition_unique
                UNIQUE (patient_id, condition_name)
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS medications (
            id               SERIAL PRIMARY KEY,
            patient_id       TEXT NOT NULL,
            medication_name  TEXT NOT NULL,
            rxnorm_code      TEXT,
            CONSTRAINT medications_patient_medication_unique
                UNIQUE (patient_id, medication_name)
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS observations (
            id                  SERIAL PRIMARY KEY,
            patient_id          TEXT NOT NULL,
            observation_name    TEXT NOT NULL,
            observation_value   TEXT,
            loinc_code          TEXT,
            CONSTRAINT observations_patient_observation_value_unique
                UNIQUE (patient_id, observation_name, observation_value)
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS ingested_files (
            filename    TEXT PRIMARY KEY,
            ingested_at TIMESTAMP DEFAULT NOW()
        );
        """))

        # ----------------------------------------------------------------
        # Agent 1 output tables
        # ----------------------------------------------------------------

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS concepts (
            concept_id      TEXT PRIMARY KEY,
            concept_name    TEXT NOT NULL,
            source_type     TEXT NOT NULL,
            category        TEXT,
            subcategory     TEXT,
            confidence      FLOAT,
            needs_review    BOOLEAN DEFAULT FALSE,
            vocabulary_code TEXT,
            vocabulary_id   TEXT,
            classified_at   TIMESTAMP DEFAULT NOW(),
            updated_at      TIMESTAMP DEFAULT NOW()
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS patient_concepts (
            id          SERIAL PRIMARY KEY,
            patient_id  TEXT NOT NULL,
            concept_id  TEXT NOT NULL,
            source_id   INTEGER,
            source_type TEXT,
            CONSTRAINT patient_concepts_patient_concept_unique
                UNIQUE (patient_id, concept_id)
        );
        """))

        # ----------------------------------------------------------------
        # Agent 2 output table
        # ----------------------------------------------------------------

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS ontology_relationships (
            id                  SERIAL PRIMARY KEY,
            parent_concept_id   TEXT,
            child_concept_id    TEXT REFERENCES concepts(concept_id),
            parent_label        TEXT,
            relationship_type   TEXT,  -- IS_A, PART_OF, SUBTYPE_OF
            confidence          FLOAT,
            source              TEXT,  -- 'omop', 'llm', 'rule'
            created_at          TIMESTAMP DEFAULT NOW()
        );
        """))

        # ----------------------------------------------------------------
        # Agent 3 output table
        # ----------------------------------------------------------------

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS concept_relationships (
            id                  SERIAL PRIMARY KEY,
            source_concept_id   TEXT REFERENCES concepts(concept_id),
            target_concept_id   TEXT REFERENCES concepts(concept_id),
            relationship_type   TEXT,  -- TREATS, RISK_FACTOR_FOR, MONITORS, etc.
            confidence          FLOAT,
            source              TEXT,  -- 'omop', 'llm'
            created_at          TIMESTAMP DEFAULT NOW()
        );
        """))

        # ----------------------------------------------------------------
        # Agent 4 output table
        # ----------------------------------------------------------------

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS patient_profiles (
            id              SERIAL PRIMARY KEY,
            patient_id      TEXT NOT NULL UNIQUE,
            profile_json    JSONB,
            created_at      TIMESTAMP DEFAULT NOW(),
            updated_at      TIMESTAMP DEFAULT NOW()
        );
        """))

        # ----------------------------------------------------------------
        # Pipeline tracking tables
        # ----------------------------------------------------------------

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS processing_status (
            id              SERIAL PRIMARY KEY,
            concept_id      TEXT REFERENCES concepts(concept_id),
            concept_name    TEXT NOT NULL,
            source_type     TEXT NOT NULL,
            agent_1_status  TEXT DEFAULT 'pending',
            agent_2_status  TEXT DEFAULT 'pending',
            agent_3_status  TEXT DEFAULT 'pending',
            agent_4_status  TEXT DEFAULT 'pending',
            last_updated    TIMESTAMP DEFAULT NOW()
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS agent_runs (
            id                  SERIAL PRIMARY KEY,
            agent_name          TEXT NOT NULL,
            status              TEXT DEFAULT 'running',
            started_at          TIMESTAMP DEFAULT NOW(),
            completed_at        TIMESTAMP,
            total_records       INTEGER DEFAULT 0,
            processed_records   INTEGER DEFAULT 0,
            failed_records      INTEGER DEFAULT 0,
            prompt_tokens       INTEGER DEFAULT 0,
            completion_tokens   INTEGER DEFAULT 0,
            error_log           JSONB DEFAULT '[]'::jsonb
        );
        """))

        # ----------------------------------------------------------------
        # OMOP vocabulary tables
        # ----------------------------------------------------------------

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS omop_concept (
            concept_id       INTEGER PRIMARY KEY,
            concept_name     TEXT,
            domain_id        TEXT,
            vocabulary_id    TEXT,
            concept_class_id TEXT,
            standard_concept TEXT,
            concept_code     TEXT
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS omop_concept_relationship (
            concept_id_1    INTEGER,
            concept_id_2    INTEGER,
            relationship_id TEXT,
            PRIMARY KEY (concept_id_1, concept_id_2, relationship_id)
        );
        """))

        # ----------------------------------------------------------------
        # Indexes
        # ----------------------------------------------------------------

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_concepts_vocabulary ON concepts(vocabulary_code, vocabulary_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_concepts_source_type ON concepts(source_type);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_patient_concepts_patient ON patient_concepts(patient_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_processing_status_agent_1 ON processing_status(agent_1_status);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_processing_status_concept ON processing_status(concept_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_omop_concept_code ON omop_concept(concept_code, vocabulary_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_omop_relationships ON omop_concept_relationship(concept_id_1, relationship_id);"))

    print("All tables created successfully.")


if __name__ == "__main__":
    create_tables()