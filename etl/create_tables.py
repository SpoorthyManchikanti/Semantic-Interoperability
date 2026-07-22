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

        # Real provenance field — where this patient record actually came
        # from. Nullable; populated by scripts/populate_data_source.py, not
        # hardcoded in the frontend.
        conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS data_source TEXT;"))

        # Patient-merge tracking — populated by PATCH /patients/matches/{id}/review
        # when decision='confirmed'. The duplicate row is never deleted (reversible/
        # auditable); merge_status distinguishes a merged-away row from an active one.
        conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS merged_into TEXT REFERENCES patients(patient_id);"))
        conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS merge_status TEXT DEFAULT 'active';"))
        conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS merged_at TIMESTAMP;"))

        # Real creation timestamp — used by the merge survivor rule
        # (older created_at wins). Backfilled by scripts/populate_created_at.py,
        # not defaulted here, since a blanket DEFAULT NOW() would stamp every
        # existing row with the same ALTER-time value and destroy the real
        # ordering we can actually recover from ingested_files.processed_at.
        conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS created_at TIMESTAMP;"))

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

        # Additive OMOP/Athena cross-reference columns — populated by
        # scripts/enrich_with_athena.py, never by Agent 1. Nullable; a NULL
        # here just means that concept hasn't been (or couldn't be) resolved
        # against Athena yet.
        conn.execute(text("ALTER TABLE concepts ADD COLUMN IF NOT EXISTS omop_concept_id TEXT;"))
        conn.execute(text("ALTER TABLE concepts ADD COLUMN IF NOT EXISTS omop_standard_name TEXT;"))
        conn.execute(text("ALTER TABLE concepts ADD COLUMN IF NOT EXISTS omop_domain TEXT;"))
        conn.execute(text("ALTER TABLE concepts ADD COLUMN IF NOT EXISTS vocabulary_mismatch BOOLEAN;"))

        # Human-in-the-loop review tracking, populated by PATCH /concepts/{id}/review.
        # human_corrected_* are separate from category/subcategory so the
        # original Agent 1 classification stays visible alongside any
        # human correction — nothing here overwrites Agent 1's own columns.
        conn.execute(text("ALTER TABLE concepts ADD COLUMN IF NOT EXISTS reviewed_by TEXT;"))
        conn.execute(text("ALTER TABLE concepts ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP;"))
        conn.execute(text("ALTER TABLE concepts ADD COLUMN IF NOT EXISTS review_decision TEXT;"))
        conn.execute(text("ALTER TABLE concepts ADD COLUMN IF NOT EXISTS human_corrected_category TEXT;"))
        conn.execute(text("ALTER TABLE concepts ADD COLUMN IF NOT EXISTS human_corrected_subcategory TEXT;"))

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

        # Per-patient exception flag — scoped to one patient's occurrence of
        # a concept, not the concept itself. Separate from concepts.needs_review
        # /review_decision (concept-level, shared across every patient who has
        # that concept) — populated by PATCH /patient-concepts/{id}/exception.
        conn.execute(text("ALTER TABLE patient_concepts ADD COLUMN IF NOT EXISTS exception_flag BOOLEAN DEFAULT FALSE;"))
        conn.execute(text("ALTER TABLE patient_concepts ADD COLUMN IF NOT EXISTS exception_note TEXT;"))
        conn.execute(text("ALTER TABLE patient_concepts ADD COLUMN IF NOT EXISTS flagged_by TEXT;"))
        conn.execute(text("ALTER TABLE patient_concepts ADD COLUMN IF NOT EXISTS flagged_at TIMESTAMP;"))

        # Per-patient-linkage review tracking — mirrors concepts.review_decision/
        # reviewed_by/reviewed_at/human_corrected_* but scoped to one row, since
        # different patients can now get different review outcomes for the
        # same shared concept. Populated by PATCH /concepts/{id}/review when
        # the caller passes patient_concept_ids; the concepts-table columns
        # remain the default (all-patients) path when that list is omitted.
        conn.execute(text("ALTER TABLE patient_concepts ADD COLUMN IF NOT EXISTS review_decision TEXT;"))
        conn.execute(text("ALTER TABLE patient_concepts ADD COLUMN IF NOT EXISTS reviewed_by TEXT;"))
        conn.execute(text("ALTER TABLE patient_concepts ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP;"))
        conn.execute(text("ALTER TABLE patient_concepts ADD COLUMN IF NOT EXISTS human_corrected_category TEXT;"))
        conn.execute(text("ALTER TABLE patient_concepts ADD COLUMN IF NOT EXISTS human_corrected_subcategory TEXT;"))

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

        # Additive columns for real, patient-scoped Athena/OMOP relationships
        # (populated by scripts/populate_concept_relationships.py) — distinct
        # from source_concept_id/target_concept_id above, which are local
        # concepts.concept_id UUIDs, not OMOP concept IDs, and were never
        # populated by anything. These new columns store genuine
        # (non-self-referential) Athena_Concept_Relationships rows where both
        # ends are in one patient's own OMOP-resolved concept set.
        conn.execute(text("ALTER TABLE concept_relationships ADD COLUMN IF NOT EXISTS patient_id TEXT;"))
        conn.execute(text("ALTER TABLE concept_relationships ADD COLUMN IF NOT EXISTS concept_id_1 TEXT;"))
        conn.execute(text("ALTER TABLE concept_relationships ADD COLUMN IF NOT EXISTS concept_id_2 TEXT;"))
        conn.execute(text("ALTER TABLE concept_relationships ADD COLUMN IF NOT EXISTS relationship_id TEXT;"))
        conn.execute(text("ALTER TABLE concept_relationships ADD COLUMN IF NOT EXISTS concept_1_name TEXT;"))
        conn.execute(text("ALTER TABLE concept_relationships ADD COLUMN IF NOT EXISTS concept_2_name TEXT;"))
        conn.execute(text("""
            DO $$ BEGIN
                ALTER TABLE concept_relationships
                ADD CONSTRAINT concept_relationships_patient_pair_rel_unique
                UNIQUE (patient_id, concept_id_1, concept_id_2, relationship_id);
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
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
        # Patient identity resolution — match flags (read-only findings,
        # never auto-merged)
        # ----------------------------------------------------------------

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS patient_matches (
            id                  SERIAL PRIMARY KEY,
            patient_id_1        TEXT REFERENCES patients(patient_id),
            patient_id_2        TEXT REFERENCES patients(patient_id),
            match_confidence    FLOAT,
            matched_on          JSONB,
            reviewed            BOOLEAN DEFAULT FALSE,
            created_at          TIMESTAMP DEFAULT NOW(),
            CONSTRAINT patient_matches_pair_unique UNIQUE (patient_id_1, patient_id_2)
        );
        """))

        # Human-in-the-loop review tracking, populated by
        # PATCH /patients/matches/{id}/review. Never merges/modifies patients rows.
        conn.execute(text("ALTER TABLE patient_matches ADD COLUMN IF NOT EXISTS reviewed_by TEXT;"))
        conn.execute(text("ALTER TABLE patient_matches ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP;"))
        conn.execute(text("ALTER TABLE patient_matches ADD COLUMN IF NOT EXISTS review_decision TEXT;"))

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
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_patient_matches_patient_1 ON patient_matches(patient_id_1);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_patient_matches_patient_2 ON patient_matches(patient_id_2);"))

    print("All tables created successfully.")


if __name__ == "__main__":
    create_tables()