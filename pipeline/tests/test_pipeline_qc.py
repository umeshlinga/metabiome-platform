"""
MetaBiome Platform — Pipeline QC Pytest Checkpoints
These tests run AFTER each pipeline stage to validate outputs before proceeding.
They act as automated audit gates — if any test fails, the pipeline halts.
"""
import json
import os
import pytest
from pathlib import Path


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
def results_dir():
    """Path to pipeline output directory. Set via PIPELINE_RESULTS_DIR env var."""
    d = os.environ.get("PIPELINE_RESULTS_DIR", "results")
    return Path(d)


@pytest.fixture
def sample_id():
    return os.environ.get("PIPELINE_SAMPLE_ID", "test_sample")


@pytest.fixture
def qc_audit(results_dir, sample_id):
    """Load the QC audit JSON written by the FASTQ QC module."""
    audit_path = results_dir / f"{sample_id}_qc_audit.json"
    if not audit_path.exists():
        pytest.skip(f"QC audit file not found: {audit_path}")
    with open(audit_path) as f:
        return json.load(f)


# ── Stage 1: FASTQ QC checkpoints ─────────────────────────────────────────────
class TestFASTQQC:

    def test_trimmed_fastq_exists(self, results_dir, sample_id):
        """Trimmed FASTQ must be present before alignment can start."""
        trimmed = results_dir / f"{sample_id}_trimmed.fastq.gz"
        assert trimmed.exists(), f"Trimmed FASTQ not found: {trimmed}"

    def test_trimmed_fastq_not_empty(self, results_dir, sample_id):
        """Trimmed FASTQ must contain at least some reads."""
        trimmed = results_dir / f"{sample_id}_trimmed.fastq.gz"
        if trimmed.exists():
            assert trimmed.stat().st_size > 1000, "Trimmed FASTQ is suspiciously small (<1KB)"

    def test_raw_read_count_positive(self, qc_audit):
        """Pipeline must have seen at least some reads from the sequencer."""
        assert qc_audit["raw_read_count"] > 0, "No raw reads found in FASTQ"

    def test_min_reads_after_trimming(self, qc_audit):
        """Require at least 10,000 reads to survive trimming for meaningful analysis."""
        min_reads = int(os.environ.get("MIN_READS_AFTER_TRIM", 10_000))
        assert qc_audit["reads_after_trim"] >= min_reads, (
            f"Only {qc_audit['reads_after_trim']:,} reads survived trimming "
            f"(minimum: {min_reads:,})"
        )

    def test_mean_q_score_threshold(self, qc_audit):
        """Mean Q-score must meet the minimum quality threshold (default Q20)."""
        min_q = float(os.environ.get("MIN_Q_SCORE", 20.0))
        assert qc_audit["mean_q_score"] >= min_q, (
            f"Mean Q-score {qc_audit['mean_q_score']:.1f} below threshold {min_q}"
        )

    def test_adapter_removal_not_excessive(self, qc_audit):
        """If >50% of reads were adapters, something is wrong with library prep."""
        max_adapter_pct = float(os.environ.get("MAX_ADAPTER_PCT", 50.0))
        assert qc_audit["adapter_removal_pct"] <= max_adapter_pct, (
            f"Adapter content {qc_audit['adapter_removal_pct']:.1f}% exceeds {max_adapter_pct:.1f}% "
            f"— possible library prep issue"
        )

    def test_qc_module_passed(self, qc_audit):
        """The QC module itself must have flagged this sample as passing."""
        assert qc_audit["passed"], (
            f"QC module reported failure: {qc_audit['failure_reasons']}"
        )

    def test_fastqc_report_exists(self, results_dir, sample_id):
        """FastQC HTML report should be written for inspection."""
        report_dir = results_dir / "fastqc"
        assert report_dir.exists(), "FastQC output directory missing"


# ── Stage 2: Alignment checkpoints ────────────────────────────────────────────
class TestAlignment:

    @pytest.fixture
    def flagstat(self, results_dir, sample_id):
        flagstat_path = results_dir / f"{sample_id}.flagstat"
        if not flagstat_path.exists():
            pytest.skip(f"Flagstat not found: {flagstat_path}")
        return flagstat_path.read_text()

    def test_bam_exists(self, results_dir, sample_id):
        bam = results_dir / f"{sample_id}.bam"
        assert bam.exists(), f"BAM file not found: {bam}"

    def test_bam_index_exists(self, results_dir, sample_id):
        bai = results_dir / f"{sample_id}.bam.bai"
        assert bai.exists(), "BAM index (.bai) is missing — alignment incomplete"

    def test_alignment_rate_acceptable(self, flagstat):
        """At least 50% of microbial reads should align to the reference."""
        for line in flagstat.splitlines():
            if "mapped (" in line:
                pct_str = line.split("(")[1].split("%")[0].strip()
                try:
                    pct = float(pct_str)
                    min_alignment_rate = float(os.environ.get("MIN_ALIGNMENT_RATE", 50.0))
                    assert pct >= min_alignment_rate, (
                        f"Alignment rate {pct:.1f}% below minimum {min_alignment_rate:.1f}%"
                    )
                    return
                except ValueError:
                    pass
        pytest.skip("Could not parse alignment rate from flagstat")

    def test_no_zero_mapped_reads(self, flagstat):
        """Zero mapped reads indicates a critical failure (wrong reference? corrupt FASTQ?)."""
        for line in flagstat.splitlines():
            if "mapped (" in line:
                count = int(line.split()[0])
                assert count > 0, "Zero reads mapped — check reference genome and input FASTQ"
                return


