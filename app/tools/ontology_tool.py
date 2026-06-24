from pathlib import Path
from sqlalchemy import create_engine, text
import pandas as pd
import os

from dotenv import load_dotenv

load_dotenv()

class OntologyTool:

    def __init__(self):
        database_url = os.getenv("DATABASE_URL")

        if not database_url:
            raise ValueError("DATABASE_URL not found")

        self.engine = create_engine(database_url)

        data_dir = Path("data")

        print("Loading Athena relationship tables...")

        self.relationships = pd.read_csv(
            data_dir / "CONCEPT_RELATIONSHIP.csv",
            sep="\t",
            dtype=str,
            low_memory=False
        )

        self.ancestors = pd.read_csv(
            data_dir / "CONCEPT_ANCESTOR.csv",
            sep="\t",
            dtype=str,
            low_memory=False
        )

        self.synonyms = pd.read_csv(
            data_dir / "CONCEPT_SYNONYM.csv",
            sep="\t",
            dtype=str,
            low_memory=False
        )

        self.classes = pd.read_csv(
            data_dir / "CONCEPT_CLASS.csv",
            sep="\t",
            dtype=str,
            low_memory=False
        )

        print("Ontology loaded")

    # ------------------------------------------------
    # CONCEPT LOOKUP (Neon)
    # ------------------------------------------------

    def get_concept(self, concept_id: str):

        query = text("""
            SELECT *
            FROM "Athena_Concepts"
            WHERE concept_id = :concept_id
            LIMIT 1
        """)

        with self.engine.connect() as conn:

            result = conn.execute(
                query,
                {"concept_id": concept_id}
            )

            row = result.mappings().first()

        return dict(row) if row else None

    # ------------------------------------------------
    # RELATIONSHIPS
    # ------------------------------------------------

    def get_relationships(self, concept_id: str):

        rows = self.relationships[
            self.relationships["concept_id_1"] == str(concept_id)
        ]

        return rows.to_dict("records")

    # ------------------------------------------------
    # ANCESTORS
    # ------------------------------------------------

    def get_ancestors(self, concept_id: str):

        rows = self.ancestors[
            self.ancestors["descendant_concept_id"] == str(concept_id)
        ]

        return rows.to_dict("records")

    # ------------------------------------------------
    # DESCENDANTS
    # ------------------------------------------------

    def get_descendants(self, concept_id: str):

        rows = self.ancestors[
            self.ancestors["ancestor_concept_id"] == str(concept_id)
        ]

        return rows.to_dict("records")

    # ------------------------------------------------
    # SYNONYMS
    # ------------------------------------------------

    def get_synonyms(self, concept_id: str):

        rows = self.synonyms[
            self.synonyms["concept_id"] == str(concept_id)
        ]

        return rows.to_dict("records")

    # ------------------------------------------------
    # CLASS
    # ------------------------------------------------

    def get_class(self, concept_class_id: str):

        rows = self.classes[
            self.classes["concept_class_id"] == concept_class_id
        ]

        return rows.to_dict("records")