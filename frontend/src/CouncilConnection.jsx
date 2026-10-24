import {useEffect, useState} from "react";
import {api} from "./api.js";
import {Icon} from "./Icons.jsx";
import {fmt} from "./ui.jsx";

const flow = [
  ["Council sends the case", "The case reference, appeal, records and evidence arrive together. Updates replace the source snapshot and require a fresh review.", "file"],
  ["Mubit reviews the facts", "Mubit prepares a recommendation using supplied records, evidence descriptions and the configured policy. Missing information is flagged.", "spark"],
  ["Officer makes the decision", "The officer checks the recommendation, chooses an outcome and approves the response. Uncertain cases can go for investigation.", "shield"],
  ["Approved result is collected", "The council connector collects the final decision and response, matched to the original case. A file export is also available.", "download"],
  ["Council confirms receipt", "The connector confirms only after saving the result in the source system. Until then, Civic keeps it available for collection.", "check"],
];

export default function CouncilConnection({canImport, onOpenCase, onImported}) {
  const [data,setData]=useState(null), [error,setError]=useState(""), [notice,setNotice]=useState("");
  const [loading,setLoading]=useState(true), [busy,setBusy]=useState(false), [revision,setRevision]=useState(0);
  useEffect(()=>{
    let active=true;setLoading(true);setError("");
    api.integrationStatus().then(d=>{if(active)setData(d);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[revision]);
  async function importFile(event) {
    const file=event.target.files[0];event.target.value="";
    if(!file)return;
    setBusy(true);setError("");setNotice("");
    try {
      if(file.size>30*1024*1024)throw new Error("Choose a package smaller than 30 MiB.");
      const result=await api.integrationImport(JSON.parse(await file.text()));
      setNotice(`Case ${result.status}. Open it below to request a Mubit review.`);
      await onImported();setRevision(n=>n+1);
    } catch(e) {setError(e.message);} finally {setBusy(false);}
  }
  return <div className="connection-page">
    <div className="section-heading row-between insights-heading"><div><span className="eyebrow">COUNCIL CONNECTION</span><h1>From case to council<span className="blue">.</span></h1><p>See where a case came from and whether its approved result has been received.</p></div><button className="btn" disabled={loading} onClick={()=>setRevision(n=>n+1)}>{loading?"Loading…":"Refresh status"}</button></div>
    {error&&<p className="alert error" role="alert">{error}</p>}
    {notice&&<p className="alert" role="status">{notice}</p>}
    {data&&<>
      <div className="connection-summary">
        <section className="stat-card"><span className="eyebrow">COUNCIL</span><h2>{data.council_name}</h2><p className="small muted">{data.council_id}</p></section>
        <section className="stat-card"><span className="eyebrow">CASE SYSTEM</span><h2>{data.source_system==="generic"?"Generic file / API":data.source_system}</h2><p className="small muted">One council and source system per workspace</p></section>
        <section className="stat-card"><span className="eyebrow">CONNECTION STATUS</span><h2>{data.connector_enabled?"Ready for testing":"Awaiting setup"}</h2><p className="small muted">Sandbox · no live council connection verified</p></section>
        <section className="stat-card"><span className="eyebrow">AI REVIEWS</span><h2>{data.mubit_ready?"Mubit configured":"Mubit setup needed"}</h2><p className="small muted">A successful Mubit review is required before a final decision on an imported case.</p></section>
      </div>
      <section className="connection-flow" aria-label="Council case workflow">{flow.map(([title,body,icon],i)=><article key={title}><div className="row-between"><span className="number-label">0{i+1}</span><Icon name={icon}/></div><h2>{title}</h2><p>{body}</p></article>)}</section>
      <p className="alert">This workspace accepts synthetic cases and uses demonstration policies. Different councils can use this exchange format after their supplier maps its fields and their policy is approved. Attached photos and PDFs are stored for officers; Mubit currently reads their supplied descriptions.</p>
      <div className="connection-actions"><a className="btn" href="/api/integration/sample"><Icon name="download"/>Download test package</a>{canImport&&<label className="btn primary connection-file">{busy?"Importing…":"Import test package"}<input type="file" accept="application/json" aria-label="Import council test package" disabled={busy} onChange={importFile}/></label>}<a className="btn" href="/api/integration/export"><Icon name="download"/>Export approved results</a></div>
      <p className="small muted">Downloading results does not mark them received. The source-system connector must confirm successful storage.</p>
      <section className="card connection-records"><div className="card-head"><h3>Cases received · latest 100</h3><span className="small muted">Source references stay attached throughout the review.</span></div>{data.cases.length?<table className="table"><thead><tr><th>Case</th><th>Source reference</th><th>Version</th><th>Review status</th><th>Received</th></tr></thead><tbody>{data.cases.map(c=><tr key={c.case_id}><td><button className="text-btn" onClick={()=>onOpenCase(c.case_id)}>{c.pcn_ref}</button></td><td>{c.source_case_id}</td><td>{c.source_version}</td><td>{({validated:"Awaiting review",ai_reviewed:"Reviewed",ai_failed:"Review needs attention",escalated:"Needs investigation",decided:"Decision saved"})[c.status]||c.status}</td><td>{fmt(c.imported_at)}</td></tr>)}</tbody></table>:<p className="muted">No council packages received yet. Download and import the test package to try the flow.</p>}</section>
      <section className="card"><div className="card-head"><h3>Result delivery · latest 100 decisions</h3></div>{data.results.length?<table className="table"><thead><tr><th>Case</th><th>Decision</th><th>Approved by</th><th>Delivery</th><th>Receipt</th></tr></thead><tbody>{data.results.map(r=><tr key={r.decision_id}><td>{r.pcn_ref}</td><td>{r.final_outcome==="representation_accepted"?"Accept appeal":"Reject appeal"}</td><td>{r.reviewer}</td><td><span className={`chip ${r.received_at?"ok":"warn"}`}>{r.received_at?"Receipt confirmed":"Awaiting receipt"}</span></td><td>{r.receipt_id||"—"}</td></tr>)}</tbody></table>:<p className="muted">Results appear after a Mubit review and an officer saves a final decision. Investigation referrals remain in Civic.</p>}</section>
      <details className="admin-import"><summary>Connection setup for your IT team</summary><p>Configure a separate workspace and database schema for each council. Set <code>PCN_COUNCIL_ID</code>, <code>PCN_COUNCIL_NAME</code> and <code>PCN_CASE_SYSTEM</code> before the first import. Set a private <code>PCN_INTEGRATION_KEY</code> of at least 32 characters in the server and connector environments.</p><p>The connector sends complete packages to <code>POST /api/integration/v1/cases</code>, collects <code>GET /api/integration/v1/results</code>, then confirms each result at <code>POST /api/integration/v1/results/:decision_id/receipt</code>. It uses its integration key as a Bearer token; it cannot approve decisions or administer users.</p><p>Set <code>AI_PROVIDER=mubit</code>, <code>MUBIT_API_KEY</code> and your Mubit route/model on the server. No model call is made just by importing. An officer starts the review.</p><p className="small muted">Current policy: {data.policy_version}. A supplier-specific connector and approved council policies are still needed for a live rollout.</p></details>
    </>}
  </div>;
}
