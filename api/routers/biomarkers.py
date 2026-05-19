"""
MetaBiome Platform — Biomarkers Router
REST endpoints for querying microbiome biomarkers, taxa, and longitudinal trends.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import uuid

router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────────
class BiomarkerResponse(BaseModel):
    id:              str
    sample_code:     str
    subject_id:      str
    collection_date: str
    marker_name:     str
    marker_type:     str
    value:           float
    unit:            Optional[str]
    interpretation:  Optional[str]   # normal | high | low


class TaxonResponse(BaseModel):
    sample_code:     str
    subject_id:      str
    collection_date: str
    taxon_name:      str
    rank:            str
    relative_abund:  float
    read_count:      int


class LongitudinalPoint(BaseModel):
    collection_date: str
    timepoint:       int
    value:           float


class LongitudinalResponse(BaseModel):
    subject_id:  str
    marker_name: str
    unit:        Optional[str]
    trend:       str              # stable | increasing | decreasing
    data_points: list[LongitudinalPoint]


class DiversityResponse(BaseModel):
    sample_code:      str
    subject_id:       str
    collection_date:  str
    shannon_index:    float
    simpson_index:    float
    observed_species: int
    chao1_estimate:   float
    interpretation:   str


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.get("/", response_model=list[BiomarkerResponse])
async def get_biomarkers(
    sample_code:  Optional[str] = Query(None, description="Filter by sample code"),
    subject_id:   Optional[str] = Query(None, description="Filter by subject ID"),
    marker_name:  Optional[str] = Query(None, description="Filter by marker e.g. shannon_diversity"),
    marker_type:  Optional[str] = Query(None, description="Filter by type: diversity | ratio | enrichment"),
    limit:        int           = Query(50, ge=1, le=500),
):
    """
    Query microbiome biomarkers with filters.

    Example:
        GET /biomarkers/?subject_id=HMP_001&marker_type=diversity
        GET /biomarkers/?marker_name=shannon_diversity
    """
    mock_biomarkers = [
        BiomarkerResponse(
            id=str(uuid.uuid4()),
            sample_code="SRR2726945",
            subject_id="HMP_001",
            collection_date="2024-03-15",
            marker_name="shannon_diversity",
            marker_type="diversity",
            value=3.82,
            unit="bits",
            interpretation="normal",
        ),
        BiomarkerResponse(
            id=str(uuid.uuid4()),
            sample_code="SRR2726945",
            subject_id="HMP_001",
            collection_date="2024-03-15",
            marker_name="firmicutes_bacteroidetes_ratio",
            marker_type="ratio",
            value=1.24,
            unit="ratio",
            interpretation="normal",
        ),
        BiomarkerResponse(
            id=str(uuid.uuid4()),
            sample_code="SRR2726945",
            subject_id="HMP_001",
            collection_date="2024-03-15",
            marker_name="butyrate_producers_enrichment",
            marker_type="enrichment",
            value=0.31,
            unit="fraction",
            interpretation="high",
        ),
        BiomarkerResponse(
            id=str(uuid.uuid4()),
            sample_code="SRR2726946",
            subject_id="HMP_001",
            collection_date="2024-06-15",
            marker_name="shannon_diversity",
            marker_type="diversity",
            value=3.61,
            unit="bits",
            interpretation="normal",
        ),
    ]

    filtered = mock_biomarkers
    if sample_code:
        filtered = [b for b in filtered if b.sample_code == sample_code]
    if subject_id:
        filtered = [b for b in filtered if b.subject_id == subject_id]
    if marker_name:
        filtered = [b for b in filtered if b.marker_name == marker_name]
    if marker_type:
        filtered = [b for b in filtered if b.marker_type == marker_type]

    return filtered[:limit]


@router.get("/taxa", response_model=list[TaxonResponse])
async def get_taxa(
    sample_code: Optional[str] = Query(None),
    subject_id:  Optional[str] = Query(None),
    rank:        Optional[str] = Query(None, description="species | genus | family | phylum"),
    min_abund:   float         = Query(0.0,  description="Minimum relative abundance (0-1)"),
    limit:       int           = Query(20, ge=1, le=200),
):
    """
    Query microbial taxa identified across samples.

    Example:
        GET /biomarkers/taxa?subject_id=HMP_001&rank=species&min_abund=0.01
    """
    mock_taxa = [
        TaxonResponse(
            sample_code="SRR2726945",
            subject_id="HMP_001",
            collection_date="2024-03-15",
            taxon_name="Faecalibacterium prausnitzii",
            rank="species",
            relative_abund=0.1823,
            read_count=195_000,
        ),
        TaxonResponse(
            sample_code="SRR2726945",
            subject_id="HMP_001",
            collection_date="2024-03-15",
            taxon_name="Bacteroides uniformis",
            rank="species",
            relative_abund=0.1102,
            read_count=117_800,
        ),
        TaxonResponse(
            sample_code="SRR2726945",
            subject_id="HMP_001",
            collection_date="2024-03-15",
            taxon_name="Akkermansia muciniphila",
            rank="species",
            relative_abund=0.0512,
            read_count=54_700,
        ),
        TaxonResponse(
            sample_code="SRR2726945",
            subject_id="HMP_001",
            collection_date="2024-03-15",
            taxon_name="Bacteroidetes",
            rank="phylum",
            relative_abund=0.3821,
            read_count=408_400,
        ),
        TaxonResponse(
            sample_code="SRR2726945",
            subject_id="HMP_001",
            collection_date="2024-03-15",
            taxon_name="Firmicutes",
            rank="phylum",
            relative_abund=0.4738,
            read_count=506_400,
        ),
    ]

    filtered = mock_taxa
    if sample_code:
        filtered = [t for t in filtered if t.sample_code == sample_code]
    if subject_id:
        filtered = [t for t in filtered if t.subject_id == subject_id]
    if rank:
        filtered = [t for t in filtered if t.rank == rank]
    filtered = [t for t in filtered if t.relative_abund >= min_abund]

    return filtered[:limit]


@router.get("/longitudinal/{subject_id}", response_model=LongitudinalResponse)
async def get_longitudinal_trend(
    subject_id:  str,
    marker_name: str = Query(..., description="Biomarker to track over time"),
):
    """
    Get longitudinal trend for a biomarker across all timepoints for a subject.
    This is the core of MetaBiome's repeated-measures platform.

    Example:
        GET /biomarkers/longitudinal/HMP_001?marker_name=shannon_diversity
    """
    # Mock longitudinal data — 3 timepoints for one subject
    data_points = [
        LongitudinalPoint(collection_date="2024-03-15", timepoint=1, value=3.82),
        LongitudinalPoint(collection_date="2024-06-15", timepoint=2, value=3.61),
        LongitudinalPoint(collection_date="2024-09-15", timepoint=3, value=3.74),
    ]

    # Simple trend detection
    values = [p.value for p in data_points]
    if values[-1] > values[0] * 1.05:
        trend = "increasing"
    elif values[-1] < values[0] * 0.95:
        trend = "decreasing"
    else:
        trend = "stable"

    return LongitudinalResponse(
        subject_id=subject_id,
        marker_name=marker_name,
        unit="bits" if "diversity" in marker_name else None,
        trend=trend,
        data_points=data_points,
    )


@router.get("/diversity/{sample_code}", response_model=DiversityResponse)
async def get_diversity_metrics(sample_code: str):
    """
    Get alpha diversity metrics for a sample.
    Includes Shannon, Simpson, observed species, and Chao1 estimates.

    Example:
        GET /biomarkers/diversity/SRR2726945
    """
    if sample_code not in ["SRR2726945", "SRR2726946"]:
        raise HTTPException(
            status_code=404,
            detail=f"No diversity data found for sample '{sample_code}'"
        )

    return DiversityResponse(
        sample_code=sample_code,
        subject_id="HMP_001",
        collection_date="2024-03-15",
        shannon_index=3.82,
        simpson_index=0.94,
        observed_species=312,
        chao1_estimate=418.3,
        interpretation=(
            "High alpha diversity — consistent with a healthy gut microbiome. "
            "Shannon index above 3.5 suggests good species richness."
        ),
    )
