"""
Reset the Admin Review demo to its pending state — for rehearsing the
demo repeatedly (and running once on the morning of the actual demo)
without permanently losing the example rows.

Resets exactly:
  - the 21 concepts that make up the original 96-row flagged set for the
    15-patient demo subset (concepts.needs_review -> TRUE, and
    review_decision/reviewed_by/reviewed_at/human_corrected_* -> NULL)
  - the 3 patient_matches rows for the demo's synthetic-clone pairs
    (reviewed -> FALSE, review_decision/reviewed_by/reviewed_at -> NULL)
  - any patient_concepts row with an exception flag set, across the whole
    table (exception_flag -> FALSE, exception_note/flagged_by/flagged_at
    -> NULL) — this is the per-patient exception flag, separate from the
    concept-level review fields above
  - the 3 synthetic clones' merge state (merge_status -> 'active',
    merged_into/merged_at -> NULL) — undoes any patient-merge triggered by
    confirming a match, so the duplicate-review demo can be replayed

The concept_id list is hardcoded (captured once, below) rather than
re-derived from current needs_review/review_decision state, so a
reviewed-then-reset concept can't accidentally drop out of the reset set
on a later run. This guarantees your rehearsed examples (the
appendectomy correction, Carl856's duplicate) are always back to
pending after running this.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import engine

# DEMO CODE — the exact 21 concept_ids in the original 96-row flagged set
# for the 15-patient demo subset (captured 2026-07-20). Includes the
# 'Unknown' fallback (approved) and 'History of appendectomy' (corrected)
# concepts used to test the Admin Review page.
FLAGGED_CONCEPT_IDS = [
    "93b3ef11-8af4-4b5c-b1b1-2eae6d17dae7",  # Abnormal findings diagnostic imaging heart+coronary circulat (finding)
    "97caed04-8606-4012-b572-513ab60586b0",  # Acetaminophen 21.7 MG/ML / Dextromethorphan .../ doxylamine ... Oral Solution
    "869e0159-a9ec-4354-8cc4-8893050397bb",  # Awaiting transplantation of kidney (situation)
    "75dc4288-48e4-4cd3-afc5-54d7e39da96c",  # Bicarbonate [Moles/volume] in Arterial blood
    "1af9a21f-6a4f-4efd-835a-774ba2e479af",  # Bicarbonate [Moles/volume] in Venous blood
    "b99c9bc3-7ef7-40b1-bba0-cb8bb12fe4b2",  # Blood pressure panel with all children optional
    "63f97433-799d-4052-92c5-2213455a09ec",  # Carbon dioxide, total [Moles/volume] in Venous blood
    "7be295e2-b009-44a6-a387-050b5b80bbca",  # Creatine kinase [Enzymatic activity/volume] in Serum or Plasma
    "f9ea37e6-16bd-4598-9301-05311d99ea78",  # Fatigue (finding)
    "35bdcf5a-1d3c-4358-bed4-bcd117038242",  # History of appendectomy (situation)
    "e2ca83ff-5dfa-4317-850c-6bfb5a6d4aff",  # Medication review due (situation)
    "5604a89a-5def-4704-b314-40234ba9a9a8",  # Odor of Urine
    "3745b164-4c0d-40bf-a193-85fa8b4165d8",  # Physical findings of Prostate
    "d88c89a7-a4b2-4191-b851-b22ca7494348",  # Severe anxiety (panic) (finding)
    "21055ef6-aa87-4cee-84d7-c43d8c7f2d41",  # Sprain (morphologic abnormality)
    "699dd629-c026-4be4-a79b-6a77f6e2fc83",  # Symptom
    "e82a1a79-8370-46ac-8bc0-2379dae29dab",  # Transport problem (finding)
    "8503adac-0005-4e16-83fe-985a5bfe2184",  # US Guidance for biopsy of Prostate
    "0863e4bd-d699-4df6-a8b9-5d5a45c4d01c",  # Unknown
    "c3698d26-1bcb-4683-8d09-bc96864de7a7",  # Weight difference [Mass difference] --pre dialysis - post dialysis
    "f35d9175-8531-4221-aca4-c2a7e37bddf1",  # pH of Venous blood
]

# DEMO CODE — the demo's 15 real patients + 3 synthetic clones, used only
# to scope which patient_matches rows get reset.
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

SYNTHETIC_CLONE_IDS = [
    "synthetic-bfa642d0-0e6a-4355-b223-298bd5c115ac",
    "synthetic-09909454-5410-4416-acf2-4f1fe2d07616",
    "synthetic-8f6f9b04-5ff8-4c24-9b66-00fb229dd532",
]


def main():
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE concepts
            SET needs_review                = TRUE,
                review_decision              = NULL,
                reviewed_by                  = NULL,
                reviewed_at                  = NULL,
                human_corrected_category     = NULL,
                human_corrected_subcategory  = NULL
            WHERE concept_id = ANY(:concept_ids)
        """), {"concept_ids": FLAGGED_CONCEPT_IDS})
        print(f"Reset {result.rowcount} concepts to needs_review=TRUE, review fields cleared.")

        result = conn.execute(text("""
            UPDATE patient_matches
            SET reviewed        = FALSE,
                review_decision = NULL,
                reviewed_by     = NULL,
                reviewed_at     = NULL
            WHERE patient_id_1 = ANY(:demo_ids) AND patient_id_2 = ANY(:clone_ids)
        """), {"demo_ids": DEMO_SUBSET_IDS, "clone_ids": SYNTHETIC_CLONE_IDS})
        print(f"Reset {result.rowcount} patient_matches rows to reviewed=FALSE, review fields cleared.")

        result = conn.execute(text("""
            UPDATE patient_concepts
            SET exception_flag = FALSE,
                exception_note = NULL,
                flagged_by     = NULL,
                flagged_at     = NULL
            WHERE exception_flag = TRUE
               OR exception_note IS NOT NULL
               OR flagged_by IS NOT NULL
               OR flagged_at IS NOT NULL
        """))
        print(f"Reset {result.rowcount} patient_concepts rows to exception_flag=FALSE, exception fields cleared.")

        result = conn.execute(text("""
            UPDATE patient_concepts
            SET review_decision             = NULL,
                reviewed_by                 = NULL,
                reviewed_at                 = NULL,
                human_corrected_category    = NULL,
                human_corrected_subcategory = NULL
            WHERE review_decision IS NOT NULL
               OR reviewed_by IS NOT NULL
               OR reviewed_at IS NOT NULL
               OR human_corrected_category IS NOT NULL
               OR human_corrected_subcategory IS NOT NULL
        """))
        print(f"Reset {result.rowcount} patient_concepts rows with per-patient review fields cleared.")

        result = conn.execute(text("""
            UPDATE patients
            SET merge_status = 'active',
                merged_into  = NULL,
                merged_at    = NULL
            WHERE patient_id = ANY(:clone_ids)
        """), {"clone_ids": SYNTHETIC_CLONE_IDS})
        print(f"Reset {result.rowcount} synthetic clones to merge_status='active', merge fields cleared.")

    print("Demo state reset. Admin Review queues are back to pending.")


if __name__ == "__main__":
    main()
