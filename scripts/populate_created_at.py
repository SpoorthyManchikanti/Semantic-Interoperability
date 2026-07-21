"""
Backfill patients.created_at.

Real patients: matched to their original FHIR bundle in ingested_files by
filename (every bundle filename contains its patient_id), using the ETL's
real processed_at timestamp — this is genuine ETL history, not a fabricated
value.

Synthetic clones: there is no recorded historical timestamp for when
insert_synthetic_duplicates.py actually ran, so this sets their created_at
to NOW() at backfill time. That is honest about what we do and don't know:
it does not claim to be their exact original insert moment, but it is
guaranteed later than every real ETL timestamp (2026-06-23), which is all
the merge survivor rule actually needs.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import engine


def main():
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE patients p
            SET created_at = f.processed_at
            FROM ingested_files f
            WHERE f.filename LIKE '%' || p.patient_id || '.json'
              AND p.patient_id NOT LIKE 'synthetic-%'
        """))
        print(f"Backfilled created_at from ingested_files for {result.rowcount} real patients.")

        result = conn.execute(text("""
            UPDATE patients
            SET created_at = NOW()
            WHERE patient_id LIKE 'synthetic-%'
        """))
        print(f"Set created_at=NOW() for {result.rowcount} synthetic clones.")

        missing = conn.execute(text(
            "SELECT COUNT(*) FROM patients WHERE created_at IS NULL"
        )).scalar()
        print(f"Patients still missing created_at: {missing}")


if __name__ == "__main__":
    main()
