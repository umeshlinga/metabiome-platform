import { useState } from "react";

const RUNS = [
  {
    id: "run-abc123", sample: "SRR2726945", subject: "HMP_001",
    status: "success", version: "1.0.0",
    started: "2024-03-15 10:00", duration: "43 min",
    stages: {
      fastq_qc:   { passed: true,  label: "FASTQ QC",        detail: "14.9M reads, Q35.2" },
      alignment:  { passed: true,  label: "Alignment",       detail: "87.9% aligned" },
      dedup:      { passed: true,  label: "Deduplication",   detail: "18.3% duplicates" },
      variant:    { passed: true,  label: "Variant calling", detail: "4,231 variants" },
      annotation: { passed: true,  label: "Annotation",      detail: "312 species" },
    },
  },
  {
    id: "run-def456", sample: "SRR2726946", subject: "HMP_001",
    status: "running", version: "1.0.0",
    started: "2024-06-15 14:22", duration: "—",
    stages: {
      fastq_qc:   { passed: true,  label: "FASTQ QC",        detail: "12.1M reads, Q34.8" },
      alignment:  { passed: true,  label: "Alignment",       detail: "85.2% aligned" },
      dedup:      { passed: null,  label: "Deduplication",   detail: "running..." },
      variant:    { passed: null,  label: "Variant calling", detail: "pending" },
      annotation: { passed: null,  label: "Annotation",      detail: "pending" },
    },
  },
  {
    id: "run-ghi789", sample: "SRR2726948", subject: "HMP_003",
    status: "failed", version: "1.0.0",
    started: "2024-04-01 09:10", duration: "8 min",
    stages: {
      fastq_qc:   { passed: false, label: "FASTQ QC",        detail: "Only 2.1M reads — below minimum" },
      alignment:  { passed: null,  label: "Alignment",       detail: "skipped" },
      dedup:      { passed: null,  label: "Deduplication",   detail: "skipped" },
      variant:    { passed: null,  label: "Variant calling", detail: "skipped" },
      annotation: { passed: null,  label: "Annotation",      detail: "skipped" },
    },
  },
];

const stageIcon = (passed) => {
  if (passed === true)  return <span style={{ color: "var(--accent)" }}>✓</span>;
  if (passed === false) return <span style={{ color: "var(--danger)" }}>✗</span>;
  return <span style={{ color: "var(--text-3)" }}>○</span>;
};

const statusBadge = (s) => {
  const map = { success: "badge-success", running: "badge-info", failed: "badge-danger", queued: "badge-warn" };
  return <span className={`badge ${map[s]}`}>{s}</span>;
};

export default function Pipeline() {
  const [selected, setSelected] = useState(RUNS[0]);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted]   = useState(false);

  const handleSubmit = () => {
    setSubmitting(true);
    setTimeout(() => { setSubmitting(false); setSubmitted(true); }, 1800);
  };

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Pipeline</div>
        <div className="page-sub">Submit and monitor metagenomic sequencing pipeline runs</div>
      </div>

      <div className="grid-2" style={{ marginBottom: 24 }}>
        {/* Submit form */}
        <div className="card">
          <div className="card-title">Submit new run</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-3)", display: "block", marginBottom: 6, fontFamily: "var(--font-mono)", textTransform: "uppercase" }}>Sample code</label>
              <input placeholder="e.g. SRR2726950" />
            </div>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-3)", display: "block", marginBottom: 6, fontFamily: "var(--font-mono)", textTransform: "uppercase" }}>FASTQ S3 path</label>
              <input placeholder="s3://metabiome-raw-fastq/raw/SRR.../..." className="mono" style={{ fontSize: 12 }} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-3)", display: "block", marginBottom: 6, fontFamily: "var(--font-mono)", textTransform: "uppercase" }}>Pipeline version</label>
              <select>
                <option>1.0.0</option>
                <option>0.9.2</option>
              </select>
            </div>

            {submitted ? (
              <div style={{ padding: "12px 16px", background: "var(--accent-dim)", borderRadius: "var(--radius)", color: "var(--accent)", fontSize: 13, fontWeight: 500 }}>
                ✓ Job submitted to AWS Batch — run ID: run-xyz999
              </div>
            ) : (
              <button className="btn btn-primary" onClick={handleSubmit} disabled={submitting}>
                {submitting ? "Submitting..." : "◎ Submit pipeline run"}
              </button>
            )}
          </div>
        </div>

        {/* Run list */}
        <div className="card">
          <div className="card-title">Recent runs</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {RUNS.map(run => (
              <div
                key={run.id}
                onClick={() => setSelected(run)}
                style={{
                  padding: "12px 14px",
                  background: selected.id === run.id ? "var(--bg-4)" : "var(--bg-3)",
                  borderRadius: "var(--radius)",
                  cursor: "pointer",
                  border: selected.id === run.id ? "1px solid var(--accent)" : "1px solid transparent",
                  transition: "all 0.15s",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="mono" style={{ color: "var(--accent)", fontSize: 12 }}>{run.sample}</span>
                  {statusBadge(run.status)}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4, fontFamily: "var(--font-mono)" }}>
                  {run.started} · {run.duration}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Pipeline stage detail */}
      {selected && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <div>
              <div className="card-title" style={{ marginBottom: 4 }}>Run detail — {selected.id}</div>
              <span className="mono" style={{ fontSize: 12, color: "var(--text-2)" }}>{selected.sample} · {selected.subject}</span>
            </div>
            {statusBadge(selected.status)}
          </div>

          <div className="timeline">
            {Object.entries(selected.stages).map(([key, stage]) => (
              <div className="timeline-item" key={key}>
                <div className={`timeline-dot ${stage.passed === true ? "done" : ""}`}
                  style={stage.passed === false ? { borderColor: "var(--danger)", background: "var(--danger)" } : {}} />
                <div className="timeline-content">
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span className="timeline-title">{stage.label}</span>
                    {stageIcon(stage.passed)}
                  </div>
                  <div className="timeline-time">{stage.detail}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
