from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import patients, conditions, concepts, dashboard, graph, ai_summary

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|0\.0\.0\.0):(5173|5174|5175|8000|\d+)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router)
app.include_router(conditions.router)
app.include_router(concepts.router)
app.include_router(dashboard.router)
app.include_router(graph.router)
app.include_router(ai_summary.router)


@app.get("/")
def root():
    return {"message": "Semantic Interoperability API Running"}