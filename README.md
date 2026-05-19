# MetaBiome Platform

> A full-stack, production-grade microbiome data platform — modular shotgun metagenomic sequencing pipeline, REST API with clinical ontology integration, longitudinal data schema, React dashboard, and AWS deployment.

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-teal)](https://fastapi.tiangolo.com)
[![Nextflow](https://img.shields.io/badge/Nextflow-23.10-green)](https://nextflow.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)](https://postgresql.org)
[![AWS](https://img.shields.io/badge/AWS-ECS%2FBatch%2FS3-orange)](https://aws.amazon.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Overview

MetaBiome Platform mirrors the architecture of a real-world longitudinal microbiome intelligence system. It takes raw shotgun metagenomic FASTQ data, processes it through a validated bioinformatics pipeline, stores results in a structured PostgreSQL database with clinical ontology annotations, and surfaces insights via a REST API and React dashboard.

**Key capabilities:**
- End-to-end shotgun metagenomic pipeline: FASTQ → QC → alignment → deduplication → variant calling → biomarker annotation
- Clinical ontology integration: SNOMED-CT, ICD-10, LOINC, MedDRA, ATC via REST API
- Longitudinal / repeated-measures schema supporting multi-timepoint per-subject tracking
- Automated Pytest QC checkpoints at every pipeline stage
- Fully containerized with Docker Compose for local dev and AWS ECS/Fargate + Batch for production
- CI/CD via GitHub Actions

---

## Architecture

```
metabiome-platform/
├── pipeline/               # Nextflow + Python bioinformatics pipeline
│   ├── modules/            # Modular steps: QC, alignment, dedup, variant calling
│   ├── configs/            # Nextflow configs (local, AWS Batch)
│   └── tests/              # Pytest QC checkpoints per stage
│
├── api/                    # FastAPI backend
│   ├── routers/            # Endpoints: /pipeline, /samples, /ontology, /biomarkers
│   ├── models/             # SQLAlchemy ORM models
│   ├── services/           # Business logic, ontology clients, S3 integration
│   └── tests/              # API unit + integration tests
│
├── frontend/               # React + Tailwind dashboard
│   └── src/
│       ├── components/     # PipelineMonitor, OntologySearch, LongitudinalChart
│       └── pages/          # Dashboard, Samples, Results, Settings
│
├── db/                     # PostgreSQL schema + Alembic migrations
│   ├── migrations/         # Alembic versioned migration files
│   └── seeds/              # Dev seed data (HMP-derived synthetic samples)
│
└── infra/                  # Infrastructure as code
    ├── docker/             # Dockerfiles for api, pipeline, frontend
    ├── aws/                # ECS task definitions, Batch job queues, IAM policies
    └── github/             # GitHub Actions CI/CD workflows
```

---

## Bioinformatics Pipeline

The pipeline processes raw shotgun metagenomic FASTQ data through five auditable stages, each with automated Pytest QC checkpoints.

```
Raw FASTQ
   │
   ▼
[Stage 1] Quality Control          FastQC + Trimmomatic
          └── Pytest checkpoint:   read count, Q-score threshold, adapter removal %
   │
   ▼
[Stage 2] Host Removal + Alignment  bwa mem → human reference (GRCh38)
          └── Pytest checkpoint:   host removal rate, alignment rate, unmapped %
   │
   ▼
[Stage 3] Deduplication + Sorting   Picard MarkDuplicates + samtools sort
          └── Pytest checkpoint:   duplicate rate, BAM integrity, index validation
   │
   ▼
[Stage 4] Variant Calling           fgbio + bcftools
          └── Pytest checkpoint:   VCF record count, FILTER field, allele frequency range
   │
   ▼
[Stage 5] Biomarker Annotation      Kraken2 / custom taxonomy DB
          └── Pytest checkpoint:   species count, compositional sum, metadata match
   │
   ▼
PostgreSQL + S3
(BAM/VCF stored in S3; metadata, taxa, biomarkers in PostgreSQL)
```

### Tools used

| Tool | Purpose |
|---|---|
| `FastQC` | Per-base quality reporting on raw reads |
| `Trimmomatic` | Adapter trimming, low-quality read removal |
| `bwa mem` | Alignment of reads to reference genome |
| `samtools` | BAM sorting, indexing, flagstat QC |
| `Picard MarkDuplicates` | PCR duplicate marking |
| `fgbio` | UMI-aware duplicate calling, variant support |
| `bcftools` | Variant calling and VCF manipulation |
| `Nextflow / nf-core` | Pipeline orchestration and reproducibility |
| `Pytest` | Automated QC validation at each stage |

---

## Clinical Ontology Integration

The platform integrates four major clinical terminologies to standardize health metadata:

| Ontology | Used for |
|---|---|
| **SNOMED-CT** | Clinical findings, body site, organism classification |
| **ICD-10** | Disease codes associated with microbiome phenotypes |
| **LOINC** | Lab observation codes for sequencing metadata |
| **MedDRA** | Adverse event and symptom annotation |

Example API call:
```bash
GET /ontology/search?system=SNOMED&term=Crohn+disease
```
```json
{
  "code": "34000006",
  "display": "Crohn's disease (disorder)",
  "system": "SNOMED-CT",
  "synonyms": ["Regional enteritis", "Granulomatous ileocolitis"]
}
```

---

## Database Schema (PostgreSQL)

Designed for longitudinal / repeated-measures microbiome studies.

**Core tables:**
- `subjects` — demographic and clinical metadata per participant
- `samples` — one row per sample collection event (supports multiple per subject over time)
- `pipeline_runs` — tracks every pipeline execution with status, config, timestamps
- `taxa` — microbial species identified per sample with abundance values
- `biomarkers` — derived microbiome features (diversity, ratios, enrichment scores)
- `ontology_mappings` — links samples/biomarkers to SNOMED/ICD-10/LOINC codes

---

## Quick Start (Local — Docker Compose)

**Prerequisites:** Docker Desktop, Python 3.11+, Node 18+

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/metabiome-platform.git
cd metabiome-platform

# 2. Copy environment config
cp .env.example .env

# 3. Start all services (API + DB + Frontend)
docker compose up --build

# 4. Run database migrations
docker compose exec api alembic upgrade head

# 5. Seed dev data (synthetic HMP-derived samples)
docker compose exec api python db/seeds/seed_dev.py

# 6. Access
#   API docs:    http://localhost:8000/docs
#   Frontend:    http://localhost:3000
#   PgAdmin:     http://localhost:5050
```

---

## Running the Pipeline (Local)

```bash
cd pipeline

# Install Python deps
pip install -r requirements.txt

# Run on a test FASTQ (uses SRA sample SRR2726945 from HMP)
nextflow run main.nf \
  --input data/test/SRR2726945_1.fastq.gz \
  --outdir results/ \
  --profile local

# Run Pytest QC checkpoints
pytest tests/ -v
```

---

## AWS Deployment

The platform deploys to AWS using ECS Fargate (API + frontend) and AWS Batch (pipeline jobs).

```bash
cd infra/aws

# Configure AWS credentials
aws configure

# Deploy infrastructure (ECS cluster, Batch queue, RDS, S3 buckets)
./deploy.sh --env production

# Push Docker images to ECR
./push_images.sh
```

**AWS services used:**
- `ECS Fargate` — runs the FastAPI backend and React frontend as containers
- `AWS Batch` — runs Nextflow pipeline jobs on-demand, scales to zero
- `S3` — stores FASTQ, BAM, VCF files per run with versioning enabled
- `RDS PostgreSQL` — managed database with automated backups
- `IAM` — least-privilege roles per service
- `VPC` — private subnets for pipeline workers, public for API

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/pipeline/run` | Submit a new pipeline job |
| `GET` | `/pipeline/{run_id}/status` | Poll pipeline run status |
| `GET` | `/pipeline/{run_id}/results` | Retrieve QC + biomarker results |
| `POST` | `/samples/upload` | Upload FASTQ to S3 + register sample |
| `GET` | `/samples` | List all samples with metadata |
| `GET` | `/ontology/search` | Search SNOMED / ICD-10 / LOINC |
| `GET` | `/biomarkers` | Query biomarker results with filters |
| `POST` | `/subjects/{id}/metadata` | Attach clinical metadata to subject |

Full interactive docs available at `/docs` (Swagger UI) and `/redoc`.

---

## Testing

```bash
# Pipeline QC tests
cd pipeline && pytest tests/ -v

# API unit + integration tests
cd api && pytest tests/ -v --cov=. --cov-report=html

# Frontend
cd frontend && npm test
```

---

## Data Sources

This project uses publicly available microbiome datasets:

- **HMP (Human Microbiome Project)** — [hmpdacc.org](https://hmpdacc.org) — reference gut microbiome FASTQ datasets
- **NCBI SRA** — [ncbi.nlm.nih.gov/sra](https://ncbi.nlm.nih.gov/sra) — additional shotgun metagenomic samples
- **MGnify** — [ebi.ac.uk/metagenomics](https://ebi.ac.uk/metagenomics) — longitudinal cohort datasets
- **NCBI RefSeq** — human GRCh38 reference genome and microbial reference databases

---

## Tech Stack

| Layer | Technology |
|---|---|
| Pipeline | Python 3.11, Nextflow 23, nf-core, bwa, STAR, samtools, Picard, fgbio |
| Backend | FastAPI, SQLAlchemy, Alembic, Pydantic, Pytest |
| Database | PostgreSQL 15, psycopg2 |
| Frontend | React 18, Tailwind CSS, Recharts, Axios |
| Cloud | AWS ECS, Batch, S3, RDS, IAM, VPC |
| DevOps | Docker, Docker Compose, GitHub Actions |

---

## License

MIT — see [LICENSE](LICENSE)

---

## Author

**Umesh Linga**
Senior Bioinformatics Engineer
[umesh.linga25@gmail.com](mailto:umesh.linga25@gmail.com)
