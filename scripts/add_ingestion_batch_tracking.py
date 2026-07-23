"""One-time schema migration: adds ingestion_batch_id/ingested_at tracking
so every /ingest run can be identified and rolled back as a unit.

  patients.ingestion_batch_id       -- set to the /ingest job_id that created this patient
  patients.ingested_at              -- when that ingest stage ran (NULL for pre-existing/demo patients)
  ingested_files.ingestion_batch_id -- same job_id, linking the source file to the batch

Idempotent (IF NOT EXISTS) — safe to re-run. Pre-existing rows keep these
columns NULL, which is how DELETE /ingest/batches/{batch_id} in
app/routes/ingest.py tells a real ingest-created patient apart from the
original demo dataset (never rollback-eligible).
"""

from app.database import engine
from sqlalchemy import text


def run():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS ingestion_batch_id UUID"))
        conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ"))
        conn.execute(text("ALTER TABLE ingested_files ADD COLUMN IF NOT EXISTS ingestion_batch_id UUID"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_patients_batch_id ON patients (ingestion_batch_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ingested_files_batch_id ON ingested_files (ingestion_batch_id)"))
    print("Migration applied (or already up to date).")


if __name__ == "__main__":
    run()
