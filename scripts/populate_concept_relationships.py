"""
Populate concept_relationships with real, patient-scoped Athena/OMOP
relationships for the 15-patient demo subset.

For each patient: take their full OMOP-resolved concept set, then find
every genuine (non-self-referential — concept_id_1 != concept_id_2) row
in Athena_Concept_Relationships where both ends are in that same set.
This excludes the 'Maps to'/'Mapped from' identity-mapping noise found
earlier (a concept mapping to itself), while still keeping any Maps
to/Mapped from row that happens to be non-identity.

Read-only against Athena_Concept_Relationships/patient_concepts/concepts;
only writes to concept_relationships (additive columns, doesn't touch
source_concept_id/target_concept_id/relationship_type/confidence/source).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import engine

# DEMO CODE — the 15-patient demo subset.
DEMO_SUBSET_IDS = [
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


def fetch_patient_omop_concepts(conn, patient_id):
    rows = conn.execute(text("""
        SELECT DISTINCT con.omop_concept_id, con.omop_standard_name
        FROM patient_concepts pc
        JOIN concepts con ON con.concept_id = pc.concept_id
        WHERE pc.patient_id = :patient_id AND con.omop_concept_id IS NOT NULL
    """), {"patient_id": patient_id}).fetchall()
    return {r.omop_concept_id: r.omop_standard_name for r in rows}


def fetch_internal_relationships(conn, ids):
    rows = conn.execute(text("""
        SELECT relationship_id, concept_id_1, concept_id_2
        FROM "Athena_Concept_Relationships"
        WHERE concept_id_1 = ANY(:ids) AND concept_id_2 = ANY(:ids)
          AND concept_id_1 != concept_id_2
    """), {"ids": ids}).fetchall()
    return rows


def main():
    total_inserted = 0
    with engine.begin() as conn:
        for patient_id in DEMO_SUBSET_IDS:
            names = fetch_patient_omop_concepts(conn, patient_id)
            ids = list(names.keys())
            rels = fetch_internal_relationships(conn, ids)

            for rel in rels:
                conn.execute(text("""
                    INSERT INTO concept_relationships
                        (patient_id, concept_id_1, concept_id_2, relationship_id,
                         concept_1_name, concept_2_name)
                    VALUES
                        (:patient_id, :concept_id_1, :concept_id_2, :relationship_id,
                         :concept_1_name, :concept_2_name)
                    ON CONFLICT ON CONSTRAINT concept_relationships_patient_pair_rel_unique
                    DO NOTHING
                """), {
                    "patient_id": patient_id,
                    "concept_id_1": rel.concept_id_1,
                    "concept_id_2": rel.concept_id_2,
                    "relationship_id": rel.relationship_id,
                    "concept_1_name": names.get(rel.concept_id_1),
                    "concept_2_name": names.get(rel.concept_id_2),
                })

            print(f"{patient_id}: {len(ids)} OMOP concepts, {len(rels)} genuine relationships")
            total_inserted += len(rels)

    print()
    print(f"Total relationships inserted (or already present) across all 15 patients: {total_inserted}")


if __name__ == "__main__":
    main()
