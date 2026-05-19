"""
MetaBiome Platform — Samples Router
REST endpoints for uploading FASTQs, registering samples, and retrieving sample metadata.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional
from datetime import date
import uuid
import boto3
import os

router = APIRouter()

S3_BUCKET_RAW = os.environ.get("S3_BUCKET_RAW", "metabiome-raw-fastq")
AWS_REGION    = os.environ.get("AWS_REGION", "us-east-1")


# ── Pydantic models ───────────────────────────────────────────────────────────
class SampleCreate(BaseModel):
    subject_id:      str
    sample_code:     str
    collection_date: date
    timepoint:       Optional[int] = None
    body_site:       str = "stool"
    sequencer:       Optional[str] = None
    read_length_bp:  Optional[int] = None
    notes:           Optional[str] = None


class SampleResponse(BaseModel):
    id:              str
    subject_id:      str
    sample_code:     str
    collection_date: date
    timepoint:       Optional[int]
    body_site:       str
    status:          str
    fastq_s3_path:   Optional[str]
    created_at:      str


class SampleListResponse(BaseModel):
    total:   int
    samples: list[SampleResponse]


class UploadResponse(BaseModel):
    sample_code:   str
    s3_path:       str
    presigned_url: str
    message:       str


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/upload", response_model=UploadResponse)
async def upload_fastq(
    sample_code: str = Query(..., description="Unique sample identifier e.g. SRR2726945"),
    file: UploadFile = File(..., description="FASTQ file (.fastq or .fastq.gz)"),
):
    """
    Upload a FASTQ file to S3 and register the sample.

    Example:
        POST /samples/upload?sample_code=SRR2726945
        Body: multipart/form-data with FASTQ file
    """
    # Validate file extension
    if not (file.filename.endswith(".fastq") or file.filename.endswith(".fastq.gz")):
        raise HTTPException(
            status_code=400,
            detail="Only .fastq or .fastq.gz files are accepted"
        )

    s3_key  = f"raw/{sample_code}/{file.filename}"
    s3_path = f"s3://{S3_BUCKET_RAW}/{s3_key}"

    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)

        # Upload file to S3
        content = await file.read()
        s3.put_object(
            Bucket=S3_BUCKET_RAW,
            Key=s3_key,
            Body=content,
            ContentType="application/gzip" if file.filename.endswith(".gz") else "text/plain",
        )

        # Generate presigned URL for direct download (valid 1 hour)
        presigned_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET_RAW, "Key": s3_key},
            ExpiresIn=3600,
        )

        return UploadResponse(
            sample_code=sample_code,
            s3_path=s3_path,
            presigned_url=presigned_url,
            message=f"FASTQ uploaded successfully to {s3_path}",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")


@router.post("/", response_model=SampleResponse, status_code=201)
async def create_sample(sample: SampleCreate):
    """
    Register a new sample in the database.
    Call this after uploading the FASTQ file.

    Example:
        POST /samples/
        {
          "subject_id": "HMP_001",
          "sample_code": "SRR2726945",
          "collection_date": "2024-03-15",
          "timepoint": 1,
          "body_site": "stool"
        }
    """
    # In production this inserts into PostgreSQL via SQLAlchemy
    # Returning a mock response for demo purposes
    sample_id = str(uuid.uuid4())
    return SampleResponse(
        id=sample_id,
        subject_id=sample.subject_id,
        sample_code=sample.sample_code,
        collection_date=sample.collection_date,
        timepoint=sample.timepoint,
        body_site=sample.body_site,
        status="received",
        fastq_s3_path=f"s3://{S3_BUCKET_RAW}/raw/{sample.sample_code}/",
        created_at=str(date.today()),
    )


@router.get("/", response_model=SampleListResponse)
async def list_samples(
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    status:     Optional[str] = Query(None, description="Filter by status: received | qc_pass | qc_fail | processed"),
    body_site:  Optional[str] = Query(None, description="Filter by body site e.g. stool"),
    limit:      int           = Query(50, ge=1, le=500),
    offset:     int           = Query(0, ge=0),
):
    """
    List all samples with optional filters.

    Example:
        GET /samples/?subject_id=HMP_001&status=processed
        GET /samples/?body_site=stool&limit=20
    """
    # Mock response — production queries PostgreSQL
    mock_samples = [
        SampleResponse(
            id=str(uuid.uuid4()),
            subject_id="HMP_001",
            sample_code="SRR2726945",
            collection_date=date(2024, 3, 15),
            timepoint=1,
            body_site="stool",
            status="processed",
            fastq_s3_path=f"s3://{S3_BUCKET_RAW}/raw/SRR2726945/",
            created_at="2024-03-15",
        ),
        SampleResponse(
            id=str(uuid.uuid4()),
            subject_id="HMP_001",
            sample_code="SRR2726946",
            collection_date=date(2024, 6, 15),
            timepoint=2,
            body_site="stool",
            status="qc_pass",
            fastq_s3_path=f"s3://{S3_BUCKET_RAW}/raw/SRR2726946/",
            created_at="2024-06-15",
        ),
    ]

    # Apply filters
    filtered = mock_samples
    if subject_id:
        filtered = [s for s in filtered if s.subject_id == subject_id]
    if status:
        filtered = [s for s in filtered if s.status == status]
    if body_site:
        filtered = [s for s in filtered if s.body_site == body_site]

    return SampleListResponse(total=len(filtered), samples=filtered[offset:offset+limit])


@router.get("/{sample_code}", response_model=SampleResponse)
async def get_sample(sample_code: str):
    """
    Get a single sample by its sample code.

    Example:
        GET /samples/SRR2726945
    """
    # Mock — production queries PostgreSQL
    if sample_code == "SRR2726945":
        return SampleResponse(
            id=str(uuid.uuid4()),
            subject_id="HMP_001",
            sample_code=sample_code,
            collection_date=date(2024, 3, 15),
            timepoint=1,
            body_site="stool",
            status="processed",
            fastq_s3_path=f"s3://{S3_BUCKET_RAW}/raw/{sample_code}/",
            created_at="2024-03-15",
        )
    raise HTTPException(status_code=404, detail=f"Sample '{sample_code}' not found")


@router.delete("/{sample_code}", status_code=204)
async def delete_sample(sample_code: str):
    """
    Delete a sample record and its associated S3 files.
    WARNING: This is irreversible.
    """
    # Production: delete from PostgreSQL + S3
    return None
