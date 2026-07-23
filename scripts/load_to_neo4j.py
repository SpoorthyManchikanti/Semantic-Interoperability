"""
Load the identity-resolution demo (15 real patients + 3 synthetic clones)
into Neo4j Aura.

Creates:
  (:Patient)  — patient_id, first_name, last_name, birth_date, gender
  (:Concept)  — concept_id, concept_name, category, subcategory,
                vocabulary_id, vocabulary_code, confidence, needs_review
  (:OMOPConcept) — omop_concept_id, standard_name, domain
      one per concept that resolved against Athena/OMOP (concepts.omop_concept_id
      is not null)
  (:Patient)-[:DIAGNOSED_WITH | :IS_ON_MEDICATION | :HAS_OBSERVATION]->(:Concept)
      for the 15 real patients only (the 3 synthetic clones have no
      clinical data, so no edges are created for them) — the relationship
      type is picked from the concept's source_type (condition/medication/
      observation) rather than one generic HAS_CONCEPT for everything, so
      the edge label itself says whether it's a diagnosis, a prescription,
      or a lab result. Anything with an unrecognized source_type falls
      back to HAS_CONCEPT (shouldn't happen given current data — a dry-run
      warning is printed listing any concepts that hit it).
  (:Patient)-[:POTENTIAL_DUPLICATE_OF {confidence, matched_on}]->(:Patient)
      one per patient_matches row, directed from the synthetic clone to
      the real patient it was generated from
  (:Concept)-[:MAPS_TO]->(:OMOPConcept)
      one per resolved concept
  (:Concept)-[:<SANITIZED_RELATIONSHIP_ID>]->(:Concept)
      one per row in concept_relationships (real, patient-scoped Athena
      clinical relationships — e.g. 'Is a' -> IS_A, 'Has due to' ->
      HAS_DUE_TO), resolved from concept_relationships' OMOP concept_id_1/
      concept_id_2 back to each patient's own local Concept node

By default this script only counts what it *would* create against
Postgres and checks that against Aura Free's limits (200K nodes /
400K relationships) — it does not touch Neo4j unless run with --execute.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from sqlalchemy import text
from neo4j import GraphDatabase

from app.database import engine

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

AURA_FREE_NODE_LIMIT = 200_000
AURA_FREE_REL_LIMIT = 400_000

# DEMO CODE — hardcoded to this specific demo's 15 real + 3 synthetic patients.
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

ALL_PATIENT_IDS = DEMO_SUBSET_IDS + SYNTHETIC_CLONE_IDS


SOURCE_TYPE_RELATIONSHIP_MAP = {
    "condition": "DIAGNOSED_WITH",
    "medication": "IS_ON_MEDICATION",
    "observation": "HAS_OBSERVATION",
}
HAS_CONCEPT_FALLBACK = "HAS_CONCEPT"


def map_source_type_to_relationship(source_type: str) -> str:
    """condition -> DIAGNOSED_WITH, medication -> IS_ON_MEDICATION,
    observation -> HAS_OBSERVATION. Anything else falls back to
    HAS_CONCEPT rather than failing loudly — the caller is responsible for
    surfacing a warning when the fallback gets used, since that means a
    source_type showed up that this mapping doesn't know about yet."""
    return SOURCE_TYPE_RELATIONSHIP_MAP.get(source_type, HAS_CONCEPT_FALLBACK)


def sanitize_relationship_type(relationship_id: str) -> str:
    """Turn an arbitrary Athena relationship_id string into a valid Neo4j
    relationship type: 'Is a' -> IS_A, 'Has due to' -> HAS_DUE_TO,
    'Has asso finding' -> HAS_ASSO_FINDING. One general rule, not a
    hardcoded per-value mapping, since Athena has ~300 distinct
    relationship_id values overall (we only use a handful here, but the
    rule has to hold for whichever ones show up)."""
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", relationship_id.strip()).strip("_").upper()
    return sanitized or "RELATED_TO"


def fetch_patients(conn):
    rows = conn.execute(text("""
        SELECT patient_id, first_name, last_name, gender, birth_date
        FROM patients
        WHERE patient_id = ANY(:ids)
    """), {"ids": ALL_PATIENT_IDS}).fetchall()
    return [dict(r._mapping) for r in rows]


