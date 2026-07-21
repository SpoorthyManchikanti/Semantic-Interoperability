"""
Populate patients.data_source — real provenance, not a hardcoded frontend
string. Real Synthea-generated patients get one label; the synthetic
clones created to test identity resolution get a visibly distinct one,
since they are not actual Synthea output.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import engine

SYNTHEA_LABEL = "Synthea Synthetic Patient Data"
SYNTHETIC_CLONE_LABEL = "Synthetic Test Record — Identity Resolution Demo"


def main():
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE patients
            SET data_source = :label
            WHERE patient_id NOT LIKE 'synthetic-%'
        """), {"label": SYNTHEA_LABEL})
        print(f"Set data_source='{SYNTHEA_LABEL}' on {result.rowcount} real patients.")

        result = conn.execute(text("""
            UPDATE patients
            SET data_source = :label
            WHERE patient_id LIKE 'synthetic-%'
        """), {"label": SYNTHETIC_CLONE_LABEL})
        print(f"Set data_source='{SYNTHETIC_CLONE_LABEL}' on {result.rowcount} synthetic clones.")


if __name__ == "__main__":
    main()
