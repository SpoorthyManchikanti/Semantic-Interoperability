from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOCK_PATIENT = {
    "id": "12345",
    "name": "John Doe",
    "age": 58,
    "conditions": [
        "Type 2 Diabetes",
        "Hypertension"
    ],
    "medications": [
        "Metformin",
        "Lisinopril"
    ],
    "relationships": [
        {
            "source": "Type 2 Diabetes",
            "target": "Metformin",
            "relationship": "treated_by"
        },
        {
            "source": "Hypertension",
            "target": "Lisinopril",
            "relationship": "treated_by"
        }
    ]
}

@app.get("/")
def root():
    return {"message": "Semantic Interoperability API Running"}

@app.get("/patient/{patient_id}")
def get_patient(patient_id: str):
    return MOCK_PATIENT