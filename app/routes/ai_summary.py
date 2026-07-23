"""AI-generated executive summary for a patient's semantic profile.

Two-step pipeline:
  Step A (structured extraction) — one LLM call over this patient's real
  classified concepts plus their needs_review count and patient_matches
  status, returning strict JSON (chief_complaints, active_problems,
  active_medications, risk_flags). risk_flags are computed here from real
  data (needs_review=true concepts, unreviewed patient_matches rows) and
  handed to the model as a fixed, verbatim list — the model is instructed
  to echo them, not invent its own.

  Step B (narrative) — a second LLM call given ONLY Step A's JSON (not the
  raw patient rows again) writes the final 3-4 sentence prose summary.

Both the structured JSON and the narrative are cached together in
patient_profiles.profile_json (already a flexible JSONB column — no schema
migration needed to hold both).
"""

import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from openai import AzureOpenAI
from sqlalchemy import text

from app.database import engine

load_dotenv()

router = APIRouter(tags=["ai-summary"])

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-08-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

PROFILE_CACHE_HOURS = 24


def _fetch_patient_concepts(conn, patient_id):
    return conn.execute(text("""
        SELECT con.concept_name, con.source_type, con.category, con.subcategory, con.confidence,
               con.omop_standard_name, con.omop_concept_id, con.needs_review
        FROM patient_concepts pc
        JOIN concepts con ON con.concept_id = pc.concept_id
        WHERE pc.patient_id = :id
        ORDER BY con.source_type, con.category
    """), {"id": patient_id}).fetchall()


# Causal/associative Athena relationship types only — a real complication or
# clinical association, not a pure taxonomic Is a/Subsumes category pair
# (e.g. "Gingival disease"/"Gingivitis" is a real documented relationship,
# but it's just a category hierarchy, not evidence this patient has a
# complication).
CAUSAL_RELATIONSHIP_TYPES = [
    "Has due to", "Due to of",
    "Has asso finding", "Asso finding of",
    "Has asso morph", "Asso morph of",
]


def _fetch_related_condition_omop_ids(conn, patient_id):
    """OMOP concept_ids that appear (in either direction) in this patient's
    real, Athena-documented concept_relationships rows — restricted to
    causal/associative relationship types (see CAUSAL_RELATIONSHIP_TYPES).
    Pure Is a/Subsumes taxonomic pairs don't count here; they still show up
    as a documented relationship, just not as evidence of a complication."""
    rows = conn.execute(text("""
        SELECT concept_id_1 AS concept_id FROM concept_relationships
        WHERE patient_id = :id AND relationship_id = ANY(:types)
        UNION
        SELECT concept_id_2 AS concept_id FROM concept_relationships
        WHERE patient_id = :id AND relationship_id = ANY(:types)
    """), {"id": patient_id, "types": CAUSAL_RELATIONSHIP_TYPES}).fetchall()
    return {r.concept_id for r in rows}


def _fetch_unreviewed_duplicate_matches(conn, patient_id):
    """Includes the *other* patient's name (not this one's) so risk flags can
    read e.g. 'potential duplicate of Carl85 Sporer811' without the frontend
    needing a second lookup."""
    rows = conn.execute(text("""
        SELECT pm.match_confidence,
               CASE WHEN pm.patient_id_1 = :id THEN pm.patient_id_2 ELSE pm.patient_id_1 END AS other_patient_id
        FROM patient_matches pm
        WHERE (pm.patient_id_1 = :id OR pm.patient_id_2 = :id) AND pm.reviewed = FALSE
    """), {"id": patient_id}).fetchall()

    matches = []
    for r in rows:
        other = conn.execute(text(
            "SELECT first_name, last_name FROM patients WHERE patient_id = :id"
        ), {"id": r.other_patient_id}).fetchone()
        matches.append({
            "match_confidence": r.match_confidence,
            "other_patient_id": r.other_patient_id,
            "other_patient_name": f"{other.first_name} {other.last_name}" if other else "Unknown patient",
        })
    return matches


