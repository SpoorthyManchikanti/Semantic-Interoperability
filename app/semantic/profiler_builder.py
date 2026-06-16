"""Semantic profile builder and data quality analyzer.

Analyzes loaded FHIR data and generates semantic profiles.
"""

from sqlalchemy import text
from app.database import engine
from app.semantic.normalizer import (
    normalize_condition,
    normalize_observation,
    normalize_medication
)


def build_condition_profile() -> dict:
    """Analyze condition data and build semantic profile."""
    with engine.begin() as conn:
        result = conn.execute(
            text("""
            SELECT condition_name, COUNT(*) as patient_count
            FROM conditions
            GROUP BY condition_name
            ORDER BY patient_count DESC
            """)
        )
        
        conditions = {}
        for row in result.fetchall():
            raw_name = row.condition_name
            canonical = normalize_condition(raw_name)
            
            if canonical not in conditions:
                conditions[canonical] = {
                    "canonical": canonical,
                    "variants": [],
                    "total_patients": 0
                }
            
            conditions[canonical]["variants"].append({
                "variant": raw_name,
                "patient_count": row.patient_count
            })
            conditions[canonical]["total_patients"] += row.patient_count
        
        return conditions


def build_observation_profile() -> dict:
    """Analyze observation data and build semantic profile."""
    with engine.begin() as conn:
        result = conn.execute(
            text("""
            SELECT observation_name, COUNT(*) as observation_count
            FROM observations
            GROUP BY observation_name
            ORDER BY observation_count DESC
            """)
        )
        
        observations = {}
        for row in result.fetchall():
            raw_name = row.observation_name
            canonical = normalize_observation(raw_name)
            
            if canonical not in observations:
                observations[canonical] = {
                    "canonical": canonical,
                    "variants": [],
                    "total_observations": 0
                }
            
            observations[canonical]["variants"].append({
                "variant": raw_name,
                "count": row.observation_count
            })
            observations[canonical]["total_observations"] += row.observation_count
        
        return observations


def build_medication_profile() -> dict:
    """Analyze medication data and build semantic profile."""
    with engine.begin() as conn:
        result = conn.execute(
            text("""
            SELECT medication_name, COUNT(*) as patient_count
            FROM medications
            GROUP BY medication_name
            ORDER BY patient_count DESC
            """)
        )
        
        medications = {}
        for row in result.fetchall():
            raw_name = row.medication_name
            canonical = normalize_medication(raw_name)
            
            if canonical not in medications:
                medications[canonical] = {
                    "canonical": canonical,
                    "variants": [],
                    "total_patients": 0
                }
            
            medications[canonical]["variants"].append({
                "variant": raw_name,
                "patient_count": row.patient_count
            })
            medications[canonical]["total_patients"] += row.patient_count
        
        return medications


def calculate_data_quality() -> dict:
    """Calculate overall data quality metrics."""
    with engine.begin() as conn:
        # Patient counts
        total_patients = conn.execute(text("SELECT COUNT(*) FROM patients")).scalar()
        patients_with_conditions = conn.execute(
            text("SELECT COUNT(DISTINCT patient_id) FROM conditions")
        ).scalar()
        patients_with_observations = conn.execute(
            text("SELECT COUNT(DISTINCT patient_id) FROM observations")
        ).scalar()
        patients_with_medications = conn.execute(
            text("SELECT COUNT(DISTINCT patient_id) FROM medications")
        ).scalar()
        
        # Calculate completeness scores (0-1)
        condition_completeness = patients_with_conditions / total_patients if total_patients > 0 else 0
        observation_completeness = patients_with_observations / total_patients if total_patients > 0 else 0
        medication_completeness = patients_with_medications / total_patients if total_patients > 0 else 0
        
        # Overall quality score
        quality_score = (
            condition_completeness * 0.4 +
            observation_completeness * 0.3 +
            medication_completeness * 0.3
        )
        
        return {
            "total_patients": total_patients,
            "completeness": {
                "conditions": round(condition_completeness, 2),
                "observations": round(observation_completeness, 2),
                "medications": round(medication_completeness, 2)
            },
            "overall_quality_score": round(quality_score, 2)
        }


def build_complete_profile() -> dict:
    """Build complete semantic profile of the dataset."""
    return {
        "conditions": build_condition_profile(),
        "observations": build_observation_profile(),
        "medications": build_medication_profile(),
        "data_quality": calculate_data_quality()
    }


def print_profile_summary():
    """Print a human-readable summary of the semantic profile."""
    profile = build_complete_profile()
    
    print("\n" + "=" * 70)
    print("SEMANTIC DATA PROFILE")
    print("=" * 70)
    
    # Data quality
    quality = profile["data_quality"]
    print(f"\nData Quality Score: {quality['overall_quality_score']}")
    print(f"  Total Patients: {quality['total_patients']}")
    print(f"  Conditions Coverage: {quality['completeness']['conditions'] * 100:.1f}%")
    print(f"  Observations Coverage: {quality['completeness']['observations'] * 100:.1f}%")
    print(f"  Medications Coverage: {quality['completeness']['medications'] * 100:.1f}%")
    
    # Conditions
    print(f"\nConditions ({len(profile['conditions'])} unique):")
    for i, (canonical, data) in enumerate(sorted(
        profile['conditions'].items(),
        key=lambda x: x[1]['total_patients'],
        reverse=True
    )[:10]):
        print(f"  {i+1}. {canonical} ({data['total_patients']} patients)")
    
    # Observations
    print(f"\nObservations ({len(profile['observations'])} unique):")
    for i, (canonical, data) in enumerate(sorted(
        profile['observations'].items(),
        key=lambda x: x[1]['total_observations'],
        reverse=True
    )[:10]):
        print(f"  {i+1}. {canonical} ({data['total_observations']} records)")
    
    # Medications
    print(f"\nMedications ({len(profile['medications'])} unique):")
    for i, (canonical, data) in enumerate(sorted(
        profile['medications'].items(),
        key=lambda x: x[1]['total_patients'],
        reverse=True
    )[:10]):
        print(f"  {i+1}. {canonical} ({data['total_patients']} patients)")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    print_profile_summary()