def fetch_patient_concepts(conn):
    """One row per (patient, concept) link for the 15 real patients only."""
    rows = conn.execute(text("""
        SELECT
            pc.patient_id,
            con.concept_id, con.concept_name, con.category, con.subcategory,
            con.vocabulary_id, con.vocabulary_code, con.confidence, con.needs_review,
            con.omop_concept_id, con.omop_standard_name, con.omop_domain,
            con.source_type
        FROM patient_concepts pc
        JOIN concepts con ON con.concept_id = pc.concept_id
        WHERE pc.patient_id = ANY(:ids)
    """), {"ids": DEMO_SUBSET_IDS}).fetchall()
    return [dict(r._mapping) for r in rows]


def fetch_clinical_relationships(conn):
    """concept_relationships stores OMOP concept_id_1/concept_id_2, not our
    local concept_id — resolve each back to the specific local Concept node
    that this same patient actually has linked (via patient_concepts), so
    ambiguity from two local concepts sharing one OMOP id is scoped away."""
    rows = conn.execute(text("""
        SELECT
            cr.patient_id,
            cr.relationship_id,
            pc1.concept_id AS local_concept_id_1,
            pc2.concept_id AS local_concept_id_2
        FROM concept_relationships cr
        JOIN concepts c1 ON c1.omop_concept_id = cr.concept_id_1
        JOIN patient_concepts pc1 ON pc1.concept_id = c1.concept_id AND pc1.patient_id = cr.patient_id
        JOIN concepts c2 ON c2.omop_concept_id = cr.concept_id_2
        JOIN patient_concepts pc2 ON pc2.concept_id = c2.concept_id AND pc2.patient_id = cr.patient_id
        WHERE cr.patient_id = ANY(:ids)
    """), {"ids": DEMO_SUBSET_IDS}).fetchall()
    return [dict(r._mapping) for r in rows]


def fetch_patient_matches(conn):
    rows = conn.execute(text("""
        SELECT patient_id_1, patient_id_2, match_confidence, matched_on
        FROM patient_matches
        WHERE patient_id_1 = ANY(:demo_ids) AND patient_id_2 = ANY(:clone_ids)
    """), {"demo_ids": DEMO_SUBSET_IDS, "clone_ids": SYNTHETIC_CLONE_IDS}).fetchall()
    return [dict(r._mapping) for r in rows]


def compute_plan():
    with engine.connect() as conn:
        patients = fetch_patients(conn)
        patient_concept_links = fetch_patient_concepts(conn)
        matches = fetch_patient_matches(conn)
        clinical_relationships = fetch_clinical_relationships(conn)

    # Group by sanitized Neo4j relationship type, since Cypher requires the
    # relationship type as a literal in the query, not a bound parameter —
    # one MERGE query gets run per distinct type.
    clinical_by_type = {}
    for row in clinical_relationships:
        neo4j_type = sanitize_relationship_type(row["relationship_id"])
        clinical_by_type.setdefault(neo4j_type, []).append(row)

    # Same idea for patient->concept edges: group by the relationship type
    # derived from source_type, and separately track anything that fell
    # back to HAS_CONCEPT so it can be surfaced as a warning.
    patient_concept_by_type = {}
    has_concept_fallback_rows = []
    for row in patient_concept_links:
        neo4j_type = map_source_type_to_relationship(row["source_type"])
        patient_concept_by_type.setdefault(neo4j_type, []).append(row)
        if neo4j_type == HAS_CONCEPT_FALLBACK:
            has_concept_fallback_rows.append(row)

    distinct_concepts = {row["concept_id"]: row for row in patient_concept_links}

    # Concepts that resolved to an OMOP concept — one entry per Concept node,
    # used to drive MAPS_TO edges (341 concepts, not deduped: two different
    # local concepts can legitimately map to the same OMOP concept).
    concepts_with_omop_mapping = [
        row for row in distinct_concepts.values() if row["omop_concept_id"] is not None
    ]

    # Distinct OMOP concepts referenced above — used to drive OMOPConcept
    # node creation (339, deduped by omop_concept_id since MERGE would
    # collapse duplicates anyway; kept explicit here so the printed count
    # matches what actually gets created).
    omop_concept_nodes = {
        row["omop_concept_id"]: row for row in concepts_with_omop_mapping
    }

    plan = {
        "patients": patients,
        "patient_concept_links": patient_concept_links,
        "distinct_concepts": list(distinct_concepts.values()),
        "matches": matches,
        "concepts_with_omop_mapping": concepts_with_omop_mapping,
        "omop_concept_nodes": list(omop_concept_nodes.values()),
        "clinical_relationships": clinical_relationships,
        "clinical_by_type": clinical_by_type,
        "patient_concept_by_type": patient_concept_by_type,
        "has_concept_fallback_rows": has_concept_fallback_rows,
    }
    return plan


