import os
import csv
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL missing")


TABLE_NAME = "Athena_Concept_Relationships"
FILE_PATH = Path("data/CONCEPT_RELATIONSHIP.csv")


def get_columns(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        return next(reader)


conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print(f"Loading header from {FILE_PATH}")

columns = get_columns(FILE_PATH)

col_defs = []

for col in columns:
    clean = col.strip().replace('"', "")
    col_defs.append(f'"{clean}" TEXT')

print("Dropping existing table...")

cur.execute(f'''
DROP TABLE IF EXISTS "{TABLE_NAME}"
''')

print("Creating table...")

cur.execute(f'''
CREATE TABLE "{TABLE_NAME}" (
    {",".join(col_defs)}
)
''')

conn.commit()

print("Starting COPY...")

with open(FILE_PATH, "r", encoding="utf-8") as f:

    # skip header
    next(f)

    copy_sql = f'''
    COPY "{TABLE_NAME}"
    FROM STDIN
    WITH (
        FORMAT TEXT
    )
    '''

    cur.copy_expert(copy_sql, f)

conn.commit()

print("Creating indexes...")

cur.execute(f'''
CREATE INDEX idx_rel_source
ON "{TABLE_NAME}" (concept_id_1)
''')

cur.execute(f'''
CREATE INDEX idx_rel_target
ON "{TABLE_NAME}" (concept_id_2)
''')

cur.execute(f'''
CREATE INDEX idx_rel_type
ON "{TABLE_NAME}" (relationship_id)
''')

conn.commit()

cur.close()
conn.close()

print("DONE")