def _compute_risk_flags(concepts_rows, duplicate_matches):
    """Real, computed risk flags — these are set directly from Postgres and
    never left to the model to invent or reformat (Step A's LLM call gets
    them as read-only context; the final stored risk_flags always come from
    here, not from the LLM's JSON, so counts/names can't drift)."""
    flags = []
    # Same exclusion GET /concepts/needs-review applies: the 'Unknown'
    # fallback (category='General', subcategory='Unknown / Invalid Concept')
    # means the source data was missing/invalid, not a genuine classification
    # call for a human to weigh in on — so it shouldn't inflate this count.
    # Keeping this in sync with that endpoint is what makes clicking through
    # from this flag to Admin Review's filtered view land on a matching count.
    needs_review_count = sum(
        1 for r in concepts_rows
        if r.needs_review and not (r.category == "General" and r.subcategory == "Unknown / Invalid Concept")
    )
    if needs_review_count > 0:
        flags.append({
            "type": "needs_review",
            "count": needs_review_count,
            "description": f"{needs_review_count} concept(s) below the confidence threshold, pending human review",
        })
    for m in duplicate_matches:
        flags.append({
            "type": "potential_duplicate",
            "other_patient_id": m["other_patient_id"],
            "other_patient_name": m["other_patient_name"],
            "match_confidence": round(m["match_confidence"] * 100),
            "description": f"Flagged as a potential duplicate identity of {m['other_patient_name']} "
                            f"(match confidence {round(m['match_confidence'] * 100)}%), pending review",
        })
    return flags


PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _build_active_problems(concepts_rows, related_condition_omop_ids):
    """Real, computed priority — never left to the model.

      high:   has a documented concept_relationships link to another
              condition this patient has, of a causal/associative type
              (CAUSAL_RELATIONSHIP_TYPES — Has due to/Due to of, Has asso
              finding/Asso finding of, Has asso morph/Asso morph of). This is
              the ONLY path to high — confidence can no longer grant it on
              its own (a confidence-based boost swamped the signal when this
              dataset averages ~98% confidence), and pure taxonomic Is
              a/Subsumes pairs (e.g. "Gingival disease"/"Gingivitis") don't
              qualify either — a category hierarchy isn't a complication.
      medium: no qualifying causal relationship, but confidence >= 0.90 and
              not an administrative '(situation)' SNOMED concept. This
              includes conditions whose only documented relationship is a
              taxonomic Is a/Subsumes pair — still real, just not causal.
      low:    everything else (administrative situations, or low-confidence
              findings with no qualifying relationship).

    Sorted high -> medium -> low."""
    conditions = [r for r in concepts_rows if r.source_type == "condition"]
    problems = []
    for r in conditions:
        has_relationship = bool(r.omop_concept_id and r.omop_concept_id in related_condition_omop_ids)
        is_situation = "(situation)" in r.concept_name.lower()
        decent_confidence = r.confidence is not None and r.confidence >= 0.90

        if has_relationship:
            priority = "high"
        elif decent_confidence and not is_situation:
            priority = "medium"
        else:
            priority = "low"

        problems.append({
            "name": r.concept_name,
            "category": r.category or "unclassified",
            "confidence": round(r.confidence * 100) if r.confidence is not None else None,
            "priority": priority,
        })

    problems.sort(key=lambda p: PRIORITY_RANK[p["priority"]])
    return problems


def _fmt_concepts(rows):
    lines = []
    for r in rows:
        conf = f", confidence {round(r.confidence * 100)}%" if r.confidence is not None else ""
        omop = f", OMOP: {r.omop_standard_name}" if r.omop_standard_name else ""
        lines.append(f"- {r.concept_name} (category: {r.category or 'unclassified'}{omop}{conf})")
    return "\n".join(lines) or "- none recorded"


