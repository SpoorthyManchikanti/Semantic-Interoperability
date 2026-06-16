"""Semantic normalization module.

Handles mapping of raw FHIR values to canonical concepts.
This enables semantic interoperability across different data sources.
"""

from typing import Dict, Optional


# Condition mappings - FHIR variations → Canonical concept
CONDITION_MAPPINGS: Dict[str, str] = {
    # Diabetes variants
    "Type II Diabetes": "Diabetes Mellitus Type 2",
    "T2DM": "Diabetes Mellitus Type 2",
    "Diabetes Mellitus": "Diabetes Mellitus Type 2",
    "Type 2 Diabetes": "Diabetes Mellitus Type 2",
    "NIDDM": "Diabetes Mellitus Type 2",
    
    # Hypertension variants
    "Hypertension": "Hypertension",
    "High Blood Pressure": "Hypertension",
    "HTN": "Hypertension",
    "Essential Hypertension": "Hypertension",
    
    # Asthma variants
    "Asthma": "Asthma",
    "Asthma - Uncontrolled": "Asthma",
    "Asthma - Intermittent": "Asthma",
    
    # Depression variants
    "Depression": "Major Depressive Disorder",
    "Major Depression": "Major Depressive Disorder",
    "Depressive Disorder": "Major Depressive Disorder",
    "MDD": "Major Depressive Disorder",
}

# Observation/Lab mappings
OBSERVATION_MAPPINGS: Dict[str, str] = {
    # Blood Pressure
    "Blood Pressure": "Blood Pressure",
    "Systolic blood pressure": "Blood Pressure Systolic",
    "Diastolic blood pressure": "Blood Pressure Diastolic",
    "BP": "Blood Pressure",
    
    # Glucose
    "Glucose": "Blood Glucose",
    "Fasting Glucose": "Blood Glucose Fasting",
    "HbA1c": "Hemoglobin A1c",
    "Glycated Hemoglobin": "Hemoglobin A1c",
    
    # Lipids
    "Total Cholesterol": "Total Cholesterol",
    "LDL": "LDL Cholesterol",
    "HDL": "HDL Cholesterol",
    "Triglycerides": "Triglycerides",
    
    # BMI
    "BMI": "Body Mass Index",
    "Body Mass Index": "Body Mass Index",
    "Weight": "Body Weight",
    "Height": "Body Height",
}

# Medication mappings
MEDICATION_MAPPINGS: Dict[str, str] = {
    # Diabetes meds
    "Metformin": "Metformin",
    "Insulin": "Insulin",
    "Glipizide": "Glipizide",
    "Lisinopril": "Lisinopril (ACE Inhibitor)",
    
    # Blood pressure meds
    "Amlodipine": "Amlodipine (Calcium Channel Blocker)",
    "Atenolol": "Atenolol (Beta Blocker)",
    
    # Antidepressants
    "Sertraline": "Sertraline (SSRI)",
    "Fluoxetine": "Fluoxetine (SSRI)",
    "Paroxetine": "Paroxetine (SSRI)",
    
    # Other common meds
    "Aspirin": "Aspirin",
    "Ibuprofen": "Ibuprofen",
}


def normalize_value(value: str, concept_type: str) -> str:
    """
    Normalize a raw value to its canonical form.
    
    Args:
        value: Raw value from FHIR data
        concept_type: Type of concept - "condition", "observation", "medication"
    
    Returns:
        Canonical concept name
    """
    if not value:
        return "Unknown"
    
    # Clean the input
    value = value.strip()
    
    # Select appropriate mapping
    if concept_type == "condition":
        return CONDITION_MAPPINGS.get(value, value)
    elif concept_type == "observation":
        return OBSERVATION_MAPPINGS.get(value, value)
    elif concept_type == "medication":
        return MEDICATION_MAPPINGS.get(value, value)
    else:
        return value


def normalize_condition(condition: str) -> str:
    """Normalize a condition name to canonical form."""
    return normalize_value(condition, "condition")


def normalize_observation(observation: str) -> str:
    """Normalize an observation name to canonical form."""
    return normalize_value(observation, "observation")


def normalize_medication(medication: str) -> str:
    """Normalize a medication name to canonical form."""
    return normalize_value(medication, "medication")


def get_canonical_concepts() -> Dict[str, list]:
    """Get all canonical concepts by type."""
    return {
        "conditions": list(set(CONDITION_MAPPINGS.values())),
        "observations": list(set(OBSERVATION_MAPPINGS.values())),
        "medications": list(set(MEDICATION_MAPPINGS.values())),
    }


def get_concept_variants(canonical: str) -> list:
    """Get all known variants of a canonical concept."""
    variants = []
    
    # Check conditions
    for variant, canonical_form in CONDITION_MAPPINGS.items():
        if canonical_form == canonical:
            variants.append({"type": "condition", "variant": variant})
    
    # Check observations
    for variant, canonical_form in OBSERVATION_MAPPINGS.items():
        if canonical_form == canonical:
            variants.append({"type": "observation", "variant": variant})
    
    # Check medications
    for variant, canonical_form in MEDICATION_MAPPINGS.items():
        if canonical_form == canonical:
            variants.append({"type": "medication", "variant": variant})
    
    return variants
