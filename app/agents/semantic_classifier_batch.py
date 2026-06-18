import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os
import uuid
import json
import logging
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import text

from app.database import engine
from app.agents.semantic_classifier_agent import classify_concept, fetch_categories

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


# ----------------------------------------------------------------
# Agent run logging
# ----------------------------------------------------------------

def start_run(total_records: int) -> int:
    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO agent_runs (agent_name, status, total_records)
            VALUES ('semantic_classifier', 'running', :total)
            RETURNING id
        """), {"total": total_records})
        run_id = result.fetchone()[0]
    log.info(f"Agent run started — id={run_id}, total_unique_concepts={total_records}")
    return run_id


def update_progress(run_id: int, processed: int, failed: int, prompt_tokens: int, completion_tokens: int):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE agent_runs
            SET processed_records = :processed,
                failed_records = :failed,
                prompt_tokens = :prompt_tokens,
                completion_tokens = :completion_tokens
            WHERE id = :run_id
        """), {
            "processed": processed,
            "failed": failed,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "run_id": run_id
        })


def append_error(run_id: int, concept_name: str, source_type: str, error: str):
    entry = json.dumps({
        "record": concept_name,
        "source_type": source_type,
        "error": error,
        "timestamp": datetime.utcnow().isoformat()
    })
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE agent_runs
            SET error_log = error_log || :entry::jsonb
            WHERE id = :run_id
        """), {"entry": f"[{entry}]", "run_id": run_id})


def complete_run(run_id: int, processed: int, failed: int, prompt_tokens: int, completion_tokens: int, success: bool):
    status = "completed" if success else "failed"
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE agent_runs
            SET status = :status,
                completed_at = NOW(),
                processed_records = :processed,
                failed_records = :failed,
                prompt_tokens = :prompt_tokens,
                completion_tokens = :completion_tokens
            WHERE id = :run_id
        """), {
            "status": status,
            "processed": processed,
            "failed": failed,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "run_id": run_id
        })
    log.info(f"Run {run_id} {status} — processed={processed}, failed={failed}, prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}")


# ----------------------------------------------------------------
# Step 1: Fetch all unique concepts from source tables
# ----------------------------------------------------------------

def fetch_unique_concepts() -> list[dict]:
    """
    Returns a deduplicated list of {concept_name, source_type}
    across conditions, medications, and observations.
    One entry per unique (concept_name, source_type) pair.
    """
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT condition_name AS concept_name, 'condition' AS source_type FROM conditions
            UNION
            SELECT DISTINCT medication_name, 'medication' FROM medications
            UNION
            SELECT DISTINCT observation_name, 'observation' FROM observations
            ORDER BY source_type, concept_name
        """)).fetchall()
    return [{"concept_name": row[0], "source_type": row[1]} for row in rows]


# ----------------------------------------------------------------
# Step 2: Classify and write each unique concept
# ----------------------------------------------------------------

def write_concept(concept_name: str, source_type: str, result: dict) -> str:
    """
    Upsert into concepts table. Returns the concept_id.
    """
    with engine.begin() as conn:
        existing = conn.execute(text("""
            SELECT concept_id FROM concepts
            WHERE concept_name = :name AND source_type = :source_type
        """), {"name": concept_name, "source_type": source_type}).fetchone()

        if existing:
            concept_id = existing[0]
            conn.execute(text("""
                UPDATE concepts
                SET category = :category,
                    subcategory = :subcategory,
                    confidence = :confidence,
                    updated_at = NOW()
                WHERE concept_id = :concept_id
            """), {
                "category": result["category"],
                "subcategory": result["subcategory"],
                "confidence": result["confidence"],
                "concept_id": concept_id
            })
        else:
            concept_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO concepts
                    (concept_id, concept_name, source_type, category, subcategory, confidence)
                VALUES
                    (:concept_id, :concept_name, :source_type, :category, :subcategory, :confidence)
            """), {
                "concept_id": concept_id,
                "concept_name": concept_name,
                "source_type": source_type,
                "category": result["category"],
                "subcategory": result["subcategory"],
                "confidence": result["confidence"]
            })

    return concept_id