def print_plan_summary(plan):
    patient_node_count = len(plan["patients"])
    concept_node_count = len(plan["distinct_concepts"])
    omop_concept_node_count = len(plan["omop_concept_nodes"])
    has_concept_rel_count = len(plan["patient_concept_links"])
    duplicate_rel_count = len(plan["matches"])
    maps_to_rel_count = len(plan["concepts_with_omop_mapping"])
    clinical_rel_count = len(plan["clinical_relationships"])

    total_nodes = patient_node_count + concept_node_count + omop_concept_node_count
    total_rels = has_concept_rel_count + duplicate_rel_count + maps_to_rel_count + clinical_rel_count

    print("=" * 60)
    print("Neo4j load plan (Postgres counts, nothing written yet)")
    print("=" * 60)
    print(f"  Patient nodes:                 {patient_node_count} (15 real + 3 synthetic)")
    print(f"  Concept nodes:                 {concept_node_count}")
    print(f"  OMOPConcept nodes:             {omop_concept_node_count}")
    print(f"  Patient->Concept relationships: {has_concept_rel_count} (by source_type)")
    for neo4j_type, rows in sorted(plan["patient_concept_by_type"].items(), key=lambda kv: -len(kv[1])):
        print(f"    {neo4j_type:<24} {len(rows)}")
    fallback_count = len(plan["has_concept_fallback_rows"])
    if fallback_count:
        print(f"  WARNING: {fallback_count} concept(s) fell back to HAS_CONCEPT (unrecognized source_type):")
        for row in plan["has_concept_fallback_rows"]:
            print(f"    - {row['concept_name']!r} (source_type={row['source_type']!r}, patient_id={row['patient_id']})")
    else:
        print(f"  HAS_CONCEPT fallback count:    0")
    print(f"  POTENTIAL_DUPLICATE_OF rels:   {duplicate_rel_count}")
    print(f"  MAPS_TO relationships:         {maps_to_rel_count}")
    print(f"  Clinical relationships:        {clinical_rel_count} (from concept_relationships)")
    for neo4j_type, rows in sorted(plan["clinical_by_type"].items(), key=lambda kv: -len(kv[1])):
        print(f"    {neo4j_type:<24} {len(rows)}")
    print("-" * 60)
    print(f"  TOTAL NODES:                   {total_nodes}")
    print(f"  TOTAL RELATIONSHIPS:           {total_rels}")
    print("-" * 60)
    print(f"  Aura Free node limit:          {AURA_FREE_NODE_LIMIT:,} "
          f"({total_nodes / AURA_FREE_NODE_LIMIT * 100:.4f}% used)")
    print(f"  Aura Free relationship limit:  {AURA_FREE_REL_LIMIT:,} "
          f"({total_rels / AURA_FREE_REL_LIMIT * 100:.4f}% used)")
    print("=" * 60)

    within_limits = total_nodes <= AURA_FREE_NODE_LIMIT and total_rels <= AURA_FREE_REL_LIMIT
    print("Within Aura Free limits: " + ("YES" if within_limits else "NO"))
    return within_limits


