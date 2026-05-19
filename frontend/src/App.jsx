import { useState } from "react";
import Dashboard from "./pages/Dashboard";
import Samples from "./pages/Samples";
import Pipeline from "./pages/Pipeline";
import Results from "./pages/Results";
import OntologySearch from "./pages/OntologySearch";
import "./App.css";

const NAV_ITEMS = [
  { id: "dashboard",  label: "Dashboard",       icon: "⬡" },
  { id: "samples",    label: "Samples",          icon: "◈" },
  { id: "pipeline",   label: "Pipeline",         icon: "◎" },
  { id: "results",    label: "Results",          icon: "◇" },
  { id: "ontology",   label: "Ontology Search",  icon: "⬢" },
];

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");

  const renderPage = () => {
    switch (activePage) {
      case "dashboard":  return <Dashboard onNavigate={setActivePage} />;
      case "samples":    return <Samples />;
      case "pipeline":   return <Pipeline />;
      case "results":    return <Results />;
      case "ontology":   return <OntologySearch />;
      default:           return <Dashboard onNavigate={setActivePage} />;
    }
  };

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">MB</div>
          <div>
            <div className="brand-name">MetaBiome</div>
            <div className="brand-sub">Platform v1.0</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              className={`nav-item ${activePage === item.id ? "active" : ""}`}
              onClick={() => setActivePage(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="status-dot" />
          <span>API connected</span>
        </div>
      </aside>

      {/* Main content */}
      <main className="main">
        {renderPage()}
      </main>
    </div>
  );
}
