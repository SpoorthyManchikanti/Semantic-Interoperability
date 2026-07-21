"""
Enrich concepts with real Athena/OMOP cross-references — additive only.

Runs the concepts.vocabulary_code -> Athena_Concepts.concept_code join
(scoped to the demo subset's 15 patients) as a read-only SELECT, then
writes the results into concepts.omop_concept_id, omop_standard_name,
and omop_domain.

Does NOT touch category, subcategory, confidence, vocabulary_code,
vocabulary_id, or needs_review — those are Agent 1's columns and are
never modified here. Agent 1 itself is never invoked or re-run.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import engine

# DEMO CODE — hardcoded to the 15-patient demo subset.
DEMO_SUBSET_PATIENT_IDS = [
    "de7bdc23-9140-c119-268f-36fe8ddaab44",
    "aa305aed-7552-d253-e929-361157b3f14d",
    "299e68be-4e57-a106-3b8a-5e44df196f2a",
    "4c77f24d-765d-edf6-a7d7-bb1d14801f1b",
    "d95089e3-0388-e617-d87a-dd345033f51a",
    "ca2910b0-5032-b5de-0240-a727eaa9fd9a",
    "b2f866ed-f1b8-1c7d-81dd-311110bfd7d3",
    "2d123aa6-15c2-5d05-f04b-bb2829d724d9",
    "fb66498c-fbf8-3c71-7145-0dafa7866a37",
    "b5a8bbe2-8854-905d-af0e-4e19ca015db8",
    "5146d402-7629-2880-27b6-3203115cabb7",
    "d76fde70-5136-84a2-2721-0ea898b8683f",
    "c4fe8cf1-1b0d-710e-6976-e8183e3b7ab9",
    "ab683cb7-419f-9426-9183-a394af834440",
    "d2a30bc4-15fe-4cc8-a3ab-fbb824dbff33",
]


def fetch_matches(conn):
    """Read-only join: our vocabulary_code/vocabulary_id against Athena's
    concept_code/vocabulary_id, for the 345 concepts linked to the demo
    subset's 15 patients."""
    rows = conn.execute(text("""
        SELECT DISTINCT
            con.concept_id,
            ac.concept_id   AS omop_concept_id,
            ac.concept_name AS omop_standard_name,
            ac.domain_id    AS omop_domain
        FROM concepts con
        JOIN patient_concepts pc ON pc.concept_id = con.concept_id
        JOIN "Athena_Concepts" ac
            ON ac.concept_code = con.vocabulary_code
           AND ac.vocabulary_id = con.vocabulary_id
        WHERE pc.patient_id = ANY(:patient_ids)
          AND con.vocabulary_code IS NOT NULL
    """), {"patient_ids": DEMO_SUBSET_PATIENT_IDS}).fetchall()
    return [dict(r._mapping) for r in rows]


def main():
    with engine.begin() as conn:
        matches = fetch_matches(conn)
        print(f"Resolved {len(matches)} concepts against Athena/OMOP.")

        for m in matches:
            conn.execute(text("""
                UPDATE concepts
                SET omop_concept_id    = :omop_concept_id,
                    omop_standard_name = :omop_standard_name,
                    omop_domain        = :omop_domain
                WHERE concept_id = :concept_id
            """), m)

    print("Enrichment complete. No other columns were modified; Agent 1 was not invoked.")


if __name__ == "__main__":
    main()
