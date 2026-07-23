"""Live ingestion pipeline for onboarding one new patient through our real
pipeline components — no reimplementation. Each stage below calls the same
functions/queries our existing scripts use, just scoped to a single new
patient_id instead of a hardcoded demo-subset list:

  ingest              -> etl.load_data.process_bundle (verbatim)
  classify            -> app.agents.semantic_classifier_agent.classify_concept +
                         semantic_classifier_batch's fetch_pending_concepts/
                         write_concept/write_patient_linkages (verbatim)
  standardize_relate  -> same SQL as scripts/enrich_with_athena.py and
                         scripts/flag_vocabulary_mismatches.py, parameterized
                         to this patient; scripts/populate_concept_relationships.py's
                         fetch_patient_omop_concepts/fetch_internal_relationships
                         (already patient-scoped, imported verbatim)
  identity_check      -> app.services.identity_resolution.match_score/
                         match_breakdown (verbatim), compared against every
                         other patient — the same real function the demo's
                         populate_patient_matches.py script uses
  graph_sync          -> same Cypher/queries as scripts/load_to_neo4j.py
                         (map_source_type_to_relationship/sanitize_relationship_type
                         imported verbatim), parameterized to this one patient
                         instead of the demo subset — writes Patient/Concept/
                         OMOPConcept nodes and DIAGNOSED_WITH/IS_ON_MEDICATION/
                         HAS_OBSERVATION/MAPS_TO/clinical-relationship edges via
                         MERGE, so it's safe to re-run
  complete            -> summary only, no new logic

Progress is tracked in an in-memory job store and exposed via polling —
adequate for this single-process demo deployment (no multi-worker uvicorn).
"""

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from sqlalchemy import text

from app.database import engine
from etl.load_data import process_bundle, mark_file_ingested
from app.agents.semantic_classifier_agent import classify_concept, fetch_categories
from app.agents.semantic_classifier_batch import (
    fetch_pending_concepts,
    write_concept,
    mark_failed,
    write_patient_linkages,
    start_run,
    complete_run,
)
from scripts.populate_concept_relationships import (
    fetch_patient_omop_concepts,
    fetch_internal_relationships,
)
from app.services.identity_resolution import match_score, match_breakdown, DEFAULT_MATCH_THRESHOLD
from app.routes.concepts import register_ingested_patient
from app.neo4j_db import get_neo4j_session
from scripts.load_to_neo4j import map_source_type_to_relationship, sanitize_relationship_type

