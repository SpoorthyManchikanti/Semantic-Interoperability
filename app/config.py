from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FHIR_DATA_RAW = os.getenv('FHIR_DATA_PATH', './data/import_test')

# Resolve to a Path relative to project root when not absolute
FHIR_DATA_PATH = Path(FHIR_DATA_RAW)
if not FHIR_DATA_PATH.is_absolute():
    FHIR_FOLDER = (PROJECT_ROOT / FHIR_DATA_PATH).resolve()
else:
    FHIR_FOLDER = FHIR_DATA_PATH

FHIR_IS_URL = isinstance(FHIR_DATA_RAW, str) and FHIR_DATA_RAW.startswith(('http://', 'https://'))
