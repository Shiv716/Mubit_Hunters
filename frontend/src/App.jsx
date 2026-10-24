import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { api } from "./api.js";
import CaseDetail from "./CaseDetail.jsx";
import Login, { ApprovalPage } from "./Login.jsx";
import AccessRequests from "./AccessRequests.jsx";
import CaseIntake from "./CaseIntake.jsx";
import Insights from "./Insights.jsx";
import CouncilConnection from "./CouncilConnection.jsx";
import { AuditView, FeedbackView, MubitView } from "./Panels.jsx";
import { Icon, Mark } from "./Icons.jsx";

export default function App() {
  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem("civic-theme");
      if (saved === "light" || saved === "dark") return saved;
    } catch { /* Theme switching still works when browser storage is unavailable. */ }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#15191c" : "#f5f1e8");
    try { localStorage.setItem("civic-theme", theme); } catch { /* Keep the preference for this session. */ }
  }, [theme]);
  const themeSwitch = <ThemeSwitch theme={theme} onToggle={() => setTheme(t => t === "dark" ? "light" : "dark")} />;
  const [approvalToken, setApprovalToken] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get("approve"));
  useEffect(()=>{
    if(approvalToken) window.history.replaceState(null,"",window.location.pathname+window.location.search);
    const changed=()=>{const token=new URLSearchParams(window.location.hash.slice(1)).get("approve");if(token)setApprovalToken(token);};
    window.addEventListener("hashchange",changed);return()=>window.removeEventListener("hashchange",changed);
  },[approvalToken]);
  const [session, setSession] = useState(null);
  const [page, setPage] = useState("cases");
  const [adminTab, setAdminTab] = useState("feedback");
  const [health, setHealth] = useState(null);
  const [policy, setPolicy] = useState(null);
  const [cases, setCases] = useState([]);
  const [selected, setSelected] = useState(null);
  const [intake, setIntake] = useState(false);
  const [filter, setFilter] = useState("open");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [profile, setProfile] = useState(false);
  const [reviewer, setReviewer] = useState(() => localStorage.getItem("reviewer") || "Priya Shah");
  const [revision, setRevision] = useState(0);

  useEffect(() => { api.session().then(setSession).catch(e => setError(e.message)); }, []);
  const refresh = useCallback(async () => {
    const rows = await api.queue();
    setCases(rows);
    setRevision(v => v + 1);
    return rows;
  }, []);
  useEffect(() => {
    if (!session?.authenticated) return;
    if (session.reviewer) setReviewer(session.reviewer);
    Promise.all([api.health(), api.policy(), api.queue()]).then(([h, p, rows]) => {
      setHealth(h); setPolicy(p); setCases(rows); setSelected(rows.find(r => r.lane !== "done")?.id ?? rows[0]?.id ?? null);
    }).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [session]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 6000); return () => clearTimeout(t);
  }, [toast]);

  async function seed() {
    setSeeding(true); setError("");
    try { await api.seedDemo(); const rows = await refresh(); setSelected(rows[0]?.id); setToast("Sample appeals are ready to review."); }
    catch(e) { setError(e.message); } finally { setSeeding(false); }
  }
  async function saved(id, next) {
    const rows = await refresh();
    setToast("Decision recorded. Council delivery is tracked separately.");
    if (next) {
      const following = rows.find(r => r.id !== id && r.lane !== "done" && r.status !== "escalated");
      if (following) { setSelected(following.id); setFilter("open"); setSearch(""); }
    }
  }
  function chooseFilter(next) {
    setFilter(next);
    const matches = cases.filter(c => (next === "open" ? c.lane !== "done" : c.lane === next) &&
      `${c.pcn_ref} ${c.location} ${c.claim}`.toLowerCase().includes(search.toLowerCase()));
    setSelected(matches.find(c => c.id === selected)?.id ?? matches[0]?.id ?? null);
  }
  const open = cases.filter(c => c.lane !== "done");
  const counts = {open: open.length, ready: cases.filter(c=>c.lane==="ready").length,
    investigate: cases.filter(c=>c.lane==="investigate").length, done: cases.filter(c=>c.lane==="done").length};
  const visible = cases.filter(c => (filter === "open" ? c.lane !== "done" : c.lane === filter) &&
    `${c.pcn_ref} ${c.location} ${c.claim}`.toLowerCase().includes(search.toLowerCase()));
  const due = open.filter(c => c.days_left !== null && c.days_left <= 7).length;

  if (approvalToken) return <><div className="login-theme">{themeSwitch}</div><ApprovalPage token={approvalToken} onClose={()=>{setApprovalToken(null);api.session().then(setSession).catch(e=>setError(e.message));}}/></>;
  if (session && !session.authenticated) return <><div className="login-theme">{themeSwitch}</div><Login onLogin={setSession} session={session} /></>;
  return <div className="app">
    <a className="skip-link" href="#main-content">Skip to case workspace</a>
    <header className="topbar">
      <a className="brand" href="#" onClick={e=>{e.preventDefault();setPage("cases");}}><Mark/><span>civic<span className="brand-dot">.</span><small>REVIEW COPILOT</small></span></a>
      <nav className="main-nav" aria-label="Main navigation">
        <button className={page==="cases"?"nav-item active":"nav-item"} onClick={()=>setPage("cases")}><Icon name="inbox"/>Cases <span className="nav-count">{open.length}</span></button>
        <button className={page==="insights"?"nav-item active":"nav-item"} onClick={()=>setPage("insights")}><Icon name="chart"/>Insights</button>
        <button className={page==="connection"?"nav-item active":"nav-item"} onClick={()=>setPage("connection")}><Icon name="arrow"/>Council connection</button>
      </nav>
      <div className="top-right">
        {themeSwitch}
        <button className={`icon-btn ${page==="admin"?"selected":""}`} title="Workspace admin" aria-label="Workspace admin" onClick={()=>setPage("admin")}><Icon name="settings"/></button>
        <div className="profile-wrap"><button className="avatar" title="Reviewer profile" aria-label="Reviewer profile" onClick={()=>setProfile(!profile)}>{reviewer.split(" ").map(n=>n[0]).slice(0,2).join("")}</button>
        {profile && <div className="profile-popover"><label>Your reviewer name<input value={reviewer} disabled={session?.required} onChange={e=>{setReviewer(e.target.value);localStorage.setItem("reviewer",e.target.value);}}/></label><button className="btn" onClick={()=>setProfile(false)}>Done</button>{session?.required && <button className="btn" onClick={async()=>{await api.logout();setSession(await api.session());}}>Sign out</button>}</div>}</div>
      </div>
    </header>
    {error && <div className="alert error global-alert" role="alert"><span>{error}</span><button className="icon-btn" aria-label="Dismiss error" onClick={()=>setError("")}><Icon name="close"/></button></div>}
    {toast && <div className="toast" role="status"><Icon name="check"/>{toast}<button className="icon-btn" aria-label="Dismiss notification" onClick={()=>setToast("")}><Icon name="close" size={15}/></button></div>}
    {page==="cases" && <>
      <div className="workspace-heading"><div><div className="eyebrow">{health?.council_name||"Council workspace"} / PARKING SERVICES</div><h1>Your review desk<span className="blue">.</span></h1><p>The facts together. The final call, yours.</p><button className="text-btn small connection-indicator" onClick={()=>setPage("connection")}>Council connection · Sandbox setup <Icon name="arrow" size={13}/></button></div>
        <div className="desk-summary"><span><b>{open.length.toString().padStart(2,"0")}</b> in your queue</span><span className={due?"attention":""}><Icon name="clock" size={16}/>{due} due within 7 days</span><button className="btn primary" onClick={()=>setIntake(true)}><Icon name="plus" size={16}/>New appeal</button></div>
      </div>
      {loading ? <div className="empty-state" role="status"><span className="spinner"/>Opening your workspace…</div> : cases.length===0 ? <main id="main-content" className="welcome"><div className="welcome-icon"><Icon name="inbox" size={40}/></div><div className="eyebrow">A FRESH DESK</div><h2>Give every appeal<br/>a clear starting point.</h2><p>Bring the evidence, policy and response together.<br/>Try a set of fictional appeals to see the workflow.</p><button className="btn primary large" disabled={seeding} onClick={seed}>{seeding?"Loading…":"Explore sample appeals"}<Icon name="arrow"/></button><span className="small muted">Fictional council. Synthetic cases. No messages sent.</span></main> :
      <div className="workspace">
        <aside className="queue-panel" aria-label="Appeal queue"><div className="queue-heading"><h2>Case queue</h2><span className="mono muted">{String(visible.length).padStart(2,"0")}</span></div>
          <label className="search-box"><Icon name="search" size={16}/><input aria-label="Search cases" placeholder="Find a case or street…" value={search} onChange={e=>setSearch(e.target.value)}/>{search&&<button className="clear-search" aria-label="Clear search" onClick={()=>setSearch("")}><Icon name="close" size={14}/></button>}</label>
          <div className="queue-filters" role="group" aria-label="Filter cases">{[["open","Open"],["ready","Ready"],["investigate","Flagged"],["done","Done"]].map(([id,label])=><button key={id} aria-pressed={filter===id} className={filter===id?"active":""} onClick={()=>chooseFilter(id)}>{label}<span>{counts[id]}</span></button>)}</div>
          <div className="queue-list">{visible.map(c=><button key={c.id} className={`case-ticket ${selected===c.id?"selected":""}`} onClick={()=>setSelected(c.id)} aria-current={selected===c.id?"true":undefined}>
            <div className="row-between"><span className="mono ticket-id">{c.pcn_ref}</span><span className={`mini-status ${c.lane}`}>{({new:"TO REVIEW",ready:"READY",investigate:"FLAGGED",done:"DONE"})[c.lane]}</span></div>
            <h3>{c.location.replace(", Demo Borough","")}</h3><p>{c.claim}</p><div className="ticket-bottom"><span><Icon name="file" size={13}/>{c.evidence_count} evidence items</span><span className={c.days_left!==null&&c.days_left<=7&&c.lane!=="done"?"due-soon":""}>{c.lane==="done"?"Recorded":c.days_left===null?"No due date":c.days_left<0?`${Math.abs(c.days_left)}d overdue`:c.days_left===0?"Due today":`${c.days_left}d left`}</span></div>
          </button>)}{!visible.length&&<div className="queue-empty">No cases match this view.<button className="text-btn" onClick={()=>{setSearch("");setFilter("open");}}>Clear filters</button></div>}</div>
          <div className="queue-footer"><Icon name="shield" size={15}/><span>Every decision stays with you.</span></div>
        </aside>
        <main id="main-content" className="case-workspace">{selected ? <CaseDetail key={selected} caseId={selected} policy={policy} reviewer={reviewer} onChanged={refresh} onSaved={saved} onError={setError} health={health}/> : <div className="empty-state">Select an appeal to get started.</div>}</main>
      </div>}
    </>}
    {page==="insights"&&<main id="main-content"><Insights revision={revision} onError={setError}/></main>}
    {page==="connection"&&<main id="main-content"><CouncilConnection canImport={session?.owner||!session?.required} onImported={refresh} onOpenCase={id=>{setSelected(id);setFilter("open");setSearch("");setPage("cases");}}/></main>}
    {page==="admin"&&<main id="main-content" className="admin-page"><div className="section-heading"><div className="eyebrow">WORKSPACE ADMIN</div><h1>Behind the decisions<span className="blue">.</span></h1><p>Approved examples, model connections and the full audit trail.</p></div><div className="admin-tabs">{[["feedback","Learning & evaluation"],["mubit","Mubit connection"],["audit","Audit history"],...(session?.owner?[["access","Access requests"]]:[])].map(([id,label])=><button key={id} className={`btn ${adminTab===id?"primary":""}`} onClick={()=>setAdminTab(id)}>{label}</button>)}</div>{adminTab==="access"&&session?.owner?<AccessRequests/>:adminTab==="feedback"?<FeedbackView onError={setError}/>:adminTab==="mubit"?<MubitView health={health}/>:<AuditView/>}<details className="admin-import"><summary>Import synthetic cases</summary><p className="muted small">Choose an exported JSON array of cases.</p><input type="file" accept="application/json" aria-label="Import cases JSON" onChange={async e=>{const f=e.target.files[0];if(!f)return;try{const data=JSON.parse(await f.text());if(!Array.isArray(data))throw new Error("Choose a JSON array of cases.");const r=await api.importCases(data);await refresh();setToast(`Imported ${r.created.length} cases; skipped ${r.skipped_duplicates.length} duplicates.`);}catch(err){setError(err.message);}e.target.value="";}}/><button className="btn" disabled={seeding} onClick={seed}>Load sample appeals</button></details></main>}
    {intake&&<CaseIntake onClose={()=>setIntake(false)} onCreated={async id=>{await refresh();setSelected(id);setIntake(false);setPage("cases");setFilter("open");setSearch("");setToast("Appeal added to your queue.");}}/>}
  </div>;
}

function ThemeSwitch({theme, onToggle}) {
  return <button type="button" className="theme-toggle" role="switch" aria-label="Dark mode"
    aria-checked={theme === "dark"} title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} onClick={onToggle}>
    <span className={theme === "light" ? "theme-option active" : "theme-option"}><Icon name="sun" size={16}/></span>
    <span className={theme === "dark" ? "theme-option active" : "theme-option"}><Icon name="moon" size={16}/></span>
  </button>;
}
