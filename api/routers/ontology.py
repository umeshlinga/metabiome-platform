"""
MetaBiome Platform — Ontology Router
REST endpoints for searching SNOMED-CT, ICD-10, LOINC, MedDRA, ATC.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import httpx

router = APIRouter()

# Supported ontology systems and their public API base URLs
ONTOLOGY_SOURCES = {
    "SNOMED": "https://browser.ihtsdotools.org/snowstorm/snomed-ct/MAIN/concepts",
    "ICD-10": "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search",
    "LOINC":  "https://loinc.org/search/",
    "MedDRA": None,   # requires license — use local DB cache
    "ATC":    "https://rxnav.nlm.nih.gov/REST/rxclass/class/byName.json",
}

SUPPORTED_SYSTEMS = list(ONTOLOGY_SOURCES.keys())


# ── Pydantic models ───────────────────────────────────────────────────────────
class OntologyTerm(BaseModel):
    code: str
    display: str
    system: str
    synonyms: list[str] = []
    hierarchy: list[str] = []


class OntologySearchResponse(BaseModel):
    system: str
    query: str
    total: int
    results: list[OntologyTerm]


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.get("/search", response_model=OntologySearchResponse)
async def search_ontology(
    system: str = Query(..., description="Ontology system: SNOMED | ICD-10 | LOINC | MedDRA | ATC"),
    term: str = Query(..., min_length=2, description="Search term, e.g. 'Crohn disease'"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Search a clinical ontology for matching terms.

    Example:
        GET /ontology/search?system=SNOMED&term=Crohn+disease
        GET /ontology/search?system=ICD-10&term=K50
        GET /ontology/search?system=LOINC&term=microbiome
    """
    system = system.upper()
    if system not in SUPPORTED_SYSTEMS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown ontology system '{system}'. Supported: {SUPPORTED_SYSTEMS}",
        )

    if system == "ICD-10":
        results = await _search_icd10(term, limit)
    elif system == "SNOMED":
        results = await _search_snomed(term, limit)
    elif system == "LOINC":
        results = await _search_loinc(term, limit)
    else:
        # MedDRA / ATC: use local DB cache (not implemented in this demo)
        results = []

    return OntologySearchResponse(
        system=system,
        query=term,
        total=len(results),
        results=results,
    )


@router.get("/systems")
def list_systems():
    """List all supported ontology systems."""
    return {"systems": SUPPORTED_SYSTEMS}


@router.get("/term/{system}/{code}", response_model=OntologyTerm)
async def get_term_by_code(system: str, code: str):
    """
    Look up a single ontology term by its code.

    Example:
        GET /ontology/term/ICD-10/K50.0
        GET /ontology/term/SNOMED/34000006
    """
    system = system.upper()
    if system == "ICD-10":
        results = await _search_icd10(code, limit=5)
        matches = [r for r in results if r.code == code]
        if not matches:
            raise HTTPException(status_code=404, detail=f"ICD-10 code '{code}' not found")
        return matches[0]

    raise HTTPException(status_code=501, detail=f"Direct code lookup not yet implemented for {system}")


# ── Ontology-specific search helpers ──────────────────────────────────────────
async def _search_icd10(term: str, limit: int) -> list[OntologyTerm]:
    """
    Query NLM's free ICD-10-CM search API.
    https://clinicaltables.nlm.nih.gov/apidoc/icd10cm/v3/doc.html
    """
    url = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
    params = {"sf": "code,name", "terms": term, "maxList": limit}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            # Response format: [total, codes_list, extra, display_list]
            if len(data) < 4:
                return []
            codes = data[1] or []
            displays = data[3] or []
            results = []
            for code, display_row in zip(codes, displays):
                results.append(OntologyTerm(
                    code=code,
                    display=display_row[1] if display_row else code,
                    system="ICD-10",
                ))
            return results
        except Exception:
            return []


async def _search_snomed(term: str, limit: int) -> list[OntologyTerm]:
    """
    Query SNOMED CT browser API (public IHTSDO endpoint).
    For production, point to a self-hosted Snowstorm instance.
    """
    url = "https://browser.ihtsdotools.org/snowstorm/snomed-ct/MAIN/concepts"
    params = {"term": term, "activeFilter": True, "limit": limit, "offset": 0}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("items", []):
                results.append(OntologyTerm(
                    code=item.get("conceptId", ""),
                    display=item.get("fsn", {}).get("term", ""),
                    system="SNOMED",
                    synonyms=[
                        s.get("term", "")
                        for s in item.get("descriptions", [])
                        if s.get("type") == "SYNONYM"
                    ][:5],
                ))
            return results
        except Exception:
            return []


async def _search_loinc(term: str, limit: int) -> list[OntologyTerm]:
    """
    Query LOINC via NLM FHIR endpoint.
    For production, use loinc.org API with credentials.
    """
    url = "https://fhir.loinc.org/CodeSystem/$lookup"
    params = {"system": "http://loinc.org", "code": term}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            display = next(
                (p["valueString"] for p in data.get("parameter", []) if p["name"] == "display"),
                term,
            )
            return [OntologyTerm(code=term, display=display, system="LOINC")]
        except Exception:
            return []
