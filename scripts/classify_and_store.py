#!/usr/bin/env python3
"""
Classify clinical concepts from the database using Azure OpenAI and store results.

Usage:
    python scripts/classify_and_store.py --type conditions    # Classify all condition names
    python scripts/classify_and_store.py --type observations  # Classify all observation names
    python scripts/classify_and_store.py --type medications   # Classify all medication names
    python scripts/classify_and_store.py --type all           # Classify all of the above
"""

import sys
import argparse
from sqlalchemy import text, select
from app.database import SessionLocal, engine
from app.models import conditions, observations, medications, semantic_concepts, concept_mappings
from app.agents.semantic_classifier import classify_concept

def get_unique_concepts(session, concept_type):
    """Fetch unique concept names from the database."""
    if concept_type == "conditions":
        query = select(conditions.c.condition_name).distinct()
    elif concept_type == "observations":
        query = select(observations.c.observation_name).distinct()
    elif concept_type == "medications":
        query = select(medications.c.medication_name).distinct()
    else:
        raise ValueError(f"Unknown concept type: {concept_type}")
    
    result = session.execute(query)
    return [row[0] for row in result if row[0]]  # Filter out None values


def concept_exists(session, concept_name):
    """Check if a concept already exists in semantic_concepts table."""
    query = select(semantic_concepts).where(semantic_concepts.c.concept_name == concept_name)
    result = session.execute(query)
    return result.fetchone() is not None


def classify_and_store(session, concept_name, concept_type):
    """Classify a concept and store it in the database."""
    try:
        # Skip if already classified
        if concept_exists(session, concept_name):
            print(f"✓ Already classified: {concept_name}")
            return True
        
        # Classify using Azure OpenAI
        print(f"Classifying: {concept_name}...", end=" ")
        classification = classify_concept(concept_name)
        
        # Generate concept_id from name (e.g., "Blood Pressure" -> "blood_pressure")
        concept_id = concept_name.lower().replace(" ", "_").replace("/", "_")
        
        # Insert into semantic_concepts
        insert_concept = semantic_concepts.insert().values(
            concept_id=concept_id,
            concept_name=concept_name,
            concept_type=concept_type,
            description=f"Category: {classification['category']}, Confidence: {classification['confidence']}"
        )
        session.execute(insert_concept)
        
        # Insert into concept_mappings (raw -> semantic mapping)
        insert_mapping = concept_mappings.insert().values(
            concept_id=concept_id,
            source_value=concept_name,
            source_system="FHIR",
            confidence=classification['confidence']
        )
        session.execute(insert_mapping)
        
        session.commit()
        print(f"✓ {classification['category']} (confidence: {classification['confidence']})")
        return True
        
    except Exception as e:
        session.rollback()
        print(f"✗ Error: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Classify clinical concepts and store in database")
    parser.add_argument(
        "--type",
        choices=["conditions", "observations", "medications", "all"],
        default="all",
        help="Type of concepts to classify"
    )
    
    args = parser.parse_args()
    
    session = SessionLocal()
    
    try:
        concept_types = ["conditions", "observations", "medications"] if args.type == "all" else [args.type]
        
        for concept_type in concept_types:
            print(f"\n{'='*60}")
            print(f"Classifying {concept_type.upper()}")
            print(f"{'='*60}")
            
            concepts = get_unique_concepts(session, concept_type)
            print(f"Found {len(concepts)} unique {concept_type}\n")
            
            success_count = 0
            for concept_name in concepts:
                if classify_and_store(session, concept_name, concept_type):
                    success_count += 1
            
            print(f"\n✓ Successfully classified {success_count}/{len(concepts)}")
        
        print(f"\n{'='*60}")
        print("Classification complete!")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
