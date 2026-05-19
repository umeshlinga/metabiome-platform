"""
MetaBiome Platform — Alignment Module
Removes human host reads, aligns microbial reads to reference using bwa mem.
Outputs sorted, indexed BAM file with samtools flagstat QC report.
"""
import subprocess
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────────
@dataclass
class AlignmentConfig:
    threads: int = 8
    min_alignment_rate: float = 50.0   # % of reads that must align
    max_unmapped_pct: float = 50.0     # flag if too many reads unmapped
    bwa_extra_args: str = ""           # e.g. "-k 19 -w 100"


# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class AlignmentResult:
    sample_id: str
    bam_path: str
    bai_path: str
    flagstat_path: str
    total_reads: int
    mapped_reads: int
    alignment_rate_pct: float
    host_reads_removed: int
    host_removal_pct: float
    unmapped_pct: float
    passed: bool
    failure_reasons: list[str]


# ── Main alignment function ───────────────────────────────────────────────────
def run_alignment(
    trimmed_fastq: str,
    reference_genome: str,
    sample_id: str,
    outdir: str,
    config: AlignmentConfig = None,
) -> AlignmentResult:
    """
    Full alignment workflow:
    1. Align all reads to human reference (GRCh38) — identify host reads
    2. Extract unmapped (microbial) reads
    3. Align microbial reads to microbial reference database
    4. Sort and index BAM
    5. Run samtools flagstat for QC

    Args:
        trimmed_fastq:    Path to trimmed FASTQ from QC stage
        reference_genome: Path to indexed reference genome (bwa index required)
        sample_id:        Unique sample identifier
        outdir:           Output directory for BAM and QC files
        config:           AlignmentConfig settings

    Returns:
        AlignmentResult with all metrics and pass/fail status
    """
    if config is None:
        config = AlignmentConfig()

    outdir_path = Path(outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)

    # Output paths
    host_bam        = outdir_path / f"{sample_id}_host.bam"
    microbial_fastq = outdir_path / f"{sample_id}_microbial.fastq.gz"
    aligned_bam     = outdir_path / f"{sample_id}.bam"
    flagstat_path   = outdir_path / f"{sample_id}.flagstat"
    audit_path      = outdir_path / f"{sample_id}_alignment_audit.json"

    # ── Step 1: Align to human reference to identify host reads ──────────────
    logger.info(f"[{sample_id}] Step 1: Aligning to human reference (GRCh38) for host removal")
    _run_cmd([
        "bwa", "mem",
        "-t", str(config.threads),
        *config.bwa_extra_args.split(),
        reference_genome,
        str(trimmed_fastq),
        "|",
        "samtools", "view", "-bS", "-",
        "|",
        "samtools", "sort", "-o", str(host_bam),
    ], shell=True)

    _run_cmd(["samtools", "index", str(host_bam)])

    # ── Step 2: Extract unmapped reads (microbial fraction) ───────────────────
    logger.info(f"[{sample_id}] Step 2: Extracting microbial (non-human) reads")
    _run_cmd([
        "samtools", "fastq",
        "-f", "4",              # flag 4 = unmapped = microbial
        "-0", str(microbial_fastq),
        str(host_bam),
    ])

    # Count host reads removed
    host_flagstat = _run_flagstat(host_bam)
    total_reads      = _parse_flagstat_total(host_flagstat)
    host_reads       = _parse_flagstat_mapped(host_flagstat)
    host_removal_pct = (host_reads / total_reads * 100) if total_reads > 0 else 0.0
    microbial_reads  = total_reads - host_reads

    logger.info(
        f"[{sample_id}] Host removal: {host_reads:,} human reads removed "
        f"({host_removal_pct:.1f}%), {microbial_reads:,} microbial reads retained"
    )

    # ── Step 3: Align microbial reads to reference ────────────────────────────
    logger.info(f"[{sample_id}] Step 3: Aligning microbial reads to reference")
    _run_cmd([
        "bwa", "mem",
        "-t", str(config.threads),
        reference_genome,
        str(microbial_fastq),
        "|",
        "samtools", "view", "-bS", "-F", "4",  # keep only mapped
        "|",
        "samtools", "sort", "-o", str(aligned_bam),
    ], shell=True)

    # ── Step 4: Index the aligned BAM ─────────────────────────────────────────
    logger.info(f"[{sample_id}] Step 4: Indexing BAM")
    _run_cmd(["samtools", "index", str(aligned_bam)])

    # ── Step 5: Flagstat QC ───────────────────────────────────────────────────
    logger.info(f"[{sample_id}] Step 5: Running samtools flagstat")
    flagstat_text = _run_flagstat(aligned_bam)
    flagstat_path.write_text(flagstat_text)

    mapped_reads      = _parse_flagstat_mapped(flagstat_text)
    alignment_rate    = (mapped_reads / microbial_reads * 100) if microbial_reads > 0 else 0.0
    unmapped_pct      = 100.0 - alignment_rate

    # ── Step 6: Pass / fail evaluation ───────────────────────────────────────
    failures = []
    if alignment_rate < config.min_alignment_rate:
        failures.append(
            f"Alignment rate {alignment_rate:.1f}% below minimum {config.min_alignment_rate:.1f}%"
        )
    if unmapped_pct > config.max_unmapped_pct:
        failures.append(
            f"Unmapped reads {unmapped_pct:.1f}% exceeds maximum {config.max_unmapped_pct:.1f}%"
        )
    if mapped_reads == 0:
        failures.append("Zero reads mapped — check reference genome and FASTQ integrity")

    result = AlignmentResult(
        sample_id=sample_id,
        bam_path=str(aligned_bam),
        bai_path=str(aligned_bam) + ".bai",
        flagstat_path=str(flagstat_path),
        total_reads=total_reads,
        mapped_reads=mapped_reads,
        alignment_rate_pct=round(alignment_rate, 2),
        host_reads_removed=host_reads,
        host_removal_pct=round(host_removal_pct, 2),
        unmapped_pct=round(unmapped_pct, 2),
        passed=len(failures) == 0,
        failure_reasons=failures,
    )

    # ── Step 7: Write audit JSON ──────────────────────────────────────────────
    with open(audit_path, "w") as f:
        json.dump({
            "sample_id": result.sample_id,
            "total_reads": result.total_reads,
            "mapped_reads": result.mapped_reads,
            "alignment_rate_pct": result.alignment_rate_pct,
            "host_reads_removed": result.host_reads_removed,
            "host_removal_pct": result.host_removal_pct,
            "unmapped_pct": result.unmapped_pct,
            "passed": result.passed,
            "failure_reasons": result.failure_reasons,
        }, f, indent=2)

    status = "PASS" if result.passed else "FAIL"
    logger.info(f"[{sample_id}] Alignment QC: {status}")
    for reason in failures:
        logger.warning(f"  ✗ {reason}")

    return result


# ── Helpers ───────────────────────────────────────────────────────────────────
def _run_cmd(cmd: list[str], shell: bool = False) -> str:
    if shell:
        cmd_str = " ".join(cmd)
        result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
    else:
        result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed (exit {result.returncode}):\n"
            f"  cmd: {' '.join(cmd) if isinstance(cmd, list) else cmd}\n"
            f"  stderr: {result.stderr[:500]}"
        )
    return result.stdout


def _run_flagstat(bam_path: Path) -> str:
    result = subprocess.run(
        ["samtools", "flagstat", str(bam_path)],
        capture_output=True, text=True
    )
    return result.stdout


def _parse_flagstat_total(flagstat: str) -> int:
    """Extract total read count from samtools flagstat output."""
    for line in flagstat.splitlines():
        if "in total" in line:
            try:
                return int(line.split()[0])
            except (ValueError, IndexError):
                pass
    return 0


def _parse_flagstat_mapped(flagstat: str) -> int:
    """Extract mapped read count from samtools flagstat output."""
    for line in flagstat.splitlines():
        if "mapped (" in line:
            try:
                return int(line.split()[0])
            except (ValueError, IndexError):
                pass
    return 0