router = APIRouter(prefix="/ingest", tags=["ingest"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

STAGE_KEYS = ["ingest", "classify", "standardize_relate", "identity_check", "graph_sync", "complete"]

JOBS = {}
JOBS_LOCK = threading.Lock()


def _new_job(filename):
    return {
        "filename": filename,
        "patient_id": None,
        "patient_name": None,
        "duplicate_match": None,
        "stages": {key: {"status": "planned", "summary": None, "error": None} for key in STAGE_KEYS},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _set_stage(job_id, stage, status, summary=None, error=None):
    with JOBS_LOCK:
        job = JOBS[job_id]
        job["stages"][stage]["status"] = status
        if summary is not None:
            job["stages"][stage]["summary"] = summary
        if error is not None:
            job["stages"][stage]["error"] = error


def _set_job_fields(job_id, **fields):
    with JOBS_LOCK:
        JOBS[job_id].update(fields)


# ----------------------------------------------------------------
# Stage 1: Ingest — etl.load_data.process_bundle, reused verbatim
# ----------------------------------------------------------------

def _do_ingest_stage(file_path: Path, original_filename: str):
    with open(file_path, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    patient_resource = next(
        (e["resource"] for e in bundle.get("entry", []) if e.get("resource", {}).get("resourceType") == "Patient"),
        None,
    )
    if not patient_resource:
        raise ValueError("No Patient resource found in this bundle — not a valid FHIR patient export.")

    patient_id = patient_resource["id"]

    with engine.connect() as conn:
        existing = conn.execute(text("SELECT 1 FROM patients WHERE patient_id = :id"), {"id": patient_id}).fetchone()
    if existing:
        raise ValueError(f"Patient {patient_id} already exists in our system — refusing to re-ingest.")

    process_bundle(str(file_path))
    mark_file_ingested(original_filename)

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE patients SET data_source = 'Synthea Synthetic Patient Data', created_at = NOW()
            WHERE patient_id = :id
        """), {"id": patient_id})

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT first_name, last_name FROM patients WHERE patient_id = :id"
        ), {"id": patient_id}).fetchone()
        cond_count = conn.execute(text("SELECT COUNT(*) FROM conditions WHERE patient_id = :id"), {"id": patient_id}).scalar()
        med_count = conn.execute(text("SELECT COUNT(*) FROM medications WHERE patient_id = :id"), {"id": patient_id}).scalar()
        obs_count = conn.execute(text("SELECT COUNT(*) FROM observations WHERE patient_id = :id"), {"id": patient_id}).scalar()

    patient_name = f"{row.first_name} {row.last_name}"
    summary = f"{patient_name} — {cond_count} conditions, {med_count} medications, {obs_count} observations"
    return patient_id, patient_name, summary


# ----------------------------------------------------------------
# Stage 2: Classify — semantic_classifier_agent/batch, reused verbatim
# ----------------------------------------------------------------

def _do_classify_stage(patient_id: str):
    with engine.connect() as conn:
        total_concepts = conn.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT condition_name AS concept_name FROM conditions WHERE patient_id = :id
                UNION
                SELECT DISTINCT medication_name FROM medications WHERE patient_id = :id
                UNION
                SELECT DISTINCT observation_name FROM observations WHERE patient_id = :id
            ) x
        """), {"id": patient_id}).scalar()

    # Global by design (same as the standalone batch script) — right after
    # ingesting one new patient, every already-known concept name already
    # has a 'completed' processing_status row, so only this patient's
    # genuinely new concepts come back pending.
    pending = fetch_pending_concepts()
    categories = fetch_categories()
    run_id = start_run(len(pending))
    counters = {"processed": 0, "failed": 0, "prompt_tokens": 0, "completion_tokens": 0}
    newly_classified_names = []

    for item in pending:
        try:
            result = classify_concept(item["concept_name"], categories, item["source_type"])
            write_concept(item["concept_name"], item["source_type"], result, item["vocabulary_code"], item["vocabulary_id"])
            counters["processed"] += 1
            counters["prompt_tokens"] += result.get("prompt_tokens", 0)
            counters["completion_tokens"] += result.get("completion_tokens", 0)
            newly_classified_names.append((item["concept_name"], item["source_type"]))
        except Exception as e:
            counters["failed"] += 1
            mark_failed(item["concept_name"], item["source_type"])

    write_patient_linkages()
    complete_run(
        run_id, counters["processed"], counters["failed"],
        counters["prompt_tokens"], counters["completion_tokens"],
        success=(counters["failed"] == 0),
    )

    if pending and counters["processed"] == 0:
        raise RuntimeError(f"Classification failed for all {counters['failed']} new concept(s) for this patient.")

    reused = total_concepts - len(pending)
    with engine.connect() as conn:
        avg_conf = conn.execute(text("""
            SELECT AVG(con.confidence) FROM patient_concepts pc
            JOIN concepts con ON con.concept_id = pc.concept_id
            WHERE pc.patient_id = :id
        """), {"id": patient_id}).scalar()

    avg_pct = round((avg_conf or 0) * 100)
    summary = f"{total_concepts} concepts — {reused} reused, {len(pending)} newly classified, avg confidence {avg_pct}%"
    return summary, newly_classified_names


# ----------------------------------------------------------------
# Stage 3: Standardize & Relate — same SQL as enrich_with_athena.py /
# flag_vocabulary_mismatches.py (parameterized to one patient instead of
# the demo subset), plus populate_concept_relationships.py's functions
# (already patient-scoped, imported verbatim)
# ----------------------------------------------------------------

def _do_standardize_relate_stage(patient_id: str, newly_classified_names):
    with engine.begin() as conn:
        omop_matches = conn.execute(text("""
            SELECT DISTINCT con.concept_id, con.concept_name, con.source_type,
                   ac.concept_id AS omop_concept_id,
                   ac.concept_name AS omop_standard_name, ac.domain_id AS omop_domain
            FROM concepts con
            JOIN patient_concepts pc ON pc.concept_id = con.concept_id
            JOIN "Athena_Concepts" ac
                ON ac.concept_code = con.vocabulary_code AND ac.vocabulary_id = con.vocabulary_id
            WHERE pc.patient_id = :patient_id
              AND con.vocabulary_code IS NOT NULL
              AND con.omop_concept_id IS NULL
        """), {"patient_id": patient_id}).fetchall()

        for m in omop_matches:
            conn.execute(text("""
                UPDATE concepts SET omop_concept_id = :omop_concept_id,
                       omop_standard_name = :omop_standard_name, omop_domain = :omop_domain
                WHERE concept_id = :concept_id
            """), dict(m._mapping))

        mismatches = conn.execute(text("""
            SELECT DISTINCT con.concept_id
            FROM concepts con
            JOIN patient_concepts pc ON pc.concept_id = con.concept_id
            LEFT JOIN "Athena_Concepts" ac
                ON ac.concept_code = con.vocabulary_code AND ac.vocabulary_id = con.vocabulary_id
            WHERE pc.patient_id = :patient_id
              AND con.vocabulary_code IS NOT NULL
              AND ac.concept_id IS NULL
              AND (con.vocabulary_mismatch IS NULL OR con.vocabulary_mismatch = FALSE)
        """), {"patient_id": patient_id}).fetchall()

        for m in mismatches:
            conn.execute(text(
                "UPDATE concepts SET vocabulary_mismatch = TRUE WHERE concept_id = :id"
            ), {"id": m.concept_id})

    new_relationship_count = 0
    with engine.begin() as conn:
        omop_names = fetch_patient_omop_concepts(conn, patient_id)
        omop_ids = list(omop_names.keys())
        rels = fetch_internal_relationships(conn, omop_ids) if omop_ids else []
        for rel in rels:
            result = conn.execute(text("""
                INSERT INTO concept_relationships
                    (patient_id, concept_id_1, concept_id_2, relationship_id, concept_1_name, concept_2_name)
                VALUES
                    (:patient_id, :concept_id_1, :concept_id_2, :relationship_id, :concept_1_name, :concept_2_name)
                ON CONFLICT ON CONSTRAINT concept_relationships_patient_pair_rel_unique DO NOTHING
                RETURNING 1
            """), {
                "patient_id": patient_id,
                "concept_id_1": rel.concept_id_1,
                "concept_id_2": rel.concept_id_2,
                "relationship_id": rel.relationship_id,
                "concept_1_name": omop_names.get(rel.concept_id_1),
                "concept_2_name": omop_names.get(rel.concept_id_2),
            }).fetchone()
            if result:
                new_relationship_count += 1

    # "X of Y new concepts resolved" — both X and Y are scoped to the concepts
    # classified *this run* (newly_classified_names). omop_matches above may
    # additionally resolve older unresolved concepts already linked to this
    # patient (harmless side-effect of standardizing the corpus), but those
    # don't belong in a "new concepts" ratio about this patient's own run.
    newly_classified_set = set(newly_classified_names)
    if newly_classified_set:
        names = [n for n, _ in newly_classified_set]
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT concept_name, source_type FROM concepts
                WHERE concept_name = ANY(:names) AND vocabulary_code IS NOT NULL
            """), {"names": names}).fetchall()
        eligible = sum(1 for r in rows if (r.concept_name, r.source_type) in newly_classified_set)
    else:
        eligible = 0

    resolved_count = sum(
        1 for m in omop_matches
        if (m.concept_name, m.source_type) in newly_classified_set
    )
    summary = f"{resolved_count} of {eligible} new concepts resolved to OMOP; {new_relationship_count} new clinical relationship(s) discovered"
    return summary


# ----------------------------------------------------------------
# Stage 4: Identity Check — identity_resolution.match_score, reused
# verbatim, compared against every other patient (no demo special-casing)
# ----------------------------------------------------------------

def _do_identity_check_stage(patient_id: str):
    with engine.connect() as conn:
        new_row = conn.execute(text(
            "SELECT patient_id, first_name, last_name, gender, birth_date FROM patients WHERE patient_id = :id"
        ), {"id": patient_id}).fetchone()
        other_rows = conn.execute(text(
            "SELECT patient_id, first_name, last_name, gender, birth_date FROM patients WHERE patient_id != :id"
        ), {"id": patient_id}).fetchall()

    new_patient = dict(new_row._mapping)
    new_patient["birth_date"] = str(new_patient["birth_date"])

    best_match = None
    for row in other_rows:
        other = dict(row._mapping)
        other["birth_date"] = str(other["birth_date"])
        score = match_score(new_patient, other)
        if score >= DEFAULT_MATCH_THRESHOLD and (best_match is None or score > best_match["score"]):
            best_match = {
                "patient_id": other["patient_id"],
                "name": f"{other['first_name']} {other['last_name']}",
                "score": score,
                "matched_on": match_breakdown(new_patient, other),
            }

    if best_match:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO patient_matches (patient_id_1, patient_id_2, match_confidence, matched_on)
                VALUES (:p1, :p2, :conf, CAST(:matched_on AS JSONB))
                ON CONFLICT (patient_id_1, patient_id_2) DO NOTHING
            """), {
                "p1": patient_id,
                "p2": best_match["patient_id"],
                "conf": best_match["score"],
                "matched_on": json.dumps(best_match["matched_on"]),
            })
        summary = f"Potential match: {best_match['name']}, {round(best_match['score'] * 100)}% confidence"
    else:
        summary = "No potential duplicates found"

    return summary, best_match


