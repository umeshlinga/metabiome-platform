"""
MetaBiome Platform — FastAPI Backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import pipeline, samples, ontology, biomarkers

app = FastAPI(
    title="MetaBiome Platform API",
    description="Microbiome data platform — pipeline management, ontology search, biomarker retrieval",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router,   prefix="/pipeline",   tags=["Pipeline"])
app.include_router(samples.router,    prefix="/samples",    tags=["Samples"])
app.include_router(ontology.router,   prefix="/ontology",   tags=["Ontology"])
app.include_router(biomarkers.router, prefix="/biomarkers", tags=["Biomarkers"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "metabiome-api"}
