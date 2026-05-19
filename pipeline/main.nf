#!/usr/bin/env nextflow
// MetaBiome Platform — Main Nextflow Pipeline
// Shotgun metagenomic sequencing: FASTQ → QC → alignment → dedup → variant call → annotation

nextflow.enable.dsl = 2

// ── Parameters ────────────────────────────────────────────
params.input           = null
params.outdir          = 'results'
params.reference       = params.reference ?: System.getenv('REFERENCE_GENOME_PATH')
params.kraken2_db      = params.kraken2_db ?: System.getenv('KRAKEN2_DB_PATH')
params.pipeline_version = '1.0.0'
params.min_q_score     = 20
params.min_read_length = 50
params.profile         = 'local'

// ── Validate inputs ───────────────────────────────────────
if (!params.input) error "ERROR: --input FASTQ path is required"
if (!params.reference) error "ERROR: --reference genome path is required"

log.info """
=================================================
  MetaBiome Platform — Metagenomic Pipeline
  version : ${params.pipeline_version}
  input   : ${params.input}
  outdir  : ${params.outdir}
  profile : ${params.profile}
=================================================
""".stripIndent()

// ── Include modules ───────────────────────────────────────
include { FASTQ_QC        } from './modules/fastq_qc'
include { HOST_REMOVAL    } from './modules/host_removal'
include { ALIGNMENT       } from './modules/alignment'
include { DEDUPLICATION   } from './modules/deduplication'
include { VARIANT_CALLING } from './modules/variant_calling'
include { TAXONOMY_ANNOTATION } from './modules/taxonomy_annotation'
include { GENERATE_REPORT } from './modules/report'

// ── Main workflow ─────────────────────────────────────────
workflow {
    // Input channel: FASTQ file
    ch_fastq = Channel.fromPath(params.input, checkIfExists: true)

    // Stage 1: QC + trimming
    FASTQ_QC(ch_fastq)

    // Stage 2: Remove human host reads, align microbial reads
    HOST_REMOVAL(FASTQ_QC.out.trimmed_fastq, params.reference)
    ALIGNMENT(HOST_REMOVAL.out.microbial_fastq, params.reference)

    // Stage 3: Sort, deduplicate
    DEDUPLICATION(ALIGNMENT.out.bam)

    // Stage 4: Variant calling
    VARIANT_CALLING(DEDUPLICATION.out.dedup_bam, params.reference)

    // Stage 5: Taxonomy annotation
    TAXONOMY_ANNOTATION(DEDUPLICATION.out.dedup_bam, params.kraken2_db)

    // Final: Aggregate report
    GENERATE_REPORT(
        FASTQ_QC.out.qc_report,
        ALIGNMENT.out.flagstat,
        DEDUPLICATION.out.dup_metrics,
        VARIANT_CALLING.out.vcf,
        TAXONOMY_ANNOTATION.out.kraken2_report
    )
}

// ── Completion handler ────────────────────────────────────
workflow.onComplete {
    log.info """
Pipeline completed!
  Status  : ${workflow.success ? 'SUCCESS' : 'FAILED'}
  Duration: ${workflow.duration}
  Results : ${params.outdir}
    """.stripIndent()
}