# ── Stage 3: Deduplication checkpoints ───────────────────────────────────────
class TestDeduplication:

    @pytest.fixture
    def dup_metrics(self, results_dir, sample_id):
        metrics_path = results_dir / f"{sample_id}_dup_metrics.txt"
        if not metrics_path.exists():
            pytest.skip(f"Duplicate metrics not found: {metrics_path}")
        return metrics_path.read_text()

    def test_dedup_bam_exists(self, results_dir, sample_id):
        dedup_bam = results_dir / f"{sample_id}_dedup.bam"
        assert dedup_bam.exists(), "Dedup BAM not found"

    def test_duplicate_rate_not_excessive(self, dup_metrics):
        """Duplicate rates >80% suggest PCR over-amplification. Flag for review."""
        max_dup_rate = float(os.environ.get("MAX_DUPLICATE_RATE", 80.0))
        for line in dup_metrics.splitlines():
            if line.startswith("Unknown") or line[0].isdigit():
                cols = line.split("\t")
                if len(cols) >= 9:
                    try:
                        dup_pct = float(cols[8]) * 100
                        assert dup_pct <= max_dup_rate, (
                            f"Duplicate rate {dup_pct:.1f}% exceeds {max_dup_rate:.1f}% "
                            f"— check PCR cycles"
                        )
                        return
                    except (ValueError, IndexError):
                        pass


# ── Stage 4: Variant calling checkpoints ─────────────────────────────────────
class TestVariantCalling:

    def test_vcf_exists(self, results_dir, sample_id):
        vcf = results_dir / f"{sample_id}.vcf.gz"
        assert vcf.exists(), "VCF output not found"

    def test_vcf_index_exists(self, results_dir, sample_id):
        tbi = results_dir / f"{sample_id}.vcf.gz.tbi"
        assert tbi.exists(), "VCF index (.tbi) missing — bcftools index may have failed"

    def test_vcf_has_records(self, results_dir, sample_id):
        """An empty VCF (header only) likely indicates a pipeline problem."""
        vcf = results_dir / f"{sample_id}.vcf.gz"
        if vcf.exists():
            import subprocess
            result = subprocess.run(
                ["bcftools", "view", "-H", str(vcf)],
                capture_output=True, text=True
            )
            line_count = len([l for l in result.stdout.splitlines() if l.strip()])
            assert line_count > 0, "VCF contains no variant records"


# ── Stage 5: Taxonomy annotation checkpoints ──────────────────────────────────
class TestTaxonomyAnnotation:

    @pytest.fixture
    def kraken_report(self, results_dir, sample_id):
        report = results_dir / f"{sample_id}_kraken2.report"
        if not report.exists():
            pytest.skip(f"Kraken2 report not found: {report}")
        return report.read_text()

    def test_kraken2_report_exists(self, results_dir, sample_id):
        report = results_dir / f"{sample_id}_kraken2.report"
        assert report.exists(), "Kraken2 report missing"

    def test_at_least_one_species_identified(self, kraken_report):
        """Require at least one classified read for the sample to be informative."""
        species_lines = [
            l for l in kraken_report.splitlines()
            if l.strip() and l.split()[3] == "S"
        ]
        assert len(species_lines) > 0, "No species-level classifications found"

    def test_compositional_coverage(self, kraken_report):
        """The unclassified fraction should not exceed 90% — suggests DB mismatch."""
        max_unclassified = float(os.environ.get("MAX_UNCLASSIFIED_PCT", 90.0))
        for line in kraken_report.splitlines():
            cols = line.strip().split("\t")
            if len(cols) >= 4 and cols[3].strip() == "U":
                try:
                    unclassified_pct = float(cols[0])
                    assert unclassified_pct <= max_unclassified, (
                        f"Unclassified reads {unclassified_pct:.1f}% > {max_unclassified:.1f}% "
                        f"— check Kraken2 database"
                    )
                    return
                except ValueError:
                    pass