# ----------------------------------------------------------------
# Stage 5: Graph Sync — same Cypher as scripts/load_to_neo4j.py's run_load,
# scoped to this one patient instead of the demo subset. Every write is a
# MERGE, so re-running this stage for the same patient is always safe.
# ----------------------------------------------------------------

def _do_graph_sync_stage(patient_id: str):
    with engine.connect() as conn:
        patient_row = conn.execute(text("""
            SELECT patient_id, first_name, last_name, gender, birth_date
            FROM patients WHERE patient_id = :id
        """), {"id": patient_id}).fetchone()
        patient = dict(patient_row._mapping)

        pc_rows = conn.execute(text("""
            SELECT pc.patient_id, con.concept_id, con.concept_name, con.category, con.subcategory,
                   con.vocabulary_id, con.vocabulary_code, con.confidence, con.needs_review,
                   con.omop_concept_id, con.omop_standard_name, con.omop_domain, con.source_type
            FROM patient_concepts pc
            JOIN concepts con ON con.concept_id = pc.concept_id
            WHERE pc.patient_id = :id
        """), {"id": patient_id}).fetchall()
        patient_concept_links = [dict(r._mapping) for r in pc_rows]

        cr_rows = conn.execute(text("""
            SELECT cr.patient_id, cr.relationship_id,
                   pc1.concept_id AS local_concept_id_1,
                   pc2.concept_id AS local_concept_id_2
            FROM concept_relationships cr
            JOIN concepts c1 ON c1.omop_concept_id = cr.concept_id_1
            JOIN patient_concepts pc1 ON pc1.concept_id = c1.concept_id AND pc1.patient_id = cr.patient_id
            JOIN concepts c2 ON c2.omop_concept_id = cr.concept_id_2
            JOIN patient_concepts pc2 ON pc2.concept_id = c2.concept_id AND pc2.patient_id = cr.patient_id
            WHERE cr.patient_id = :id
        """), {"id": patient_id}).fetchall()
        clinical_relationships = [dict(r._mapping) for r in cr_rows]

    distinct_concepts = {row["concept_id"]: row for row in patient_concept_links}
    concepts_with_omop = [row for row in distinct_concepts.values() if row["omop_concept_id"] is not None]
    omop_nodes = {row["omop_concept_id"]: row for row in concepts_with_omop}

    patient_concept_by_type = {}
    for row in patient_concept_links:
        neo4j_type = map_source_type_to_relationship(row["source_type"])
        patient_concept_by_type.setdefault(neo4j_type, []).append(row)

    clinical_by_type = {}
    for row in clinical_relationships:
        neo4j_type = sanitize_relationship_type(row["relationship_id"])
        clinical_by_type.setdefault(neo4j_type, []).append(row)

    with get_neo4j_session() as session:
        session.run("""
            MERGE (p:Patient {patient_id: $patient_id})
            SET p.first_name = $first_name,
                p.last_name  = $last_name,
                p.birth_date = toString($birth_date),
                p.gender     = $gender
        """, patient)

        for concept in distinct_concepts.values():
            session.run("""
                MERGE (c:Concept {concept_id: $concept_id})
                SET c.concept_name   = $concept_name,
                    c.category       = $category,
                    c.subcategory    = $subcategory,
                    c.vocabulary_id  = $vocabulary_id,
                    c.vocabulary_code = $vocabulary_code,
                    c.confidence     = $confidence,
                    c.needs_review   = $needs_review
            """, concept)

        for omop_concept in omop_nodes.values():
            session.run("""
                MERGE (o:OMOPConcept {omop_concept_id: $omop_concept_id})
                SET o.standard_name = $omop_standard_name,
                    o.domain        = $omop_domain
            """, omop_concept)

        for neo4j_type, rows in patient_concept_by_type.items():
            # Relationship type can't be a bound Cypher parameter — safe as an
            # f-string here since map_source_type_to_relationship() only ever
            # returns one of a fixed literal set.
            query = f"""
                MATCH (p:Patient {{patient_id: $patient_id}})
                MATCH (c:Concept {{concept_id: $concept_id}})
                MERGE (p)-[:{neo4j_type}]->(c)
            """
            for row in rows:
                session.run(query, row)

        for concept in concepts_with_omop:
            session.run("""
                MATCH (c:Concept {concept_id: $concept_id})
                MATCH (o:OMOPConcept {omop_concept_id: $omop_concept_id})
                MERGE (c)-[:MAPS_TO]->(o)
            """, concept)

        for neo4j_type, rows in clinical_by_type.items():
            # Same reasoning as above — sanitize_relationship_type() guarantees
            # [A-Z0-9_]+ output, so this f-string is safe. patient_id is part
            # of the MERGE key itself (not just a later SET) since Concept
            # nodes are shared by name across patients.
            query = f"""
                MATCH (a:Concept {{concept_id: $local_concept_id_1}})
                MATCH (b:Concept {{concept_id: $local_concept_id_2}})
                MERGE (a)-[r:{neo4j_type} {{patient_id: $patient_id}}]->(b)
                SET r.relationship_id = $relationship_id
            """
            for row in rows:
                session.run(query, row)

    summary = (
        f"{len(distinct_concepts)} concept node(s), {len(omop_nodes)} OMOP mapping(s), "
        f"{len(clinical_relationships)} clinical relationship(s) synced to Neo4j"
    )
    return summary


