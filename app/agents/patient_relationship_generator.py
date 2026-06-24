from __future__ import annotations

import os
from typing import Any, Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor

from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """
    Create and return a connection to the Neon Postgres database.
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL was not found in the environment.")

    return psycopg2.connect(database_url)


def load_patient_data(patient_id: str) -> Dict[str, Any]:
    """
    Load normalized patient data from the database and return it
    as a dictionary.

    Parameters
    ----------
    patient_id : str
        The patient identifier.

    Returns
    -------
    Dict[str, Any]
        Dictionary containing conditions, medications, and observations.
    """
    patient_data: Dict[str, Any] = {
        "patient_id": patient_id,
        "conditions": [],
        "medications": [],
        "observations": []
    }

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # Load conditions
            cur.execute(
                """
                SELECT condition_name
                FROM conditions
                WHERE patient_id = %s
                """,
                (patient_id,)
            )

            patient_data["conditions"] = [
                row["condition_name"]
                for row in cur.fetchall()
            ]

            # Load medications
            cur.execute(
                """
                SELECT medication_name
                FROM medications
                WHERE patient_id = %s
                """,
                (patient_id,)
            )

            patient_data["medications"] = [
                row["medication_name"]
                for row in cur.fetchall()
            ]

            # Load observations
            cur.execute(
                """
                SELECT observation_name, observation_value
                FROM observations
                WHERE patient_id = %s
                """,
                (patient_id,)
            )

            patient_data["observations"] = [
                {
                    "name": row["observation_name"],
                    "value": row["observation_value"]
                }
                for row in cur.fetchall()
            ]

    return patient_data


def discover_relationships(
    patient_data: Dict[str, Any]
) -> List[Dict[str, str]]:
    """
    Create graph-style relationships (edges) between entities.

    Parameters
    ----------
    patient_data : Dict[str, Any]

    Returns
    -------
    List[Dict[str, str]]
        List of relationship edges.
    """
    relationships: List[Dict[str, str]] = []

    patient_node = patient_data["patient_id"]

    # Patient -> Condition relationships
    for condition in patient_data["conditions"]:
        relationships.append(
            {
                "source": patient_node,
                "target": condition,
                "relationship": "HAS_CONDITION"
            }
        )

    # Patient -> Medication relationships
    for medication in patient_data["medications"]:
        relationships.append(
            {
                "source": patient_node,
                "target": medication,
                "relationship": "TAKES_MEDICATION"
            }
        )

    # Patient -> Observation relationships
    for observation in patient_data["observations"]:
        observation_node = (
            f"{observation['name']}={observation['value']}"
        )

        relationships.append(
            {
                "source": patient_node,
                "target": observation_node,
                "relationship": "HAS_OBSERVATION"
            }
        )

    return relationships

def get_all_patient_ids() -> List[str]:
    """
    Return all distinct patient IDs found in the database.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT patient_id
                FROM (
                    SELECT patient_id FROM conditions
                    UNION
                    SELECT patient_id FROM medications
                    UNION
                    SELECT patient_id FROM observations
                ) AS patients
            """)

            return [row[0] for row in cur.fetchall()]

def main() -> None:
    """
    Load every patient and discover relationships.
    """

    patient_ids = get_all_patient_ids()

    if not patient_ids:
        print("No patients found.")
        return

    for patient_id in patient_ids:
        print("\n" + "=" * 50)
        print(f"Patient ID: {patient_id}")

        patient_data = load_patient_data(patient_id)

        print("\nPatient Data")
        print("------------")
        print(patient_data)

        relationships = discover_relationships(patient_data)

        print("\nDiscovered Relationships")
        print("------------------------")

        for edge in relationships:
            print(edge)

if __name__ == "__main__":
    main()