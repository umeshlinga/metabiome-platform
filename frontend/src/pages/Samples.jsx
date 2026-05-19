import { useState } from "react";

const SAMPLES = [
  { code: "SRR2726945", subject: "HMP_001", date: "2024-03-15", timepoint: 1, site: "stool", status: "processed", reads: "15.4M" },
  { code: "SRR2726946", subject: "HMP_001", date: "2024-06-15", timepoint: 2, site: "stool", status: "qc_pass",   reads: "12.1M" },
  { code: "SRR2726947", subject: "HMP_002", date: "2024-03-20", timepoint: 1, site: "stool", status: "processed", reads: "18.2M" },
  { code: "SRR2726948", subject: "HMP_003", date: "2024-04-01", timepoint: 1, site: "stool", status: "qc_fail",   reads: "2.1M"  },
  { code: "SRR2726949", subject: "HMP_004", date: "2024-04-10", timepoint: 1, site: "stool", status: "received",  reads: "—"     },
];

const statusBadge = (s) => {
  const map = { processed: "badge-success", qc_pass: "badge-info", qc_fail: "badge-danger", received: "badge-warn" };
  return <span className={`badge ${map[s] || "badge-warn"}`}>{s}</span>;
};

export default function Samples() {
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded]   = useState(false);
  const [dragOver, setDragOver]   = useState(false);
  const [search, setSearch]       = useState("");

  const handleUpload = () => {
    setUploading(true);
    setTimeout(() => { setUploading(false); setUploaded(true); }, 2000);
  };

  const filtered = SAMPLES.filter(s =>
    s.code.includes(search) || s.subject.includes(search)
  );

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Samples</div>
        <div className="page-sub">Upload FASTQ files and manage sample metadata</div>
      </div>

      <div className="grid-2" style={{ marginBottom: 24 }}>
        {/* Upload zone */}
        <div className="card">
          <div className="card-title">Upload FASTQ</div>
          <div
            className="upload-zone"
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => { e.preventDefault(); setDragOver(false); handleUpload(); }}
            onClick={handleUpload}
            style={dragOver ? { borderColor: "var(--accent)", background: "var(--accent-dim)" } : {}}
          >
            {uploaded ? (
              <>
                <div className="upload-icon">✓</div>
                <div className="upload-text" style={{ color: "var(--accent)" }}>Upload complete</div>
                <div className="upload-hint">SRR2726950.fastq.gz → S3</div>
              </>
            ) : uploading ? (
              <>
                <div className="upload-icon">⟳</div>
                <div className="upload-text">Uploading to S3...</div>
                <div style={{ marginTop: 12 }}>
                  <div className="progress-bar"><div className="progress-fill" style={{ width: "65%" }} /></div>
                </div>
              </>
            ) : (
              <>
                <div className="upload-icon">⬆</div>
                <div className="upload-text">Drop FASTQ file here or click to browse</div>
                <div className="upload-hint">.fastq or .fastq.gz · max 50GB</div>
              </>
            )}
          </div>

          {/* Sample metadata form */}
          <div style={{ marginTop: 20, display: "flex", flexDirection: "column", gap: 10 }}>
            <div className="card-title">Sample metadata</div>
            <input placeholder="Sample code (e.g. SRR2726950)" />
            <input placeholder="Subject ID (e.g. HMP_005)" />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input type="date" />
              <input placeholder="Timepoint (e.g. 1)" type="number" />
            </div>
            <select>
              <option>stool</option>
              <option>saliva</option>
              <option>skin</option>
            </select>
            <button className="btn btn-primary" style={{ marginTop: 4 }}>
              Register sample
            </button>
          </div>
        </div>

        {/* Stats */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {[
            { label: "Total samples",    value: "1,284" },
            { label: "Processed",        value: "1,101" },
            { label: "QC failed",        value: "23"    },
            { label: "Awaiting pipeline",value: "160"   },
          ].map(s => (
            <div className="stat-card" key={s.label}>
              <div className="stat-label">{s.label}</div>
              <div className="stat-value" style={{ fontSize: 22 }}>{s.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Sample table */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div className="card-title" style={{ marginBottom: 0 }}>All samples</div>
          <input
            placeholder="Search by code or subject..."
            style={{ width: 240 }}
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Sample code</th>
                <th>Subject</th>
                <th>Collection date</th>
                <th>Timepoint</th>
                <th>Reads</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(s => (
                <tr key={s.code}>
                  <td className="mono" style={{ color: "var(--accent)", fontSize: 12 }}>{s.code}</td>
                  <td style={{ color: "var(--text-2)" }}>{s.subject}</td>
                  <td style={{ color: "var(--text-2)" }}>{s.date}</td>
                  <td style={{ color: "var(--text-3)" }}>T{s.timepoint}</td>
                  <td className="mono" style={{ color: "var(--text-2)", fontSize: 12 }}>{s.reads}</td>
                  <td>{statusBadge(s.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