# ----------------------------------------------------------------
# Pipeline runner
# ----------------------------------------------------------------

def _run_pipeline(job_id: str, file_path: Path, original_filename: str):
    try:
        _set_stage(job_id, "ingest", "running")
        patient_id, patient_name, ingest_summary = _do_ingest_stage(file_path, original_filename)
        _set_job_fields(job_id, patient_id=patient_id, patient_name=patient_name)
        _set_stage(job_id, "ingest", "success", summary=ingest_summary)
    except Exception as e:
        _set_stage(job_id, "ingest", "failure", error=str(e))
        return

    try:
        _set_stage(job_id, "classify", "running")
        classify_summary, newly_classified_names = _do_classify_stage(patient_id)
        _set_stage(job_id, "classify", "success", summary=classify_summary)
    except Exception as e:
        _set_stage(job_id, "classify", "failure", error=str(e))
        return

    try:
        _set_stage(job_id, "standardize_relate", "running")
        sr_summary = _do_standardize_relate_stage(patient_id, newly_classified_names)
        _set_stage(job_id, "standardize_relate", "success", summary=sr_summary)
    except Exception as e:
        _set_stage(job_id, "standardize_relate", "failure", error=str(e))
        return

    try:
        _set_stage(job_id, "identity_check", "running")
        ic_summary, duplicate_match = _do_identity_check_stage(patient_id)
        _set_job_fields(job_id, duplicate_match=duplicate_match)
        _set_stage(job_id, "identity_check", "success", summary=ic_summary)
    except Exception as e:
        _set_stage(job_id, "identity_check", "failure", error=str(e))
        return

    try:
        _set_stage(job_id, "graph_sync", "running")
        gs_summary = _do_graph_sync_stage(patient_id)
        _set_stage(job_id, "graph_sync", "success", summary=gs_summary)
    except Exception as e:
        _set_stage(job_id, "graph_sync", "failure", error=str(e))
        return

    # Makes this patient's flagged concepts/vocabulary mismatches visible in
    # Admin Review's Concept Review and Data Quality Review tabs, which are
    # otherwise scoped to a curated demo subset of patients.
    register_ingested_patient(patient_id)

    with engine.connect() as conn:
        flagged_count = conn.execute(text("""
            SELECT COUNT(*) FROM patient_concepts pc
            JOIN concepts con ON con.concept_id = pc.concept_id
            WHERE pc.patient_id = :id AND con.needs_review = TRUE
        """), {"id": patient_id}).scalar()

    notes = []
    if flagged_count > 0:
        notes.append(f"{flagged_count} concept{'s' if flagged_count != 1 else ''} flagged for review — visible in Admin Review")
    if duplicate_match:
        notes.append("Potential duplicate flagged — visible in Duplicate Review")
    complete_summary = " · ".join(notes) if notes else "No follow-up items — fully resolved, nothing pending review."
    _set_stage(job_id, "complete", "success", summary=complete_summary)


@router.post("/start")
async def start_ingestion(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Please upload a FHIR JSON bundle (.json file).")

    job_id = str(uuid.uuid4())
    dest_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
    contents = await file.read()
    dest_path.write_bytes(contents)

    with JOBS_LOCK:
        JOBS[job_id] = _new_job(file.filename)

    thread = threading.Thread(target=_run_pipeline, args=(job_id, dest_path, file.filename), daemon=True)
    thread.start()

    return {"job_id": job_id}


@router.get("/{job_id}")
def get_ingestion_status(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
