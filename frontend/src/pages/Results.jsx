import { useState } from "react";

const LONGITUDINAL = {
  shannon_diversity: [
    { timepoint: 1, date: "Mar 2024", value: 3.82 },
    { timepoint: 2, date: "Jun 2024", value: 3.61 },
    { timepoint: 3, date: "Sep 2024", value: 3.74 },
  ],
  firmicutes_bacteroidetes_ratio: [
    { timepoint: 1, date: "Mar 2024", value: 1.24 },
    { timepoint: 2, date: "Jun 2024", value: 1.38 },
    { timepoint: 3, date: "Sep 2024", value: 1.19 },
  ],
  butyrate_producers_enrichment: [
    { timepoint: 1, date: "Mar 2024", value: 0.31 },
    { timepoint: 2, date: "Jun 2024", value: 0.29 },
    { timepoint: 3, date: "Sep 2024", value: 0.34 },
  ],
};

const TAXA = [
  { name: "Faecalibacterium prausnitzii", rank: "species", abund: 18.23, reads: "195,000" },
  { name: "Bacteroides uniformis",        rank: "species", abund: 11.02, reads: "117,800" },
  { name: "Bifidobacterium longum",       rank: "species", abund: 8.91,  reads: "95,300"  },
  { name: "Roseburia intestinalis",       rank: "species", abund: 7.43,  reads: "79,400"  },
  { name: "Akkermansia muciniphila",      rank: "species", abund: 5.12,  reads: "54,700"  },
  { name: "Firmicutes",                   rank: "phylum",  abund: 47.38, reads: "506,400" },
  { name: "Bacteroidetes",                rank: "phylum",  abund: 38.21, reads: "408,400" },
];

const BIOMARKERS = [
  { name: "shannon_diversity",              type: "diversity",   value: 3.82, unit: "bits",    interp: "normal" },
  { name: "firmicutes_bacteroidetes_ratio", type: "ratio",       value: 1.24, unit: "ratio",   interp: "normal" },
  { name: "butyrate_producers_enrichment",  type: "enrichment",  value: 0.31, unit: "fraction",interp: "high"   },
  { name: "chao1_richness",                 type: "diversity",   value: 418,  unit: "species", interp: "normal" },
  { name: "simpson_index",                  type: "diversity",   value: 0.94, unit: "index",   interp: "normal" },
];

const interpBadge = (i) => {
  const map = { normal: "badge-success", high: "badge-warn", low: "badge-danger" };
  return <span className={`badge ${map[i]}`}>{i}</span>;
};

// Simple SVG sparkline chart
function SparkChart({ data, color = "var(--accent)" }) {
  const min = Math.min(...data.map(d => d.value));
  const max = Math.max(...data.map(d => d.value));
  const range = max - min || 1;
  const W = 300, H = 80, pad = 16;

  const points = data.map((d, i) => {
    const x = pad + (i / (data.length - 1)) * (W - pad * 2);
    const y = H - pad - ((d.value - min) / range) * (H - pad * 2);
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width={W} height={H} style={{ overflow: "visible" }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
      {data.map((d, i) => {
        const x = pad + (i / (data.length - 1)) * (W - pad * 2);
        const y = H - pad - ((d.value - min) / range) * (H - pad * 2);
        return (
          <g key={i}>
            <circle cx={x} cy={y} r={4} fill={color} />
            <text x={x} y={y - 10} textAnchor="middle" fill="var(--text-2)" fontSize="10" fontFamily="var(--font-mono)">
              {d.value}
            </text>
            <text x={x} y={H - 2} textAnchor="middle" fill="var(--text-3)" fontSize="10" fontFamily="var(--font-mono)">
              {d.date}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function Results() {
  const [selectedMarker, setSelectedMarker] = useState("shannon_diversity");
  const [selectedSubject, setSelectedSubject] = useState("HMP_001");

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Results</div>
        <div className="page-sub">Biomarkers, taxa profiles, and longitudinal trends</div>
      </div>

      {/* Subject selector */}
      <div className="card" style={{ marginBottom: 24, display: "flex", alignItems: "center", gap: 16 }}>
        <span style={{ fontSize: 13, color: "var(--text-2)" }}>Subject:</span>
        {["HMP_001", "HMP_002", "HMP_003"].map(s => (
          <button
            key={s}
            className="btn"
            onClick={() => setSelectedSubject(s)}
            style={selectedSubject === s ? { borderColor: "var(--accent)", color: "var(--accent)" } : {}}
          >
            {s}
          </button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-3)", fontFamily: "var(--font-mono)" }}>
          Sample: SRR2726945 · Run: run-abc123 · 3 timepoints
        </span>
      </div>

      {/* Longitudinal chart */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div className="card-title" style={{ marginBottom: 0 }}>Longitudinal trend — {selectedSubject}</div>
          <select style={{ width: "auto" }} value={selectedMarker} onChange={e => setSelectedMarker(e.target.value)}>
            {Object.keys(LONGITUDINAL).map(k => (
              <option key={k} value={k}>{k.replace(/_/g, " ")}</option>
            ))}
          </select>
        </div>
        <SparkChart data={LONGITUDINAL[selectedMarker]} />
        <div style={{ marginTop: 12, fontSize: 12, color: "var(--text-3)" }}>
          Trend: <span style={{ color: "var(--accent)" }}>stable</span> — 3 timepoints over 6 months
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 24 }}>
        {/* Taxa table */}
        <div className="card">
          <div className="card-title">Taxa — top species</div>
          <div className="bar-chart">
            {TAXA.filter(t => t.rank === "species").map(t => (
              <div className="bar-row" key={t.name}>
                <div className="bar-label" title={t.name}>{t.name}</div>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${(t.abund / 20) * 100}%` }} />
                </div>
                <div className="bar-val">{t.abund}%</div>
              </div>
            ))}
          </div>
        </div>

        {/* Biomarkers */}
        <div className="card">
          <div className="card-title">Biomarkers</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Marker</th>
                  <th>Value</th>
                  <th>Interpretation</th>
                </tr>
              </thead>
              <tbody>
                {BIOMARKERS.map(b => (
                  <tr key={b.name}>
                    <td>
                      <div className="mono" style={{ fontSize: 11, color: "var(--text-1)" }}>{b.name.replace(/_/g, " ")}</div>
                      <div style={{ fontSize: 11, color: "var(--text-3)" }}>{b.type}</div>
                    </td>
                    <td>
                      <span className="mono" style={{ color: "var(--accent-2)", fontWeight: 500 }}>{b.value}</span>
                      <span style={{ color: "var(--text-3)", fontSize: 11 }}> {b.unit}</span>
                    </td>
                    <td>{interpBadge(b.interp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* QC summary */}
      <div className="card">
        <div className="card-title">QC metrics — run-abc123</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 16 }}>
          {[
            { label: "Raw reads",      value: "15.4M",  ok: true  },
            { label: "After trim",     value: "14.9M",  ok: true  },
            { label: "Alignment rate", value: "87.9%",  ok: true  },
            { label: "Dup rate",       value: "18.3%",  ok: true  },
            { label: "Variants",       value: "4,231",  ok: true  },
          ].map(m => (
            <div key={m.label} style={{ textAlign: "center" }}>
              <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 6, fontFamily: "var(--font-mono)", textTransform: "uppercase" }}>{m.label}</div>
              <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "var(--font-display)", color: m.ok ? "var(--accent)" : "var(--danger)" }}>{m.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
