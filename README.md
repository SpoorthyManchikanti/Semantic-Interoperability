# Semantic Interoperability Layer

A semantic interoperability layer built on FHIR data that normalizes heterogeneous healthcare information into canonical semantic concepts, enabling unified queries across different data sources.

## Features

- **FHIR Data Ingestion**: Load synthetic Synthea patient data from FHIR JSON bundles
- **Semantic Normalization**: Map raw FHIR values to canonical concepts (conditions, observations, medications)
- **Unified Query API**: RESTful endpoints for semantic queries across patient records
- **Data Profiling**: Analyze loaded data and generate semantic profiles
- **Data Quality Metrics**: Track completeness and coverage of semantic data

## Quick Start

### 1. Clone and Setup

```bash
git clone <repo>
cd Semantic-Interoperability

# Create virtual environment (if not already present)
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the template and add your database credentials:

```bash
cp .env.example .env
```

Edit `.env` and set:

```env
# Neon PostgreSQL connection
DATABASE_URL=postgresql://user:password@host/database?sslmode=require

# Path to FHIR data (local folder or OneDrive URL)
FHIR_DATA_PATH=./data/import_test
```

### 3. Download/Setup Data

If using OneDrive data:

```bash
python scripts/download_data.py
```

Or place Synthea FHIR JSON files directly in `./data/import_test/`

### 4. Run ETL Pipeline

**Windows:**
```bash
scripts\run_etl.bat
```

**Python (all platforms):**
```bash
python scripts/run_etl.py
```

### 5. Start API Server

```bash
uvicorn app.main:app --reload
```

API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Patients
- `GET /patients/` - List all patients
- `GET /patients/{patient_id}` - Get full patient profile
- `GET /patients/search?first_name=...&last_name=...` - Search by name

### Conditions
- `GET /conditions/` - List all unique conditions
- `GET /conditions/{condition_name}/patients` - Get patients with condition

### Concepts
- `GET /concepts/` - List all semantic concepts
- `GET /concepts/profile` - Get dataset semantic profile
- `POST /concepts/normalize` - Normalize a concept value

## Project Structure

```
app/
├── main.py                    # FastAPI application
├── database.py                # Database connection
├── models.py                  # SQLAlchemy tables
├── semantic/
│   ├── normalizer.py         # Semantic normalization
│   ├── profiler_builder.py   # Data profiling
│   └── schemas.py            # Pydantic schemas
└── routes/
    ├── patients.py           # Patient endpoints
    ├── conditions.py         # Condition endpoints
    └── concepts.py           # Semantic endpoints

etl/
├── create_tables.py          # Table creation
└── load_data.py              # FHIR data loading

scripts/
├── download_data.py          # OneDrive downloader
├── run_etl.py               # ETL orchestrator
└── run_etl.bat              # Windows batch runner
```

## Semantic Mappings

Common terminology variants are normalized to canonical forms in `app/semantic/normalizer.py`:

- **Conditions**: Diabetes variants → "Diabetes Mellitus Type 2"
- **Observations**: "BP", "HbA1c" → canonical lab names
- **Medications**: Drug names → standardized medication concepts

## Data Sources

**Synthea**: Generates realistic, synthetic patient data in FHIR format.

https://github.com/synthetichealth/synthea

## Troubleshooting

### ImportError: No module named 'app'
Set PYTHONPATH to project root:
```bash
$env:PYTHONPATH = Get-Location  # PowerShell
```

### Database connection failed
Verify `DATABASE_URL` in `.env`

### FHIR data not found
Check `FHIR_DATA_PATH` points to folder with `.json` files

## Next Steps

- Expand semantic mappings
- Integrate SNOMED CT codes
- Add clinical decision support
- Implement HL7 FHIR API
- Add GraphQL query interface