# ----------------------------------------------------------------
# Step 3: Bulk write patient linkages via SQL JOIN — no API calls
# ----------------------------------------------------------------

def write_patient_linkages():
    """
    Bulk insert into patient_concepts by joining source tables
    against the classified concepts table.
    Zero API calls — pure SQL.
    """
    log.info("Writing patient linkages...")

    with engine.begin() as conn:
        # Conditions
        conn.execute(text("""
            INSERT INTO patient_concepts (patient_id, concept_id, source_id, source_type)
            SELECT c.patient_id, con.concept_id, c.id, 'condition'
            FROM conditions c
            JOIN concepts con
                ON con.concept_name = c.condition_name
                AND con.source_type = 'condition'
            ON CONFLICT (patient_id, concept_id) DO NOTHING
        """))

        # Medications
        conn.execute(text("""
            INSERT INTO patient_concepts (patient_id, concept_id, source_id, source_type)
            SELECT m.patient_id, con.concept_id, m.id, 'medication'
            FROM medications m
            JOIN concepts con
                ON con.concept_name = m.medication_name
                AND con.source_type = 'medication'
            ON CONFLICT (patient_id, concept_id) DO NOTHING
        """))

        # Observations
        conn.execute(text("""
            INSERT INTO patient_concepts (patient_id, concept_id, source_id, source_type)
            SELECT o.patient_id, con.concept_id, o.id, 'observation'
            FROM observations o
            JOIN concepts con
                ON con.concept_name = o.observation_name
                AND con.source_type = 'observation'
            ON CONFLICT (patient_id, concept_id) DO NOTHING
        """))

    log.info("Patient linkages written.")

if __name__ == "__main__":
    log.info("Starting optimized semantic classifier batch run...")

    # Fetch all unique concepts upfront
    unique_concepts = fetch_unique_concepts()
    total = len(unique_concepts)
    log.info(f"Found {total} unique concepts to classify.")

    categories = fetch_categories()
    log.info(f"Loaded {len(categories)} categories: {categories}")

    run_id = start_run(total)
    counters = {"processed": 0, "failed": 0, "prompt_tokens": 0, "completion_tokens": 0}

    try:
        # Step 2: classify each unique concept — one API call each
        for i, item in enumerate(unique_concepts):
            concept_name = item["concept_name"]
            source_type = item["source_type"]
            try:
                result = classify_concept(concept_name, categories)
                write_concept(concept_name, source_type, result)
                counters["processed"] += 1
                counters["prompt_tokens"] += result.get("prompt_tokens", 0)
                counters["completion_tokens"] += result.get("completion_tokens", 0)
                log.info(f"  [{source_type}] {concept_name} → {result['category']} ({result['confidence']}) | tokens: {result.get('prompt_tokens', 0)}p {result.get('completion_tokens', 0)}c")
            except Exception as e:
                counters["failed"] += 1
                error_msg = str(e)
                log.error(f"  [{source_type}] Failed for '{concept_name}': {error_msg}")
                append_error(run_id, concept_name, source_type, error_msg)

            # Update progress every 10 records
            if (i + 1) % 10 == 0:
                update_progress(run_id, counters["processed"], counters["failed"], counters["prompt_tokens"], counters["completion_tokens"])

        # Step 3: bulk write all patient linkages — no API calls
        write_patient_linkages()

        complete_run(run_id, counters["processed"], counters["failed"], counters["prompt_tokens"], counters["completion_tokens"], success=True)

    except Exception as e:
        log.error(f"Batch run failed unexpectedly: {e}")
        complete_run(run_id, counters["processed"], counters["failed"], counters["prompt_tokens"], counters["completion_tokens"], success=False)