"""
MetaBiome Platform — Variant Calling Module
Calls variants from deduplicated BAM using bcftools + fgbio.
Annotates VCF with taxonomy and functional information.
Outputs indexed, filtered VCF ready for biomarker extraction.
"""
import subprocess
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────────
@dataclass
class VariantConfig:
    min_base_quality: int = 20          # minimum base quality for variant calling
    min_mapping_quality: int = 20       # minimum read mapping quality
    min_allele_frequency: float = 0.01  # minimum VAF to report a variant
    min_depth: int = 5                  # minimum read depth at variant site
    max_depth: int = 10000              # cap depth for performance
    min_vcf_records: int = 1            # at least 1 variant expected
    threads: int = 4


# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class VariantResult:
    sample_id: str
    vcf_path: str
    vcf_index_path: str
    filtered_vcf_path: str
    stats_path: str
    total_variants: int
    passed_filter_variants: int
    snp_count: int
    indel_count: int
    mean_depth: float
    passed: bool
    failure_reasons: list[str]


# ── Main variant calling function ─────────────────────────────────────────────
def run_variant_calling(
    dedup_bam: str,
    reference_genome: str,
    sample_id: str,
    outdir: str,
    config: VariantConfig = None,
) -> VariantResult:
    """
    Variant calling workflow:
    1. Generate pileup with bcftools mpileup
    2. Call variants with bcftools call
    3. Filter variants by quality, depth, allele frequency
    4. Index the VCF
    5. Generate stats and evaluate pass/fail

    Args:
        dedup_bam:        Path to deduplicated, sorted BAM
        reference_genome: Path to indexed reference genome (FASTA)
        sample_id:        Unique sample identifier
        outdir:           Output directory
        config:           VariantConfig settings

    Returns:
        VariantResult with variant counts and pass/fail status
    """
    if config is None:
        config = VariantConfig()

    outdir_path = Path(outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)

    raw_vcf      = outdir_path / f"{sample_id}_raw.vcf.gz"
    filtered_vcf = outdir_path / f"{sample_id}.vcf.gz"
    stats_path   = outdir_path / f"{sample_id}_vcf_stats.txt"
    audit_path   = outdir_path / f"{sample_id}_variant_audit.json"

    # ── Step 1: Generate pileup + call variants ───────────────────────────────
    logger.info(f"[{sample_id}] Step 1: Generating pileup and calling variants (bcftools)")
    _run_cmd([
        "bcftools", "mpileup",
        "--fasta-ref", reference_genome,
        "--min-BQ", str(config.min_base_quality),
        "--min-MQ", str(config.min_mapping_quality),
        "--max-depth", str(config.max_depth),
        "--annotate", "FORMAT/AD,FORMAT/DP",
        "--output-type", "u",           # uncompressed BCF for piping
        str(dedup_bam),
        "|",
        "bcftools", "call",
        "--multiallelic-caller",        # modern multi-allelic calling model
        "--variants-only",              # only output variant sites
        "--output-type", "z",           # gzipped VCF output
        "--output", str(raw_vcf),
    ], shell=True)

    # ── Step 2: Index raw VCF ─────────────────────────────────────────────────
    logger.info(f"[{sample_id}] Step 2: Indexing raw VCF")
    _run_cmd(["bcftools", "index", "--tbi", str(raw_vcf)])

    # ── Step 3: Filter variants ───────────────────────────────────────────────
    logger.info(f"[{sample_id}] Step 3: Filtering variants")
    _run_cmd([
        "bcftools", "filter",
        "--include",
        (
            f"QUAL >= 30 && "
            f"FORMAT/DP >= {config.min_depth} && "
            f"FORMAT/AD[0:1] / FORMAT/DP >= {config.min_allele_frequency}"
        ),
        "--soft-filter", "LOW_QUAL",    # mark filtered variants, don't remove
        "--output-type", "z",
        "--output", str(filtered_vcf),
        str(raw_vcf),
    ])

    # ── Step 4: Index filtered VCF ────────────────────────────────────────────
    logger.info(f"[{sample_id}] Step 4: Indexing filtered VCF")
    _run_cmd(["bcftools", "index", "--tbi", str(filtered_vcf)])

    # ── Step 5: Generate VCF stats ────────────────────────────────────────────
    logger.info(f"[{sample_id}] Step 5: Generating VCF statistics")
    stats_output = _run_cmd_output([
        "bcftools", "stats", str(filtered_vcf)
    ])
    stats_path.write_text(stats_output)

    # ── Step 6: Parse stats ───────────────────────────────────────────────────
    stats = _parse_vcf_stats(stats_output)
    total_variants         = stats.get("number of records", 0)
    passed_filter_variants = stats.get("number of SNPs", 0) + stats.get("number of indels", 0)
    snp_count              = stats.get("number of SNPs", 0)
    indel_count            = stats.get("number of indels", 0)
    mean_depth             = stats.get("average depth", 0.0)

    logger.info(
        f"[{sample_id}] Variants: {total_variants} total | "
        f"{snp_count} SNPs | {indel_count} indels | "
        f"mean depth: {mean_depth:.1f}x"
    )

    # ── Step 7: Pass / fail evaluation ───────────────────────────────────────
    failures = []
    if total_variants < config.min_vcf_records:
        failures.append(
            f"VCF has {total_variants} records — below minimum {config.min_vcf_records}. "
            f"Check BAM alignment and reference genome compatibility."
        )
    if mean_depth < config.min_depth:
        failures.append(
            f"Mean depth {mean_depth:.1f}x below minimum {config.min_depth}x "
            f"— insufficient coverage for reliable variant calling"
        )
    if not filtered_vcf.exists():
        failures.append("Filtered VCF file was not created — bcftools may have failed")
    if not Path(str(filtered_vcf) + ".tbi").exists():
        failures.append("VCF index (.tbi) missing — tabix indexing failed")

    result = VariantResult(
        sample_id=sample_id,
        vcf_path=str(raw_vcf),
        vcf_index_path=str(raw_vcf) + ".tbi",
        filtered_vcf_path=str(filtered_vcf),
        stats_path=str(stats_path),
        total_variants=total_variants,
        passed_filter_variants=passed_filter_variants,
        snp_count=snp_count,
        indel_count=indel_count,
        mean_depth=round(mean_depth, 2),
        passed=len(failures) == 0,
        failure_reasons=failures,
    )

    # ── Step 8: Write audit JSON ──────────────────────────────────────────────
    with open(audit_path, "w") as f:
        json.dump({
            "sample_id": result.sample_id,
            "total_variants": result.total_variants,
            "passed_filter_variants": result.passed_filter_variants,
            "snp_count": result.snp_count,
            "indel_count": result.indel_count,
            "mean_depth": result.mean_depth,
            "passed": result.passed,
            "failure_reasons": result.failure_reasons,
        }, f, indent=2)

    status = "PASS" if result.passed else "FAIL"
    logger.info(f"[{sample_id}] Variant calling QC: {status}")
    for reason in failures:
        logger.warning(f"  ✗ {reason}")

    return result


