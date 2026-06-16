"""Pydantic schemas for semantic interoperability API responses."""

from typing import List, Optional
from pydantic import BaseModel


class ConceptBase(BaseModel):
    """Canonical semantic concept."""
    concept_id: str
    concept_name: str
    concept_type: str  # e.g., "condition", "observation", "medication"
    description: Optional[str] = None


class ConceptResponse(ConceptBase):
    """Concept response with metadata."""
    variant_count: int
    patient_count: int

    class Config:
        from_attributes = True


class PatientBase(BaseModel):
    """Patient demographic."""
    patient_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None


class PatientCondition(BaseModel):
    """Patient condition record."""
    condition_id: int
    condition_name: str
    canonical_concept: Optional[str] = None


class PatientObservation(BaseModel):
    """Patient observation record."""
    observation_id: int
    observation_name: str
    observation_value: Optional[str] = None
    canonical_concept: Optional[str] = None


class PatientMedication(BaseModel):
    """Patient medication record."""
    medication_id: int
    medication_name: str
    canonical_concept: Optional[str] = None


class PatientProfile(PatientBase):
    """Complete semantic patient profile."""
    conditions: List[PatientCondition] = []
    observations: List[PatientObservation] = []
    medications: List[PatientMedication] = []

    class Config:
        from_attributes = True


class SemanticSummary(BaseModel):
    """High-level semantic profile statistics."""
    total_patients: int
    total_concepts: int
    concept_distribution: dict
    data_quality_score: float
