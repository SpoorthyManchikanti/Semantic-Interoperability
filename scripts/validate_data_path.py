from pathlib import Path
from app.config import FHIR_DATA_RAW, FHIR_FOLDER, FHIR_IS_URL, PROJECT_ROOT
from app.database import engine
from sqlalchemy import text

print("Resolved project root:", PROJECT_ROOT)
print("FHIR_DATA_RAW (from .env):", FHIR_DATA_RAW)
print("FHIR_FOLDER (resolved):", FHIR_FOLDER)
print("FHIR_IS_URL:", FHIR_IS_URL)
print("Exists:", Path(FHIR_FOLDER).exists())

# list first 10 json files
p = Path(FHIR_FOLDER)
if p.exists():
    files = list(p.glob("*.json"))
    print(f"Found {len(files)} .json files (showing up to 10):")
    for f in files[:10]:
        print(" -", f.name)
else:
    print("No files found (folder missing or empty)")

# count ingested files table if available
try:
    with engine.connect() as conn:
        r = conn.execute(text("SELECT count(*) FROM ingested_files"))
        cnt = r.scalar()
        print("Ingested files count:", cnt)
except Exception as e:
    print("Could not query ingested_files table:", e)
