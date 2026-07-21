"""Patient identity resolution — read-only match flagging.

Scores pairs of patient records for likely-duplicate identity based on
name similarity, date of birth, and gender. This module never merges or
mutates records; it only produces a score and a list of flagged pairs
for a human to review.
"""

from itertools import combinations
from typing import Any, Dict, List, Optional

import jellyfish

NAME_WEIGHT = 0.4
DOB_WEIGHT = 0.4
GENDER_WEIGHT = 0.2

DEFAULT_MATCH_THRESHOLD = 0.85


def _full_name(patient: Dict[str, Any]) -> str:
    first = (patient.get("first_name") or "").strip().lower()
    last = (patient.get("last_name") or "").strip().lower()
    return f"{first} {last}".strip()


def _name_similarity(patient_a: Dict[str, Any], patient_b: Dict[str, Any]) -> float:
    name_a = _full_name(patient_a)
    name_b = _full_name(patient_b)
    if not name_a or not name_b:
        return 0.0
    return jellyfish.jaro_winkler_similarity(name_a, name_b)


def _dob_match(patient_a: Dict[str, Any], patient_b: Dict[str, Any]) -> float:
    dob_a = patient_a.get("birth_date")
    dob_b = patient_b.get("birth_date")
    if not dob_a or not dob_b:
        return 0.0
    return 1.0 if str(dob_a) == str(dob_b) else 0.0


def _gender_match(patient_a: Dict[str, Any], patient_b: Dict[str, Any]) -> float:
    gender_a = (patient_a.get("gender") or "").strip().lower()
    gender_b = (patient_b.get("gender") or "").strip().lower()
    if not gender_a or not gender_b:
        return 0.0
    return 1.0 if gender_a == gender_b else 0.0


def match_breakdown(patient_a: Dict[str, Any], patient_b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Per-field detail behind a match_score, for audit/display purposes
    (e.g. a matched_on column) — which signals contributed and how.
    """
    return {
        "name_similarity": round(_name_similarity(patient_a, patient_b), 4),
        "dob_match": _dob_match(patient_a, patient_b) == 1.0,
        "gender_match": _gender_match(patient_a, patient_b) == 1.0,
    }


def match_score(patient_a: Dict[str, Any], patient_b: Dict[str, Any]) -> float:
    """
    Score how likely two patient records refer to the same person.

    Weighted: name similarity via Jaro-Winkler (40%), DOB exact match (40%),
    gender exact match (20%). Returns a float in [0.0, 1.0].
    """
    score = (
        NAME_WEIGHT * _name_similarity(patient_a, patient_b)
        + DOB_WEIGHT * _dob_match(patient_a, patient_b)
        + GENDER_WEIGHT * _gender_match(patient_a, patient_b)
    )
    return max(0.0, min(1.0, score))


def find_potential_matches(
    patients: List[Dict[str, Any]],
    threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Compare every pair of patients in the given list and flag pairs whose
    match_score is >= threshold. Does not merge or modify any records —
    this only returns candidate pairs for manual review.

    Returns a list of dicts sorted by score descending:
    {patient_a_id, patient_b_id, score, matched_on}
    """
    flagged: List[Dict[str, Any]] = []

    for patient_a, patient_b in combinations(patients, 2):
        score = match_score(patient_a, patient_b)
        if score >= threshold:
            flagged.append({
                "patient_a_id": patient_a.get("patient_id"),
                "patient_b_id": patient_b.get("patient_id"),
                "score": round(score, 4),
                "matched_on": match_breakdown(patient_a, patient_b),
            })

    flagged.sort(key=lambda pair: pair["score"], reverse=True)
    return flagged
