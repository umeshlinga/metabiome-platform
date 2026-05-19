"""
MetaBiome Platform — Deduplication Module
Marks and removes PCR duplicate reads using Picard MarkDuplicates + fgbio.
Outputs a clean, sorted, indexed BAM ready for variant calling.
"""
import subprocess
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────────
@dataclass
class DedupConfig:
    max_duplicate_rate: float = 80.0    # flag if >80% reads are duplicates
    use_umi: bool = False                # set True if library has UMI barcodes
    remove_duplicates: bool = True       # actually remove, not just mark
    threads: int = 4
    java_heap_mb: int = 4096            # memory for Picard JVM


# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class DedupResult:
    sample_id: str
    dedup_bam_path: str
    dedup_bai_path: str
    metrics_path: str
    total_reads: int
    duplicate_reads: int
    duplicate_rate_pct: float
    reads_after_dedup: int
    estimated_library_size: int
    passed: bool
    failure_reasons: list[str]


# ── Main deduplication function ───────────────────────────────────────────────
def run_deduplication(
    bam_path: str,
    sample_id: str,
    outdir: str,
    config: DedupConfig = None,
) -> DedupResult:
    """
    Deduplication workflow:
    1. Add read group tags (required by Picard)
    2. Run Picard MarkDuplicates (or fgbio for UMI-aware dedup)
    3. Sort and index deduplicated BAM
    4. Parse metrics and evaluate pass/fail

    Args:
        bam_path:   Path to aligned, sorted BAM from alignment stage
        sample_id:  Unique sample identifier
        outdir:     Output directory
        config:     DedupConfig settings

    Returns:
        DedupResult with duplicate metrics and pass/fail status
    """
    if config is None:
        config = DedupConfig()

    outdir_path = Path(outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)

    rg_bam      = outdir_path / f"{sample_id}_rg.bam"
    dedup_bam   = outdir_path / f"{sample_id}_dedup.bam"
    metrics_txt = outdir_path / f"{sample_id}_dup_metrics.txt"
    audit_path  = outdir_path / f"{sample_id}_dedup_audit.json"

    # ── Step 1: Add read group (Picard requires this) ─────────────────────────
    logger.info(f"[{sample_id}] Step 1: Adding read group tags with Picard")
    _run_picard([
        "AddOrReplaceReadGroups",
        f"I={bam_path}",
        f"O={rg_bam}",
        f"RGID={sample_id}",
        f"RGLB=lib1",
        f"RGPL=ILLUMINA",
        f"RGPU=unit1",
        f"RGSM={sample_id}",
    ], config.java_heap_mb)

    # ── Step 2: Mark / remove duplicates ─────────────────────────────────────
    if config.use_umi:
        logger.info(f"[{sample_id}] Step 2: UMI-aware deduplication with fgbio")
        _run_fgbio_dedup(rg_bam, dedup_bam, metrics_txt, sample_id, config)
    else:
        logger.info(f"[{sample_id}] Step 2: PCR deduplication with Picard MarkDuplicates")
        _run_picard_markdup(rg_bam, dedup_bam, metrics_txt, config)

    # ── Step 3: Sort and index deduplicated BAM ───────────────────────────────
    logger.info(f"[{sample_id}] Step 3: Sorting and indexing deduplicated BAM")
    sorted_bam = outdir_path / f"{sample_id}_dedup_sorted.bam"
    _run_cmd(["samtools", "sort", "-o", str(sorted_bam), str(dedup_bam)])
    _run_cmd(["samtools", "index", str(sorted_bam)])

    # Replace unsorted dedup BAM with sorted version
    sorted_bam.rename(dedup_bam)
    Path(str(sorted_bam) + ".bai").rename(str(dedup_bam) + ".bai")

    # ── Step 4: Parse Picard metrics ──────────────────────────────────────────
    logger.info(f"[{sample_id}] Step 4: Parsing duplicate metrics")
    metrics = _parse_picard_metrics(metrics_txt)

    total_reads      = metrics.get("unpaired_reads_examined", 0) + metrics.get("read_pairs_examined", 0) * 2
    duplicate_reads  = metrics.get("unpaired_read_duplicates", 0) + metrics.get("read_pair_duplicates", 0) * 2
    dup_rate         = metrics.get("percent_duplication", 0.0) * 100
    est_lib_size     = metrics.get("estimated_library_size", 0)
    reads_after_dedup = total_reads - duplicate_reads

    logger.info(
        f"[{sample_id}] Duplicate rate: {dup_rate:.1f}% | "
        f"Reads after dedup: {reads_after_dedup:,} | "
        f"Est. library size: {est_lib_size:,}"
    )

    # ── Step 5: Pass / fail evaluation ───────────────────────────────────────
    failures = []
    if dup_rate > config.max_duplicate_rate:
        failures.append(
            f"Duplicate rate {dup_rate:.1f}% exceeds maximum {config.max_duplicate_rate:.1f}% "
            f"— possible PCR over-amplification"
        )
    if reads_after_dedup == 0:
        failures.append("Zero reads remaining after deduplication")
    if est_lib_size < 1000:
        failures.append(
            f"Estimated library size {est_lib_size:,} is very low — "
            f"possible low-complexity library"
        )

    result = DedupResult(
        sample_id=sample_id,
        dedup_bam_path=str(dedup_bam),
        dedup_bai_path=str(dedup_bam) + ".bai",
        metrics_path=str(metrics_txt),
        total_reads=total_reads,
        duplicate_reads=duplicate_reads,
        duplicate_rate_pct=round(dup_rate, 2),
        reads_after_dedup=reads_after_dedup,
        estimated_library_size=est_lib_size,
        passed=len(failures) == 0,
        failure_reasons=failures,
    )

    # ── Step 6: Write audit JSON ──────────────────────────────────────────────
    with open(audit_path, "w") as f:
        json.dump({
            "sample_id": result.sample_id,
            "total_reads": result.total_reads,
            "duplicate_reads": result.duplicate_reads,
            "duplicate_rate_pct": result.duplicate_rate_pct,
            "reads_after_dedup": result.reads_after_dedup,
            "estimated_library_size": result.estimated_library_size,
            "passed": result.passed,
            "failure_reasons": result.failure_reasons,
        }, f, indent=2)

    status = "PASS" if result.passed else "FAIL"
    logger.info(f"[{sample_id}] Dedup QC: {status}")
    for reason in failures:
        logger.warning(f"  ✗ {reason}")

    return result