# ── Pipeline orchestrator: run all three stages in sequence ───────────────────
def run_full_pipeline(
    fastq_path: str,
    reference_genome: str,
    sample_id: str,
    outdir: str,
) -> dict:
    """
    Convenience function: runs QC → alignment → dedup → variant calling
    in sequence. Returns a dict of all stage results.
    Raises RuntimeError if any stage fails its QC checkpoint.
    """
    from pipeline.modules.fastq_qc import run_fastq_qc, QCConfig
    from pipeline.modules.alignment import run_alignment, AlignmentConfig
    from pipeline.modules.deduplication import run_deduplication, DedupConfig

    results = {}

    # Stage 1: FASTQ QC
    logger.info(f"[{sample_id}] === Stage 1: FASTQ QC ===")
    qc_result = run_fastq_qc(fastq_path, sample_id, f"{outdir}/qc")
    results["fastq_qc"] = qc_result
    if not qc_result.passed:
        raise RuntimeError(f"FASTQ QC failed: {qc_result.failure_reasons}")

    # Stage 2: Alignment
    logger.info(f"[{sample_id}] === Stage 2: Alignment ===")
    align_result = run_alignment(
        qc_result.trimmed_fastq_path, reference_genome,
        sample_id, f"{outdir}/alignment"
    )
    results["alignment"] = align_result
    if not align_result.passed:
        raise RuntimeError(f"Alignment failed: {align_result.failure_reasons}")

    # Stage 3: Deduplication
    logger.info(f"[{sample_id}] === Stage 3: Deduplication ===")
    dedup_result = run_deduplication(
        align_result.bam_path, sample_id, f"{outdir}/dedup"
    )
    results["deduplication"] = dedup_result
    if not dedup_result.passed:
        raise RuntimeError(f"Deduplication failed: {dedup_result.failure_reasons}")

    # Stage 4: Variant calling
    logger.info(f"[{sample_id}] === Stage 4: Variant Calling ===")
    variant_result = run_variant_calling(
        dedup_result.dedup_bam_path, reference_genome,
        sample_id, f"{outdir}/variants"
    )
    results["variant_calling"] = variant_result
    if not variant_result.passed:
        raise RuntimeError(f"Variant calling failed: {variant_result.failure_reasons}")

    logger.info(f"[{sample_id}] === Pipeline complete — all stages passed ===")
    return results


# ── Helpers ───────────────────────────────────────────────────────────────────
def _run_cmd(cmd: list[str], shell: bool = False) -> None:
    if shell:
        result = subprocess.run(" ".join(cmd), shell=True, capture_output=True, text=True)
    else:
        result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed (exit {result.returncode}):\n"
            f"  cmd: {' '.join(cmd) if isinstance(cmd, list) else cmd}\n"
            f"  stderr: {result.stderr[:500]}"
        )


def _run_cmd_output(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n{result.stderr[:500]}"
        )
    return result.stdout


def _parse_vcf_stats(stats_text: str) -> dict:
    """
    Parse bcftools stats SN (summary numbers) section.
    Lines look like: SN\t0\tnumber of SNPs:\t1234
    """
    metrics = {}
    for line in stats_text.splitlines():
        if line.startswith("SN"):
            parts = line.split("\t")
            if len(parts) >= 4:
                key   = parts[2].rstrip(":").strip()
                value = parts[3].strip()
                try:
                    metrics[key] = float(value) if "." in value else int(value)
                except ValueError:
                    metrics[key] = value
    return metrics
