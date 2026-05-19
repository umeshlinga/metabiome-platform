-- MetaBiome Platform — PostgreSQL Schema
-- Longitudinal microbiome + clinical metadata
-- Supports repeated-measures per subject, clinical ontology mappings,
-- pipeline run tracking, and microbiome biomarker storage.

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- for fast ontology term search

-- ── Subjects ──────────────────────────────────────────────────────────────────
-- One row per study participant. Clinical metadata attached via ontology_mappings.
CREATE TABLE subjects (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id     VARCHAR(64) UNIQUE NOT NULL,    -- e.g. HMP subject ID
    cohort          VARCHAR(128),                   -- study/cohort name
    age_at_enroll   INTEGER,
    sex             VARCHAR(16),
    bmi             NUMERIC(5,2),
    country         VARCHAR(64),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Samples ───────────────────────────────────────────────────────────────────
-- One row per sample collection event. Multiple samples per subject = longitudinal.
CREATE TABLE samples (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_id      UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    sample_code     VARCHAR(64) UNIQUE NOT NULL,    -- e.g. SRR2726945
    collection_date DATE NOT NULL,
    timepoint       INTEGER,                        -- visit number (1, 2, 3...)
    body_site       VARCHAR(64) DEFAULT 'stool',
    dna_conc_ng_ul  NUMERIC(8,3),
    sequencer       VARCHAR(64),                    -- e.g. Illumina NovaSeq 6000
    read_length_bp  INTEGER,
    fastq_s3_path   TEXT,                           -- s3://bucket/prefix/sample.fastq.gz
    status          VARCHAR(32) DEFAULT 'received', -- received | qc_pass | qc_fail | processed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_samples_subject_id    ON samples(subject_id);
CREATE INDEX idx_samples_collection_dt ON samples(collection_date);
CREATE INDEX idx_samples_status        ON samples(status);

-- ── Pipeline runs ─────────────────────────────────────────────────────────────
-- Tracks every pipeline execution with full audit trail.
CREATE TABLE pipeline_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sample_id       UUID NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    pipeline_version VARCHAR(32) NOT NULL,           -- e.g. 1.3.0
    nextflow_run_id  VARCHAR(128),                   -- Nextflow's internal run hash
    status          VARCHAR(32) DEFAULT 'queued',   -- queued | running | success | failed
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    -- Stage-level QC flags (set by Pytest checkpoints)
    qc_fastq        BOOLEAN,
    qc_alignment    BOOLEAN,
    qc_dedup        BOOLEAN,
    qc_variant      BOOLEAN,
    qc_annotation   BOOLEAN,
    -- Output locations
    bam_s3_path     TEXT,
    vcf_s3_path     TEXT,
    report_s3_path  TEXT,
    -- Config snapshot (full Nextflow params stored as JSON for reproducibility)
    config_snapshot JSONB,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pipeline_runs_sample_id ON pipeline_runs(sample_id);
CREATE INDEX idx_pipeline_runs_status    ON pipeline_runs(status);

-- ── QC metrics ────────────────────────────────────────────────────────────────
-- Per-stage QC numbers from each pipeline run.
CREATE TABLE qc_metrics (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pipeline_run_id     UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    stage               VARCHAR(32) NOT NULL,   -- fastq_qc | alignment | dedup | variant | annotation
    -- FASTQ QC
    raw_read_count      BIGINT,
    reads_after_trim    BIGINT,
    mean_q_score        NUMERIC(5,2),
    adapter_removal_pct NUMERIC(5,2),
    -- Alignment
    alignment_rate_pct  NUMERIC(5,2),
    host_removal_pct    NUMERIC(5,2),
    unmapped_pct        NUMERIC(5,2),
    -- Dedup
    duplicate_rate_pct  NUMERIC(5,2),
    -- Variant / annotation
    vcf_record_count    INTEGER,
    species_count       INTEGER,
    passed_pytest       BOOLEAN NOT NULL DEFAULT FALSE,
    metrics_json        JSONB,                  -- full tool output for deep inspection
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_qc_metrics_run_id ON qc_metrics(pipeline_run_id);

-- ── Taxa ──────────────────────────────────────────────────────────────────────
-- Microbial species identified per sample with abundance values.
CREATE TABLE taxa (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    sample_id       UUID NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    taxon_id        VARCHAR(64),                -- NCBI taxon ID
    taxon_name      VARCHAR(256) NOT NULL,      -- e.g. Faecalibacterium prausnitzii
    rank            VARCHAR(32),                -- species | genus | family | phylum
    relative_abund  NUMERIC(12,8),              -- fraction of total reads (0–1)
    read_count      BIGINT,
    kraken2_conf    NUMERIC(5,4),               -- Kraken2 confidence score
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_taxa_sample_id      ON taxa(sample_id);
CREATE INDEX idx_taxa_pipeline_run   ON taxa(pipeline_run_id);
CREATE INDEX idx_taxa_taxon_name     ON taxa USING gin(taxon_name gin_trgm_ops);

-- ── Biomarkers ────────────────────────────────────────────────────────────────
-- Derived microbiome features calculated from taxa profiles.
CREATE TABLE biomarkers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sample_id       UUID NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    marker_name     VARCHAR(128) NOT NULL,
    marker_type     VARCHAR(64),    -- diversity | ratio | enrichment | functional
    value           NUMERIC(16,8),
    unit            VARCHAR(32),
    reference_range_low  NUMERIC(16,8),
    reference_range_high NUMERIC(16,8),
    interpretation  VARCHAR(32),    -- normal | high | low | undefined
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_biomarkers_sample_id   ON biomarkers(sample_id);
CREATE INDEX idx_biomarkers_marker_name ON biomarkers(marker_name);

-- ── Ontology terms ────────────────────────────────────────────────────────────
-- Local cache of clinical ontology codes (SNOMED, ICD-10, LOINC, MedDRA, ATC).
CREATE TABLE ontology_terms (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    system      VARCHAR(32) NOT NULL,   -- SNOMED | ICD-10 | LOINC | MedDRA | ATC
    code        VARCHAR(64) NOT NULL,
    display     TEXT NOT NULL,
    synonyms    TEXT[],
    hierarchy   TEXT[],                 -- ancestor codes for traversal
    last_synced TIMESTAMPTZ,
    UNIQUE (system, code)
);

CREATE INDEX idx_ontology_system  ON ontology_terms(system);
CREATE INDEX idx_ontology_display ON ontology_terms USING gin(display gin_trgm_ops);

-- ── Ontology mappings ─────────────────────────────────────────────────────────
-- Links subjects, samples, and biomarkers to clinical ontology codes.
CREATE TABLE ontology_mappings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type     VARCHAR(32) NOT NULL,   -- subject | sample | biomarker
    entity_id       UUID NOT NULL,
    ontology_term_id UUID NOT NULL REFERENCES ontology_terms(id),
    relationship    VARCHAR(64),            -- has_condition | body_site | measured_by
    source          VARCHAR(64),            -- clinician | auto | import
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ont_mappings_entity ON ontology_mappings(entity_type, entity_id);

-- ── Updated_at trigger ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_subjects_updated_at
    BEFORE UPDATE ON subjects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_samples_updated_at
    BEFORE UPDATE ON samples
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Helpful views ─────────────────────────────────────────────────────────────

-- Longitudinal summary: all samples per subject in time order
CREATE VIEW v_subject_timeline AS
SELECT
    sub.external_id     AS subject_id,
    sub.cohort,
    samp.sample_code,
    samp.collection_date,
    samp.timepoint,
    samp.body_site,
    samp.status,
    pr.status           AS pipeline_status,
    pr.pipeline_version
FROM subjects sub
JOIN samples samp ON samp.subject_id = sub.id
LEFT JOIN pipeline_runs pr ON pr.sample_id = samp.id
ORDER BY sub.external_id, samp.collection_date;

-- Top taxa per sample (top 10 by relative abundance)
CREATE VIEW v_top_taxa AS
SELECT
    samp.sample_code,
    sub.external_id AS subject_id,
    samp.collection_date,
    t.taxon_name,
    t.rank,
    t.relative_abund,
    ROW_NUMBER() OVER (PARTITION BY t.sample_id ORDER BY t.relative_abund DESC) AS rank_order
FROM taxa t
JOIN samples samp ON samp.id = t.sample_id
JOIN subjects sub ON sub.id = samp.subject_id;