def run_load(plan):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            for patient in plan["patients"]:
                session.run("""
                    MERGE (p:Patient {patient_id: $patient_id})
                    SET p.first_name = $first_name,
                        p.last_name  = $last_name,
                        p.birth_date = toString($birth_date),
                        p.gender     = $gender
                """, patient)

            for concept in plan["distinct_concepts"]:
                session.run("""
                    MERGE (c:Concept {concept_id: $concept_id})
                    SET c.concept_name    = $concept_name,
                        c.category        = $category,
                        c.subcategory     = $subcategory,
                        c.vocabulary_id    = $vocabulary_id,
                        c.vocabulary_code  = $vocabulary_code,
                        c.confidence       = $confidence,
                        c.needs_review     = $needs_review
                """, concept)

            for omop_concept in plan["omop_concept_nodes"]:
                session.run("""
                    MERGE (o:OMOPConcept {omop_concept_id: $omop_concept_id})
                    SET o.standard_name = $omop_standard_name,
                        o.domain        = $omop_domain
                """, omop_concept)

            for neo4j_type, rows in plan["patient_concept_by_type"].items():
                # Same reasoning as the clinical-relationship loop below:
                # type can't be a bound parameter, so one query per type.
                # map_source_type_to_relationship() only ever returns one of
                # DIAGNOSED_WITH/IS_ON_MEDICATION/HAS_OBSERVATION/HAS_CONCEPT
                # (a fixed literal set), so this f-string is safe.
                query = f"""
                    MATCH (p:Patient {{patient_id: $patient_id}})
                    MATCH (c:Concept {{concept_id: $concept_id}})
                    MERGE (p)-[:{neo4j_type}]->(c)
                """
                for row in rows:
                    session.run(query, row)

            for concept in plan["concepts_with_omop_mapping"]:
                session.run("""
                    MATCH (c:Concept {concept_id: $concept_id})
                    MATCH (o:OMOPConcept {omop_concept_id: $omop_concept_id})
                    MERGE (c)-[:MAPS_TO]->(o)
                """, concept)

            for neo4j_type, rows in plan["clinical_by_type"].items():
                # Relationship type can't be a bound parameter in Cypher, so
                # one query runs per sanitized type. sanitize_relationship_type()
                # guarantees [A-Z0-9_]+ output, so this f-string is safe.
                #
                # patient_id must be part of the MERGE pattern itself, not
                # just a later SET — local concept_ids are shared by name
                # across patients (e.g. many patients have "Type 2 diabetes
                # mellitus" as the same Concept node), so the same
                # (a, TYPE, b) triple can legitimately recur for different
                # patients. Without patient_id in the MERGE key, Neo4j
                # collapses those into one shared edge and silently
                # overwrites patient_id with whichever patient loaded last.
                query = f"""
                    MATCH (a:Concept {{concept_id: $local_concept_id_1}})
                    MATCH (b:Concept {{concept_id: $local_concept_id_2}})
                    MERGE (a)-[r:{neo4j_type} {{patient_id: $patient_id}}]->(b)
                    SET r.relationship_id = $relationship_id
                """
                for row in rows:
                    session.run(query, row)

            for match in plan["matches"]:
                # matched_on is a JSON object in Postgres; Neo4j relationship
                # properties can't hold nested maps, so it's stored as a
                # JSON string here.
                session.run("""
                    MATCH (clone:Patient {patient_id: $patient_id_2})
                    MATCH (original:Patient {patient_id: $patient_id_1})
                    MERGE (clone)-[r:POTENTIAL_DUPLICATE_OF]->(original)
                    SET r.confidence = $match_confidence,
                        r.matched_on = $matched_on
                """, {
                    "patient_id_1": match["patient_id_1"],
                    "patient_id_2": match["patient_id_2"],
                    "match_confidence": match["match_confidence"],
                    "matched_on": json.dumps(match["matched_on"]),
                })

        print("Load complete.")
    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                         help="Actually write to Neo4j. Without this flag, only prints counts.")
    args = parser.parse_args()

    plan = compute_plan()
    within_limits = print_plan_summary(plan)

    if not args.execute:
        print("\nDry run only — no data written to Neo4j. Re-run with --execute to load.")
        return

    if not within_limits:
        print("\nRefusing to load: plan exceeds Aura Free limits.")
        sys.exit(1)

    run_load(plan)


if __name__ == "__main__":
    main()