def _extract_structured(concepts_rows, risk_flags):
    """Step A: structured JSON extraction from real classified concepts."""
    conditions = [r for r in concepts_rows if r.source_type == "condition"]
    medications = [r for r in concepts_rows if r.source_type == "medication"]
    observations = [r for r in concepts_rows if r.source_type == "observation"]

    prompt = f"""You are a clinical informatics AI extracting structured data from a
patient's semantically classified health record. Output ONLY valid JSON, no markdown,
matching exactly this shape:

{{
  "chief_complaints": [string, ...],
  "active_problems": [{{"name": string, "category": string, "confidence": number|null}}, ...],
  "active_medications": [{{"name": string, "omop_standard_name": string|null}}, ...],
  "risk_flags": [{{"type": string, "description": string}}, ...]
}}

Conditions:
{_fmt_concepts(conditions)}

Medications:
{_fmt_concepts(medications)}

Observations:
{_fmt_concepts(observations)}

Known risk flags (copy these into risk_flags verbatim — do not omit, alter, or
invent any additional risk flags beyond this exact list):
{json.dumps(risk_flags) if risk_flags else "none"}

Rules:
- chief_complaints: the 1-3 most clinically significant conditions, by name only.
- active_problems: every condition listed above, each with its category and confidence.
- active_medications: every medication listed above, with its OMOP standard name if present (else null).
- risk_flags: exactly the "Known risk flags" list above, verbatim.
- Do not invent any clinical information not present above."""

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def _write_narrative(structured):
    """Step B: narrative written from ONLY the Step A JSON, no raw patient data.
    No trailing 'Source: ...' line — data provenance is shown via the patient
    header badge on the page, not repeated in this prose."""
    prompt = f"""You are a clinical informatics AI writing a short executive summary from
the ALREADY-EXTRACTED structured patient data below. Use only this JSON — no other
information about the patient is available to you:

{json.dumps(structured, indent=2)}

Write a 3-4 sentence executive summary in plain prose (no markdown, no bullet points)
covering the patient's chief complaints, active medications, and any risk flags present.
Do not invent information not present in the JSON above. Do not mention data source or
provenance — end the summary after the clinical content, with no trailing line about
where the data came from."""

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


@router.get("/patients/{patient_id}/ai-summary")
def get_ai_summary(patient_id: str):
    """Two-step AI summary — see module docstring. Caches {structured, summary}
    together in patient_profiles.profile_json; a cached profile younger than
    24 hours is returned as-is instead of regenerating."""
    with engine.connect() as conn:
        patient_row = conn.execute(text("""
            SELECT patient_id, first_name, last_name, gender, data_source FROM patients WHERE patient_id = :id
        """), {"id": patient_id}).fetchone()

        if not patient_row:
            raise HTTPException(status_code=404, detail="Patient not found")

        cached = conn.execute(text(f"""
            SELECT profile_json FROM patient_profiles
            WHERE patient_id = :id
              AND updated_at > NOW() - INTERVAL '{PROFILE_CACHE_HOURS} hours'
        """), {"id": patient_id}).fetchone()

        if cached:
            result = dict(cached.profile_json)
            result["cached"] = True
            return result

        concepts_rows = _fetch_patient_concepts(conn, patient_id)
        duplicate_matches = _fetch_unreviewed_duplicate_matches(conn, patient_id)
        related_condition_omop_ids = _fetch_related_condition_omop_ids(conn, patient_id)

    if not concepts_rows:
        return {
            "structured": None,
            "summary": "No classified clinical data is available yet for this patient.",
            "confidence": None,
        }

    risk_flags = _compute_risk_flags(concepts_rows, duplicate_matches)
    structured = _extract_structured(concepts_rows, risk_flags)
    # Always the real, Python-computed values — not whatever the model
    # echoed back — so flags/priority can never drift from what's actually
    # in Postgres.
    structured["risk_flags"] = risk_flags
    structured["active_problems"] = _build_active_problems(concepts_rows, related_condition_omop_ids)
    narrative = _write_narrative(structured)

    all_conf = [r.confidence for r in concepts_rows if r.confidence is not None]
    avg_confidence = round(sum(all_conf) / len(all_conf) * 100, 1) if all_conf else None

    result = {
        "structured": structured,
        "summary": narrative,
        "confidence": avg_confidence,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO patient_profiles (patient_id, profile_json, updated_at)
            VALUES (:patient_id, CAST(:profile_json AS JSONB), NOW())
            ON CONFLICT (patient_id) DO UPDATE
            SET profile_json = EXCLUDED.profile_json,
                updated_at = NOW()
        """), {"patient_id": patient_id, "profile_json": json.dumps(result)})

    result["cached"] = False
    return result


@router.get("/patients/{patient_id}/risk-flags")
def get_patient_risk_flags(patient_id: str):
    """Read-only: whatever risk_flags are already sitting in this patient's
    cached profile_json, straight from Postgres — never triggers AI summary
    generation. Returns [] if no cached profile exists yet (most of the
    non-demo patient population) or if the cached profile has none, so the
    caller can render nothing rather than an empty box."""
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT profile_json -> 'structured' -> 'risk_flags' AS risk_flags
            FROM patient_profiles
            WHERE patient_id = :id
        """), {"id": patient_id}).fetchone()

    if not row or not row.risk_flags:
        return []
    return row.risk_flags
