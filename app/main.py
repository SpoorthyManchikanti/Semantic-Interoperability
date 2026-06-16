from fastapi import FastAPI
from app.routes import patients, conditions, concepts

app = FastAPI(
    title="Semantic Interoperability Layer",
    description="FHIR data semantic normalization and unified query interface",
    version="0.1.0"
)

# Include route modules
app.include_router(patients.router)
app.include_router(conditions.router)
app.include_router(concepts.router)


@app.get("/")
def root():
    """Root endpoint - API status and documentation."""
    return {
        "status": "Semantic Interoperability Layer Running",
        "version": "0.1.0",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "patients": "/patients",
            "conditions": "/conditions",
            "concepts": "/concepts"
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}