# ── Tool-specific helpers ─────────────────────────────────────────────────────
def _run_picard_markdup(
    input_bam: Path,
    output_bam: Path,
    metrics_txt: Path,
    config: DedupConfig,
) -> None:
    """Run Picard MarkDuplicates."""
    _run_picard([
        "MarkDuplicates",
        f"I={input_bam}",
        f"O={output_bam}",
        f"M={metrics_txt}",
        f"REMOVE_DUPLICATES={'true' if config.remove_duplicates else 'false'}",
        "VALIDATION_STRINGENCY=LENIENT",
        "CREATE_INDEX=true",
        "OPTICAL_DUPLICATE_PIXEL_DISTANCE=2500",  # NovaSeq patterned flowcell
    ], config.java_heap_mb)


def _run_fgbio_dedup(
    input_bam: Path,
    output_bam: Path,
    metrics_txt: Path,
    sample_id: str,
    config: DedupConfig,
) -> None:
    """
    UMI-aware deduplication with fgbio.
    Requires reads to have UMI tags (RX tag) set during FASTQ processing.
    """
    grouped_bam = input_bam.parent / f"{sample_id}_grouped.bam"

    # Group reads by UMI
    _run_cmd([
        "fgbio", f"-Xmx{config.java_heap_mb}m",
        "GroupReadsByUmi",
        "--input", str(input_bam),
        "--output", str(grouped_bam),
        "--strategy", "adjacency",
        "--min-map-q", "20",
    ])

    # Call consensus reads from UMI groups
    _run_cmd([
        "fgbio", f"-Xmx{config.java_heap_mb}m",
        "CallMolecularConsensusReads",
        "--input", str(grouped_bam),
        "--output", str(output_bam),
        "--min-reads", "1",
        "--output-per-base-tags", "false",
    ])

    # fgbio doesn't write Picard-format metrics — generate a stub
    metrics_txt.write_text(
        "## fgbio UMI deduplication\n"
        f"SAMPLE\tUMI_DEDUP\n{sample_id}\ttrue\n"
    )


def _run_picard(args: list[str], heap_mb: int = 4096) -> None:
    cmd = ["picard", f"-Xmx{heap_mb}m"] + args
    _run_cmd(cmd)


def _run_cmd(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed (exit {result.returncode}):\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  stderr: {result.stderr[:500]}"
        )
    return result.stdout


def _parse_picard_metrics(metrics_path: Path) -> dict:
    """
    Parse Picard MarkDuplicates metrics file.
    The metrics are in a tab-separated table after the header lines.
    Returns a dict of metric_name -> value.
    """
    if not metrics_path.exists():
        logger.warning(f"Metrics file not found: {metrics_path}")
        return {}

    text = metrics_path.read_text()
    lines = text.splitlines()

    # Find the METRICS CLASS header line
    header_idx = None
    for i, line in enumerate(lines):
        if line.startswith("ESTIMATED_LIBRARY_SIZE") or line.startswith("UNPAIRED_READS_EXAMINED"):
            header_idx = i - 1
            break
        if "METRICS CLASS" in line:
            header_idx = i + 1
            break

    if header_idx is None:
        return {}

    try:
        headers = lines[header_idx].strip().lower().split("\t")
        values  = lines[header_idx + 1].strip().split("\t")
        metrics = {}
        for h, v in zip(headers, values):
            try:
                metrics[h] = float(v) if "." in v else int(v)
            except ValueError:
                metrics[h] = v
        return metrics
    except (IndexError, ValueError):
        return {}
