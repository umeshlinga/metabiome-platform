export default function Dashboard({ onNavigate }) {
  const stats = [
    { label: "Total Samples",    value: "1,284",  change: "+12 this week" },
    { label: "Pipeline Runs",    value: "3,891",  change: "+48 today" },
    { label: "Subjects",         value: "412",    change: "+3 this month" },
    { label: "Biomarkers Found", value: "28,440", change: "across all runs" },
  ];

  const recentRuns = [
    { sample: "SRR2726945", subject: "HMP_001", status: "success",  started: "2 min ago",  duration: "43 min" },
    { sample: "SRR2726946", subject: "HMP_001", status: "running",  started: "18 min ago", duration: "—" },
    { sample: "SRR2726947", subject: "HMP_002", status: "success",  started: "1 hr ago",   duration: "51 min" },
    { sample: "SRR2726948", subject: "HMP_003", status: "failed",   started: "2 hr ago",   duration: "8 min" },
    { sample: "SRR2726949", subject: "HMP_004", status: "queued",   started: "just now",   duration: "—" },
  ];

  const topTaxa = [
    { name: "Faecalibacterium prausnitzii", abund: 18.2 },
    { name: "Bacteroides uniformis",        abund: 11.0 },
    { name: "Bifidobacterium longum",       abund: 8.9  },
    { name: "Roseburia intestinalis",       abund: 7.4  },
    { name: "Akkermansia muciniphila",      abund: 5.1  },
  ];

  const statusBadge = (s) => {
    const map = { success: "badge-success", running: "badge-info", failed: "badge-danger", queued: "badge-warn" };
    return <span className={`badge ${map[s]}`}>{s}</span>;
  };

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Dashboard</div>
        <div className="page-sub">MetaBiome Platform — microbiome intelligence overview</div>
      </div>

      {/* Stat cards */}
      <div className="stat-grid">
        {stats.map(s => (
          <div className="stat-card" key={s.label}>
            <div className="stat-label">{s.label}</div>
            <div className="stat-value">{s.value}</div>
            <div className="stat-change">{s.change}</div>
          </div>
        ))}
      </div>

      <div className="grid-2" style={{ marginBottom: 24 }}>
        {/* Recent pipeline runs */}
        <div className="card">
          <div className="card-title">Recent pipeline runs</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Sample</th>
                  <th>Subject</th>
                  <th>Status</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map(r => (
                  <tr key={r.sample}>
                    <td className="mono" style={{ color: "var(--accent)", fontSize: 12 }}>{r.sample}</td>
                    <td style={{ color: "var(--text-2)" }}>{r.subject}</td>
                    <td>{statusBadge(r.status)}</td>
                    <td style={{ color: "var(--text-3)", fontSize: 12 }}>{r.started}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Top taxa */}
        <div className="card">
          <div className="card-title">Top taxa — latest run</div>
          <div className="bar-chart">
            {topTaxa.map(t => (
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
      </div>

      {/* Quick actions */}
      <div className="card">
        <div className="card-title">Quick actions</div>
        <div style={{ display: "flex", gap: 12 }}>
          <button className="btn btn-primary" onClick={() => onNavigate("samples")}>
            ＋ Upload FASTQ
          </button>
          <button className="btn" onClick={() => onNavigate("pipeline")}>
            ◎ Submit pipeline run
          </button>
          <button className="btn" onClick={() => onNavigate("results")}>
            ◇ View results
          </button>
          <button className="btn" onClick={() => onNavigate("ontology")}>
            ⬢ Search ontology
          </button>
        </div>
      </div>
    </div>
  );
}
