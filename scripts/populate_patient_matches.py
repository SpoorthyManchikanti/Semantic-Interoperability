"""
Populate patient_matches by running find_potential_matches() against the
18-patient demo pool (15 real demo-subset patients + 3 synthetic clones).

Only touches patient_matches — read-only against patients, no Agent 1
tables involved.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
from dotenv import load_dotenv
from sqlalchemy import text

from app.database import engine
from app.services.identity_resolution import find_potential_matches

load_dotenv()

# DEMO CODE — hardcoded ids for this specific demo run, not a general query.
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


def fetch_patients(conn, patient_ids):
    rows = conn.execute(text("""
        SELECT patient_id, first_name, last_name, gender, birth_date
        FROM patients
        WHERE patient_id = ANY(:ids)
    """), {"ids": patient_ids}).fetchall()
    return [dict(row._mapping) for row in rows]


def main():
    with engine.begin() as conn:
        patients = fetch_patients(conn, DEMO_SUBSET_IDS + SYNTHETIC_CLONE_IDS)
        for p in patients:
            p["birth_date"] = str(p["birth_date"])

        print(f"Loaded {len(patients)} patients (expected 18)")

        matches = find_potential_matches(patients, threshold=0.85)
        print(f"find_potential_matches found {len(matches)} pairs >= 0.85")

        for m in matches:
            conn.execute(text("""
                INSERT INTO patient_matches
                    (patient_id_1, patient_id_2, match_confidence, matched_on)
                VALUES
                    (:patient_id_1, :patient_id_2, :match_confidence, CAST(:matched_on AS JSONB))
                ON CONFLICT (patient_id_1, patient_id_2) DO NOTHING
            """), {
                "patient_id_1": m["patient_a_id"],
                "patient_id_2": m["patient_b_id"],
                "match_confidence": m["score"],
                "matched_on": json.dumps(m["matched_on"]),
            })
            print(f"  {m['patient_a_id']} <-> {m['patient_b_id']}  score={m['score']}  {m['matched_on']}")


if __name__ == "__main__":
    main()
