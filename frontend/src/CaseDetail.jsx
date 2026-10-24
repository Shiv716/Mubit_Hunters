import { useEffect, useState } from "react";
import { api } from "./api.js";
import { Icon } from "./Icons.jsx";
import { fmt } from "./ui.jsx";

const labels = {accept:"Accept appeal", reject:"Reject appeal", needs_review:"Needs investigation"};
const outcomes = {representation_accepted:"Appeal accepted", representation_rejected:"Appeal rejected", escalated:"Under investigation"};
const titleCase = s => s.replaceAll("_"," ").replace(/^./,c=>c.toUpperCase());

export default function CaseDetail({caseId, policy, reviewer, onChanged, onSaved, onError, health}) {
  const [d,setD]=useState(null), [tab,setTab]=useState("evidence"), [busy,setBusy]=useState(false), [loadError,setLoadError]=useState("");
  const [outcome,setOutcome]=useState(""), [reason,setReason]=useState(""), [response,setResponse]=useState("");
  const [saving,setSaving]=useState(false), [drafting,setDrafting]=useState(false), [trace,setTrace]=useState(false);
  const [draftOutcome,setDraftOutcome]=useState("");
  const [draftError,setDraftError]=useState("");
  const [uploading,setUploading]=useState(null);
  const [draftVersion,setDraftVersion]=useState(0);
  useEffect(()=>{let active=true;api.getCase(caseId).then(x=>{if(active)setD(x);}).catch(e=>{if(active)setLoadError(e.message);});return()=>{active=false;};},[caseId]);
  useEffect(()=>{
    if (!outcome || outcome==="needs_review" || !d) {setDrafting(false);return;}
    let active=true;setDrafting(true);setDraftError("");
    const latest=d.ai_reviews[0];
    const explanation=reason.trim() || (outcome===latest?.effective_recommendation ? latest.parsed?.reason_summary||"" : "");
    api.draft(caseId,outcome,explanation).then(r=>{if(active){setResponse(r.text);setDraftOutcome(outcome);}}).catch(e=>{if(active)setDraftError(e.message);}).finally(()=>{if(active)setDrafting(false);});
    return()=>{active=false;};
  },[outcome,draftVersion]);
  if(loadError)return <div className="empty-state alert error" role="alert">{loadError}</div>;
  if(!d)return <div className="empty-state" role="status"><span className="spinner"/>Opening case…</div>;
  const c=d.case, checks=d.checks;
  const review=d.ai_reviews[0]?.check_id===checks?.id?d.ai_reviews[0]:null;
  const final=d.decisions.find(x=>x.final_outcome!=="escalated");
  const decided=d.status==="decided";
  const agrees=review&&review.status!=="failed"&&outcome===review.effective_recommendation&&outcome!=="needs_review";
  const needsReason=outcome&&!agrees;
  const mubitReview=review?.provider==="mubit"&&review?.status!=="failed";
  const aiAvailable=health?.ai_available&&(!d.integration||(health.ai_provider==="mubit"&&health.mubit_configured));
  const canSave=(!d.integration||outcome==="needs_review"||mubitReview)&&outcome&&reviewer.trim()&&(!needsReason||reason.trim())&&(outcome==="needs_review"||(response.trim()&&draftOutcome===outcome))&&!busy&&!saving&&!drafting;
  const references=Object.fromEntries((policy?.references||[]).map(r=>[r.id,r]));
  const issues=[...(checks?.validation||[]).filter(i=>i.severity!=="info").map(i=>i.message),...(review?.parsed?.missing_information||[])];
  const isSensitive=review?.safety_flags?.includes("human_judgement_required");
  const flagMessages=(review?.safety_flags||[]).filter(f=>f!=="human_judgement_required").map(f=>
    f.startsWith("provider_failure")?"The AI service did not complete. You can review the case manually.":
    f.includes("reference")||f.includes("unknown_evidence")||f.startsWith("draft_")?"The AI cited information we could not verify. Check the evidence before deciding.":
    f.startsWith("conflicts")?"The AI response conflicted with the evidence checks.":
    f.startsWith("missing_information")?"Some information needed for this decision is missing.":
    f.includes("validation")?"The case contains inconsistent information.":
    f.includes("schema")||f.includes("json")||f.includes("empty")||f.includes("truncated")?"The AI response could not be read. Review the case manually or try again.":null).filter(Boolean);

  async function runReview(){
    setBusy(true);setOutcome("");setResponse("");setReason("");
    try{const next=await api.review(caseId);setD(next);await onChanged();}catch(e){onError(e.message);}finally{setBusy(false);}
  }
  async function save(next){
    if(!canSave)return;setSaving(true);
    try{const result=await api.resolve(caseId,{outcome,review_id:review?.id??null,reason,response,reviewer});setD(result);setOutcome("");await onSaved(caseId,next);}catch(e){onError(e.message);}finally{setSaving(false);}
  }
  async function upload(eid,file){
    if(!file)return;setUploading(eid);
    try{setD(await api.uploadEvidence(caseId,eid,file));setOutcome("");await onChanged();}catch(e){onError(e.message);}finally{setUploading(null);}
  }
  return <div className="case-columns">
    <article className="case-paper">
      <header className="paper-header"><div className="row-between"><span className="eyebrow">APPEAL FILE <span className="mono">/{String(d.id).padStart(3,"0")}</span></span><span className="paper-stamp">{decided?"DECISION RECORDED":"FOR YOUR REVIEW"}</span></div><h2>{c.pcn_ref}</h2><div className="case-location"><Icon name="pin" size={15}/>{c.location}</div><div className="case-facts-strip"><span>Vehicle<b className="mono">{c.vrm}</b></span><span>Contravention<b>{c.contravention_code}</b></span><span>Received<b>{new Date(c.representation_received_date+"T12:00:00").toLocaleDateString("en-GB",{day:"numeric",month:"short"})}</b></span></div></header>
      {d.integration&&<p className="alert case-connection"><strong>Source: {d.integration.source_system}</strong> · {d.integration.council_id} · {d.integration.source_case_id} · version {d.integration.source_version}<br/>{({awaiting_decision:"Awaiting officer decision",awaiting_receipt:"Approved result awaiting council receipt",received:"Council connector confirmed receipt"})[d.integration.delivery_status]} · Sandbox exchange</p>}
      <section className="appeal-section"><div className="section-label"><span className="number-label">01</span><h3>The driver’s appeal</h3></div><blockquote>{c.representation_text}</blockquote><div className="claim-tags">{c.claimed_grounds.map(g=><span key={g}>{titleCase(g)}</span>)}</div></section>
      <div className="document-tabs" role="tablist" aria-label="Case information">{[["evidence",`Evidence ${c.evidence.length}`],["checks","Checks & policy"],["history","History"]].map(([id,label])=><button role="tab" aria-selected={tab===id} key={id} onClick={()=>setTab(id)} className={tab===id?"active":""}>{label}</button>)}</div>
      <div className="document-body" role="tabpanel">
      {tab==="evidence"&&<><div className="section-label"><span className="number-label">02</span><h3>What we have</h3></div><p className="small muted">Supplied records and evidence descriptions.</p><div className="evidence-list">{c.evidence.map(e=>{const file=d.evidence_files.find(f=>f.evidence_id===e.id);return <div className="evidence-item" key={e.id}><span className="evidence-icon"><Icon name="file" size={21}/></span><div className="evidence-copy"><strong>{titleCase(e.type)}</strong><p>{e.description||"No description supplied."}</p><span className="mono">{e.id} · {e.source==="council"?"COUNCIL RECORD":"DRIVER SUPPLIED"}</span>{file?<a className="file-link" href={`/api/cases/${caseId}/evidence/${encodeURIComponent(e.id)}/file`}><Icon name="download" size={13}/>{file.filename}</a>:<small className="muted">Description only · no file attached</small>}</div>{!decided&&<label className="attach-button" title="Attach evidence file"><Icon name="plus" size={15}/><span className="sr-only">Attach file to {e.id}</span><input type="file" disabled={busy||!!uploading} accept="image/jpeg,image/png,image/webp,application/pdf,text/plain" onChange={ev=>{upload(e.id,ev.target.files[0]);ev.target.value="";}}/></label>}</div>;})}{!c.evidence.length&&<div className="alert warning">No evidence has been attached.</div>}</div>
      <div className="records-section"><h4>Council records</h4>{[["payments","Payment"],["permits","Permit"],["badges","Badge"]].map(([key,label])=><details key={key} className="record-detail"><summary><span>{label} records</span><span className="mono muted">{c.records[key]==null?"NOT SUPPLIED":`${c.records[key].length} FOUND`}</span></summary>{c.records[key]==null?<p>These records have not been supplied. This does not mean no valid record exists.</p>:!c.records[key].length?<p>No matching records were supplied.</p>:c.records[key].map((r,i)=><dl key={i} className="mini-facts">{Object.entries(r).filter(([,v])=>v!==null).map(([k,v])=><div key={k}><dt>{titleCase(k)}</dt><dd>{typeof v==="boolean"?(v?"Yes":"No"):String(v)}</dd></div>)}</dl>)}</details>)}</div></>}
      {tab==="checks"&&<><div className="section-label"><span className="number-label">02</span><h3>Checked against the facts</h3></div>{checks?.rules.map(r=><div className="check-item" key={r.rule_id}><span className={`check-mark ${r.effect}`}><Icon name={r.status==="insufficient_data"||r.effect==="needs_review"?"flag":"check"} size={15}/></span><div><p>{r.finding}</p>{r.policy_refs.map(id=><details className="policy-ref" key={id}><summary>{references[id]?.title||id}<span className="mono">{id}</span></summary><p>{references[id]?.text}</p></details>)}</div></div>)}<p className="small muted policy-note">{policy?.notice||"Demonstration policy. Council policy approval is required before live use."}</p><details className="record-detail"><summary>Full case details</summary><dl className="mini-facts">{[["Contravention",d.contravention_description],["Issued",fmt(c.contravention_datetime)],["Zone",c.zone],["Notice date",c.notice_date],["Stage",c.stage],["Response due",c.response_due_date||"Not set"],["Observation",`${c.observation_minutes??"Not recorded"} minutes`]].map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl></details></>}
      {tab==="history"&&<><div className="section-label"><span className="number-label">02</span><h3>The case so far</h3></div><ol className="case-timeline">{[...d.audit].reverse().map(e=><li key={e.id}><span className="timeline-dot"/><strong>{titleCase(e.event_type)}</strong><time>{fmt(e.created_at)}</time><p>{e.actor}</p>{e.detail.reason&&<p>{e.detail.reason}</p>}</li>)}</ol></>}
      </div>
    </article>
    <aside className="review-panel" aria-label="Review and decision">
      <div className="review-panel-header"><span className="eyebrow">YOUR COPILOT</span><Icon name="spark" size={22}/></div>
      {decided?<div className="completed-panel"><span className="completion-check"><Icon name="check" size={28}/></span><span className="eyebrow">SAVED TO CASE HISTORY</span><h2>{outcomes[final?.final_outcome]}</h2><p>Recorded by {final?.reviewer}. The response is ready to download.</p>{final?.reason&&<p className="saved-reason">{final.reason}</p>}<a className="btn primary" href={`/api/cases/${caseId}/response`}><Icon name="download"/>Download response</a><details className="record-detail"><summary>View saved response</summary><p className="saved-letter">{final?.final_response}</p></details><div className="small muted">{d.integration?(d.integration.delivery_status==="received"?"The council connector confirmed receipt. Civic does not send letters to motorists.":"The result is available to the council connector and is awaiting its receipt."):"No letter has been sent and no external PCN record has been changed."}</div></div>:<>
        {!review&&!busy&&<div className="review-start"><div className="orbit-icon"><Icon name="spark" size={34}/></div><h2>A second pair<br/>of eyes.</h2><p>Check the evidence, find the relevant policy and prepare a response.</p><button className="btn primary large full" disabled={!aiAvailable} onClick={runReview}><Icon name="spark" size={17}/>Review case<Icon name="arrow" size={17}/></button><span className="small muted">{!aiAvailable?"Mubit setup is needed before reviewing this case.":health?.ai_provider==="mubit"?"Reviewed through Mubit.":"Local development uses simulated AI."} You make the decision.</span></div>}
        {busy&&<div className="review-running" role="status" aria-live="polite"><span className="spinner"/><h3>Putting the facts together…</h3><p>Checking the supplied evidence, council policy and approved similar cases.</p><span className="mono small muted">REVIEW IN PROGRESS</span></div>}
        {review&&!busy&&<div className={`recommendation ${review.effective_recommendation}`}><div className="row-between"><span className="eyebrow">SUGGESTED OUTCOME</span><button className="text-btn small" disabled={!aiAvailable} onClick={runReview}>Review again</button></div><h2>{labels[review.effective_recommendation]}</h2><p>{review.parsed?.reason_summary||"The AI review did not complete. Check the evidence and decide manually, or try again."}</p>{review.parsed?.relevant_rule_references.length>0&&<div className="supporting-refs">{review.parsed.relevant_rule_references.map(id=><button key={id} onClick={()=>setTab("checks")} title={references[id]?.text}><Icon name="file" size={12}/>{references[id]?.title||id}</button>)}</div>}
        {(review.steps||[]).length>0&&<><button className="trace-toggle" onClick={()=>setTrace(!trace)} aria-expanded={trace}><Icon name="check" size={13}/>{review.steps.filter(s=>s.tool!=="planner").length} investigation steps<span>{trace?"−":"+"}</span></button>{trace&&<ol className="agent-trace">{review.steps.filter(s=>s.tool!=="planner").map((s,i)=><li key={i}><strong>{s.label}</strong><p>{s.summary}</p></li>)}</ol>}</>}
        </div>}
        {(issues.length>0||isSensitive||flagMessages.length>0)&&<div className="attention-box"><div><Icon name="flag" size={16}/><strong>Needs your attention</strong></div><ul>{isSensitive&&<li>Vulnerability or mitigation was raised. Consider the circumstances carefully.</li>}{[...new Set([...issues,...flagMessages])].map((x,i)=><li key={i}>{x}</li>)}</ul></div>}
        {!busy&&<section className="officer-decision"><div className="decision-label"><span className="eyebrow">YOUR DECISION</span><span className="small muted">{reviewer||"Set your name in profile"}</span></div><fieldset className="outcome-options"><legend className="sr-only">Choose the appeal outcome</legend>{["accept","reject","needs_review"].map(o=><label className={`outcome-option ${outcome===o?"chosen":""}`} key={o}><input type="radio" name={`outcome-${caseId}`} checked={outcome===o} onChange={()=>setOutcome(o)}/><span>{labels[o]}<small>{({accept:"Recommend cancellation of the fine",reject:"Recommend that the fine stands",needs_review:"Refer for more evidence or senior review"})[o]}</small></span></label>)}</fieldset>
        {d.integration&&!mubitReview&&<p className="small muted">Run a successful Mubit review before accepting or rejecting this connected case. You can still refer it for investigation.</p>}
        {outcome&&<><label className="field">{needsReason?"Your reason · required":"Decision note · optional"}<textarea rows={2} value={reason} onChange={e=>setReason(e.target.value)} placeholder={needsReason?"Explain what led to your decision…":"Anything the next reviewer should know?"}/></label>{outcome!=="needs_review"&&<><div className="row-between draft-heading"><label htmlFor="response-draft">Response to the driver</label><button className="text-btn small" disabled={drafting} onClick={()=>setDraftVersion(v=>v+1)}>Refresh from reason</button></div>{draftError&&<p role="alert" className="alert error">{draftError}</p>}<textarea id="response-draft" className="response-editor" rows={9} value={response} disabled={drafting} onChange={e=>setResponse(e.target.value)} placeholder={drafting?"Preparing draft…":"Write your response…"}/><span className="small muted">Review the wording before saving. This is a draft for export.</span></>}
        <div className="save-actions"><button className="btn full primary" disabled={!canSave} onClick={()=>save(true)}>{saving?"Saving…":"Save decision & next case"}<Icon name="arrow" size={17}/></button><button className="text-btn small" disabled={!canSave} onClick={()=>save(false)}>Save and stay on this case</button></div></>}
        {!outcome&&<p className="small muted decision-help">Choose an outcome to prepare your response.</p>}
        </section>}
      </>}
      <div className="review-footer"><Icon name="shield" size={14}/><span>Human judgement. A complete record.</span></div>
    </aside>
  </div>;
}
