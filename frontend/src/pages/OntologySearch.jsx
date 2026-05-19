import { useState } from "react";

const MOCK_RESULTS = {
  "crohn": [
    { code: "K50.0", display: "Crohn's disease of small intestine", system: "ICD-10", synonyms: ["Regional ileitis"] },
    { code: "K50.1", display: "Crohn's disease of large intestine",  system: "ICD-10", synonyms: ["Granulomatous colitis"] },
    { code: "34000006", display: "Crohn's disease (disorder)",        system: "SNOMED", synonyms: ["Regional enteritis", "Granulomatous ileocolitis"] },
  ],
  "microbiome": [
    { code: "726075006", display: "Microbiome of gastrointestinal tract", system: "SNOMED", synonyms: ["Gut microbiome"] },
    { code: "LA28441-1",  display: "Microbiome panel",                    system: "LOINC",  synonyms: [] },
  ],
  "stool": [
    { code: "119339001", display: "Stool specimen",           system: "SNOMED", synonyms: ["Fecal sample", "Feces"] },
    { code: "2339-0",    display: "Glucose [Mass/volume] in Stool", system: "LOINC", synonyms: [] },
  ],
};

const SYSTEMS = ["All", "SNOMED", "ICD-10", "LOINC", "MedDRA", "ATC"];

const systemBadge = (s) => {
  const map = { "SNOMED": "badge-success", "ICD-10": "badge-info", "LOINC": "badge-warn", "MedDRA": "badge-danger", "ATC": "badge-danger" };
  return <span className={`badge ${map[s] || "badge-info"}`}>{s}</span>;
};

export default function OntologySearch() {
  const [query,   setQuery]   = useState("");
  const [system,  setSystem]  = useState("All");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);

    setTimeout(() => {
      const key = Object.keys(MOCK_RESULTS).find(k => query.toLowerCase().includes(k));
      let res = key ? MOCK_RESULTS[key] : [];
      if (system !== "All") res = res.filter(r => r.system === system);
      setResults(res);
      setLoading(false);
    }, 700);
  };

  const examples = ["Crohn disease", "gut microbiome", "stool specimen", "Bacteroides", "IBS"];

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-title">Ontology Search</div>
        <div className="page-sub">Search SNOMED-CT, ICD-10, LOINC, MedDRA, and ATC clinical terminologies</div>
      </div>

      {/* Search bar */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
          <input
            placeholder="Search e.g. Crohn disease, gut microbiome, stool specimen..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSearch()}
            style={{ flex: 1 }}
          />
          <select style={{ width: 140 }} value={system} onChange={e => setSystem(e.target.value)}>
            {SYSTEMS.map(s => <option key={s}>{s}</option>)}
          </select>
          <button className="btn btn-primary" onClick={handleSearch} style={{ whiteSpace: "nowrap" }}>
            Search
          </button>
        </div>

        {/* Example queries */}
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 12, color: "var(--text-3)" }}>Try:</span>
          {examples.map(e => (
            <button
              key={e}
              className="btn"
              style={{ padding: "4px 10px", fontSize: 11 }}
              onClick={() => { setQuery(e); }}
            >
              {e}
            </button>
          ))}
        </div>
      </div>

      {/* Supported ontologies info */}
      <div className="grid-3" style={{ marginBottom: 24 }}>
        {[
          { name: "SNOMED-CT",  desc: "Clinical findings, organism classification, body sites",  badge: "badge-success", count: "350,000+ concepts" },
          { name: "ICD-10",     desc: "Disease codes linked to microbiome phenotypes",            badge: "badge-info",    count: "70,000+ codes"    },
          { name: "LOINC",      desc: "Lab observation codes for sequencing metadata",            badge: "badge-warn",    count: "90,000+ terms"    },
          { name: "MedDRA",     desc: "Adverse event and symptom annotation",                     badge: "badge-danger",  count: "26,000+ terms"    },
          { name: "ATC",        desc: "Drug classification for clinical metadata",                badge: "badge-danger",  count: "6,000+ codes"     },
        ].slice(0, 3).map(o => (
          <div className="card" key={o.name}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
              <span className={`badge ${o.badge}`}>{o.name}</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--text-3)" }}>{o.count}</span>
            </div>
            <div style={{ fontSize: 12, color: "var(--text-2)" }}>{o.desc}</div>
          </div>
        ))}
      </div>

      {/* Results */}
      {loading && (
        <div className="card" style={{ textAlign: "center", padding: 48 }}>
          <div style={{ color: "var(--text-3)", fontFamily: "var(--font-mono)", fontSize: 13 }}>
            Searching ontologies...
          </div>
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: 48 }}>
          <div style={{ color: "var(--text-3)", fontSize: 13 }}>
            No results found for "{query}"
            {system !== "All" && ` in ${system}`}.
          </div>
          <div style={{ color: "var(--text-3)", fontSize: 12, marginTop: 8 }}>
            Try a different term or select "All" systems.
          </div>
        </div>
      )}

      {!loading && results.length > 0 && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
            <div className="card-title" style={{ marginBottom: 0 }}>
              {results.length} result{results.length !== 1 ? "s" : ""} for "{query}"
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {results.map((r, i) => (
              <div
                key={i}
                style={{
                  padding: "16px 18px",
                  background: "var(--bg-3)",
                  borderRadius: "var(--radius)",
                  border: "1px solid var(--border)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                  <div>
                    <span className="mono" style={{ color: "var(--accent)", fontSize: 13, fontWeight: 500 }}>{r.code}</span>
                    <span style={{ margin: "0 10px", color: "var(--text-3)" }}>·</span>
                    <span style={{ fontSize: 14, color: "var(--text-1)", fontWeight: 500 }}>{r.display}</span>
                  </div>
                  {systemBadge(r.system)}
                </div>
                {r.synonyms.length > 0 && (
                  <div style={{ fontSize: 12, color: "var(--text-3)" }}>
                    Also known as: {r.synonyms.join(", ")}
                  </div>
                )}
                <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
                  <button className="btn" style={{ padding: "4px 10px", fontSize: 11 }}>
                    Map to sample
                  </button>
                  <button className="btn" style={{ padding: "4px 10px", fontSize: 11 }}>
                    Map to biomarker
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
