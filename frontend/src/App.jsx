import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import CaseDetail from "./CaseDetail.jsx";
import CaseIntake from "./CaseIntake.jsx";
import { AuditView, FeedbackView, MubitView } from "./Panels.jsx";
import { Chip, OutcomeChip, RecChip } from "./ui.jsx";

const TABS = [
  ["cases", "Cases"],
  ["feedback", "Feedback & evaluation"],
  ["mubit", "Mubit integration"],
  ["audit", "Audit log"],
];

export default function App() {
  const [tab, setTab] = useState("cases");
  const [health, setHealth] = useState(null);
  const [policy, setPolicy] = useState(null);
  const [cases, setCases] = useState([]);
  const [selected, setSelected] = useState(null);
  const [intake, setIntake] = useState(false);
  const [error, setError] = useState(null);

  const loadCases = useCallback(async () => {
    try {
      setCases(await api.cases());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(`Backend unreachable: ${e.message}`));
    api.policy().then(setPolicy).catch(() => {});
    loadCases();
  }, [loadCases]);

  const seed = async () => {
    try {
      const r = await api.seedDemo();
      await loadCases();
      if (r.created.length && !selected) setSelected(r.created[0]);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">PCN</span>
          <div>
            <div className="brand-name">Review Copilot</div>
            <div className="brand-sub">Decision support for authorised officers · synthetic demo data</div>
          </div>
        </div>
        <nav className="tabs">
          {TABS.map(([id, label]) => (
            <button key={id} className={tab === id ? "tab active" : "tab"} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </nav>
        {health && (
          <div className="provider">
            {health.ai_provider === "mubit" ? (
              <Chip tone="ok" title={health.mubit_base_url}>Mubit live · {health.model}</Chip>
            ) : (
              <Chip tone="warn" title="Set MUBIT_API_KEY to use Mubit">Offline stub — not Mubit</Chip>
            )}
            <span className="muted small">{health.ruleset_version}</span>
          </div>
        )}
      </header>

      {error && (
        <div className="banner error" onClick={() => setError(null)}>
          {error} <span className="muted">(click to dismiss)</span>
        </div>
      )}

      {tab === "cases" && (
        <div className="cases-layout">
          <aside className="case-list">
            <div className="list-actions">
              <button className="btn primary" onClick={() => { setIntake(true); setSelected(null); }}>New case</button>
              <button className="btn" onClick={seed}>Load demo cases</button>
            </div>
            {cases.length === 0 && <p className="muted pad">No cases yet. Load the synthetic demo set or create one.</p>}
            <ul>
              {cases.map((c) => (
                <li key={c.id} className={selected === c.id ? "selected" : ""}
                    onClick={() => { setSelected(c.id); setIntake(false); }}>
                  <div className="row-between">
                    <strong className="mono">{c.pcn_ref}</strong>
                    <span className="code-badge">{c.contravention_code}</span>
                  </div>
                  <div className="muted small ellipsis">{c.location}</div>
                  <div className="chips">
                    <Chip tone="neutral">{c.status.replace("_", " ")}</Chip>
                    {c.final_outcome ? <OutcomeChip outcome={c.final_outcome} /> : c.ai_recommendation && <RecChip rec={c.ai_recommendation} prefix="AI " />}
                  </div>
                </li>
              ))}
            </ul>
          </aside>
          <main className="case-main">
            {intake ? (
              <CaseIntake onCreated={async (id) => { await loadCases(); setIntake(false); setSelected(id); }}
                          onImported={loadCases} />
            ) : selected ? (
              <CaseDetail key={selected} caseId={selected} policy={policy} onChanged={loadCases} onError={setError} />
            ) : (
              <div className="empty">Select a case to review.</div>
            )}
          </main>
        </div>
      )}
      {tab === "feedback" && <FeedbackView onError={setError} />}
      {tab === "mubit" && <MubitView health={health} />}
      {tab === "audit" && <AuditView />}
    </div>
  );
}
