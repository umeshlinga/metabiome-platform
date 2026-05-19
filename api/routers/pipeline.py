"""
MetaBiome Platform — Pipeline Router
REST endpoints for submitting pipeline jobs, polling status, and retrieving results.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import uuid
import boto3
import os
import json

router = APIRouter()

AWS_REGION           = os.environ.get("AWS_REGION", "us-east-1")
BATCH_JOB_QUEUE      = os.environ.get("AWS_BATCH_JOB_QUEUE", "metabiome-pipeline-queue")
BATCH_JOB_DEFINITION = os.environ.get("AWS_BATCH_JOB_DEFINITION", "metabiome-pipeline-job")
S3_BUCKET_RESULTS    = os.environ.get("S3_BUCKET_RESULTS", "metabiome-pipeline-results")


# ── Pydantic models ───────────────────────────────────────────────────────────
class PipelineRunRequest(BaseModel):
    sample_code:      str
    fastq_s3_path:    str
    pipeline_version: str = "1.0.0"
    config: dict = {}


class PipelineRunResponse(BaseModel):
    run_id:           str
    sample_code:      str
    status:           str
    pipeline_version: str
    batch_job_id:     Optional[str]
    message:          str


class PipelineStatusResponse(BaseModel):
    run_id:       str
    sample_code:  str
    status:       str           # queued | running | success | failed
    started_at:   Optional[str]
    completed_at: Optional[str]
    qc_stages: dict             # per-stage pass/fail flags
    error_message: Optional[str]


class PipelineResultsResponse(BaseModel):
    run_id:        str
    sample_code:   str
    status:        str
    qc_metrics:    dict
    taxa:          list[dict]
    biomarkers:    list[dict]
    output_paths:  dict


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/run", response_model=PipelineRunResponse, status_code=202)
async def submit_pipeline_run(request: PipelineRunRequest):
    """
    Submit a new pipeline job to AWS Batch.
    The pipeline runs asynchronously — poll /pipeline/{run_id}/status for updates.

    Example:
        POST /pipeline/run
        {
          "sample_code": "SRR2726945",
          "fastq_s3_path": "s3://metabiome-raw-fastq/raw/SRR2726945/SRR2726945.fastq.gz",
          "pipeline_version": "1.0.0"
        }
    """
    run_id = str(uuid.uuid4())

    # Submit to AWS Batch
    batch_job_id = None
    try:
        batch = boto3.client("batch", region_name=AWS_REGION)
        response = batch.submit_job(
            jobName=f"metabiome-{request.sample_code}-{run_id[:8]}",
            jobQueue=BATCH_JOB_QUEUE,
            jobDefinition=BATCH_JOB_DEFINITION,
            containerOverrides={
                "environment": [
                    {"name": "SAMPLE_CODE",   "value": request.sample_code},
                    {"name": "FASTQ_S3_PATH", "value": request.fastq_s3_path},
                    {"name": "RUN_ID",        "value": run_id},
                    {"name": "PIPELINE_VERSION", "value": request.pipeline_version},
                    {"name": "OUTPUT_BUCKET", "value": S3_BUCKET_RESULTS},
                ],
            },
        )
        batch_job_id = response["jobId"]
        message = f"Pipeline job submitted to AWS Batch (job ID: {batch_job_id})"

    except Exception as e:
        # AWS Batch not configured — return queued status for local dev
        message = f"Pipeline queued (local mode — AWS Batch not configured: {str(e)[:100]})"

    return PipelineRunResponse(
        run_id=run_id,
        sample_code=request.sample_code,
        status="queued",
        pipeline_version=request.pipeline_version,
        batch_job_id=batch_job_id,
        message=message,
    )


@router.get("/{run_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(run_id: str):
    """
    Poll the status of a pipeline run.

    Statuses: queued → running → success | failed

    Example:
        GET /pipeline/abc123/status
    """
    # Production: query PostgreSQL pipeline_runs table
    # Mock response for demo
    return PipelineStatusResponse(
        run_id=run_id,
        sample_code="SRR2726945",
        status="success",
        started_at="2024-03-15T10:00:00Z",
        completed_at="2024-03-15T10:45:00Z",
        qc_stages={
            "fastq_qc":   True,
            "alignment":  True,
            "dedup":      True,
            "variant":    True,
            "annotation": True,
        },
        error_message=None,
    )


@router.get("/{run_id}/results", response_model=PipelineResultsResponse)
async def get_pipeline_results(run_id: str):
    """
    Retrieve full results for a completed pipeline run.
    Includes QC metrics, top taxa, and biomarkers.

    Example:
        GET /pipeline/abc123/results
    """
    # Production: query PostgreSQL + fetch from S3
    return PipelineResultsResponse(
        run_id=run_id,
        sample_code="SRR2726945",
        status="success",
        qc_metrics={
            "fastq_qc": {
                "raw_read_count":     15_432_100,
                "reads_after_trim":   14_891_000,
                "mean_q_score":       35.2,
                "adapter_removal_pct": 3.5,
                "passed":             True,
            },
            "alignment": {
                "total_reads":       14_891_000,
                "mapped_reads":      13_100_000,
                "alignment_rate_pct": 87.9,
                "host_removal_pct":  12.1,
                "passed":            True,
            },
            "deduplication": {
                "duplicate_rate_pct":     18.3,
                "reads_after_dedup":      10_697_000,
                "estimated_library_size": 52_000_000,
                "passed":                 True,
            },
            "variant_calling": {
                "total_variants":  4_231,
                "snp_count":       3_890,
                "indel_count":     341,
                "mean_depth":      48.7,
                "passed":          True,
            },
        },
        taxa=[
            {
                "taxon_name":    "Faecalibacterium prausnitzii",
                "rank":          "species",
                "relative_abund": 0.1823,
                "read_count":    195_000,
            },
            {
                "taxon_name":    "Bacteroides uniformis",
                "rank":          "species",
                "relative_abund": 0.1102,
                "read_count":    117_800,
            },
            {
                "taxon_name":    "Bifidobacterium longum",
                "rank":          "species",
                "relative_abund": 0.0891,
                "read_count":    95_300,
            },
            {
                "taxon_name":    "Roseburia intestinalis",
                "rank":          "species",
                "relative_abund": 0.0743,
                "read_count":    79_400,
            },
            {
                "taxon_name":    "Akkermansia muciniphila",
                "rank":          "species",
                "relative_abund": 0.0512,
                "read_count":    54_700,
            },
        ],
        biomarkers=[
            {
                "marker_name":   "shannon_diversity",
                "marker_type":   "diversity",
                "value":         3.82,
                "unit":          "bits",
                "interpretation": "normal",
            },
            {
                "marker_name":   "firmicutes_bacteroidetes_ratio",
                "marker_type":   "ratio",
                "value":         1.24,
                "unit":          "ratio",
                "interpretation": "normal",
            },
            {
                "marker_name":   "butyrate_producers_enrichment",
                "marker_type":   "enrichment",
                "value":         0.31,
                "unit":          "fraction",
                "interpretation": "high",
            },
        ],
        output_paths={
            "bam":    f"s3://{S3_BUCKET_RESULTS}/{run_id}/aligned.bam",
            "vcf":    f"s3://{S3_BUCKET_RESULTS}/{run_id}/variants.vcf.gz",
            "report": f"s3://{S3_BUCKET_RESULTS}/{run_id}/report.html",
        },
    )


@router.get("/", response_model=list[PipelineRunResponse])
async def list_pipeline_runs(
    sample_code: Optional[str] = Query(None),
    status:      Optional[str] = Query(None),
    limit:       int           = Query(20, ge=1, le=100),
):
    """
    List all pipeline runs with optional filters.

    Example:
        GET /pipeline/?status=success
        GET /pipeline/?sample_code=SRR2726945
    """
    # Production: query PostgreSQL pipeline_runs table
    return [
        PipelineRunResponse(
            run_id=str(uuid.uuid4()),
            sample_code="SRR2726945",
            status="success",
            pipeline_version="1.0.0",
            batch_job_id="job-abc123",
            message="Completed successfully",
        )
    ]
