import {useEffect, useRef, useState} from "react";
import {Icon} from "./Icons.jsx";
import {driverApi} from "./driverApi.js";
import "./demo.css";

const steps = ["Scan the ticket", "Check the details", "Build the case", "Review the draft"];
const verdicts = {grounds_to_explore:"Possible grounds to explore",more_evidence:"More evidence would help",limited_grounds:"The grounds look limited",specialist_help:"This needs specialist help"};
const fields = [["issuer","Operator"],["ticket_ref","Ticket reference"],["vehicle_registration","Vehicle"],["location","Location"],["incident_date","Parking date"],["issue_date","Notice date"],["amount_pounds","Charge (£)"],["deadline","Printed challenge deadline"],["discount_deadline","Printed discount deadline"],["date_received","Date received"]];

export default function DemoTicket({onStartReal}) {
  const [sample,setSample] = useState(null), [loadError,setLoadError] = useState("");
  const [step,setStep] = useState(0), [scan,setScan] = useState(null), [assessment,setAssessment] = useState(null);
  const [mode,setMode] = useState("live"), [confirmed,setConfirmed] = useState(false), [busy,setBusy] = useState("");
  const [error,setError] = useState(""), [draft,setDraft] = useState(""), [approved,setApproved] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    let active = true;
    driverApi.demo().then(data=>{if(active)setSample(data);}).catch(e=>{if(active)setLoadError(e.message);});
    return ()=>{active=false;generation.current++;};
  }, []);
  useEffect(()=>{window.scrollTo({top:0});},[step]);
  function reset() {
    generation.current++; setStep(0);setScan(null);setAssessment(null);setMode("live");
    setConfirmed(false);setBusy("");setError("");setDraft("");setApproved(false);
  }
  async function process(action) {
    if(busy)return;
    const current=generation.current;
    setBusy(action);setError("");setMode("live");
    try {
      const result=action === "scan" ? await driverApi.demoScan() : await driverApi.demoAssess(scan.run_id);
      if(current!==generation.current)return;
      if(action === "scan"){setScan(result);setConfirmed(false);setStep(1);}
      else {setAssessment(result);setDraft(result.assessment.draft_letter);setApproved(false);setStep(3);}
    } catch(e) {if(current===generation.current)setError(e.message);}
    finally {if(current===generation.current)setBusy("");}
  }
  function walkthrough() {
    generation.current++;setBusy("");setError("");setMode("walkthrough");setApproved(false);
    setScan({mode:"walkthrough",provider:"prewritten-example",extracted:sample.extracted});
    if(step>=2) {
      const result={mode:"walkthrough",provider:"prewritten-example",assessment:sample.assessment};
      setAssessment(result);setDraft(result.assessment.draft_letter);setStep(3);
    } else {setConfirmed(false);setStep(1);}
  }
  function assess() {
    if(!confirmed)return;
    if(mode === "walkthrough")walkthrough(); else process("assess");
  }
  function download() {
    if(!approved)return;
    const text=`CIVIC DEMO — FICTIONAL SAMPLE — NOT SUBMITTED\n${assessment.mode === "live" ? "Based on a Mubit draft; may include local edits" : "Based on a prewritten walkthrough; may include local edits"}\n\n${draft}`;
    const url=URL.createObjectURL(new Blob([text],{type:"text/plain;charset=utf-8"}));
    const link=document.createElement("a");link.href=url;link.download="civic-demo-appeal.txt";link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  if(!sample)return <main id="driver-main" className="driver-main"><div className="driver-empty" role={loadError?"alert":"status"}>{loadError||"Opening the sample ticket…"}{loadError&&<button className="btn" onClick={()=>window.location.reload()}>Try again</button>}</div></main>;
  const output=assessment?.assessment;
  return <main id="driver-main" className="driver-main demo-page">
    <div className="driver-page-heading"><div><div className="eyebrow">TRY CIVIC / NO ACCOUNT NEEDED</div><h1>One ticket. See the whole journey<span className="blue">.</span></h1><p>Scan our fictional notice, check the evidence and see an appeal take shape.</p></div><button className="btn" onClick={reset} disabled={!!busy}><Icon name="refresh" size={15}/>Start again</button></div>
    <div className="demo-banner"><span className="demo-badge">FICTIONAL SAMPLE</span><p>Fixed example dates. No real charge, submission or case record. Reload this page to start from the beginning.</p><span className={`demo-mode ${mode === "walkthrough" ? "example" : ""}`}>{mode === "walkthrough" ? "Sample walkthrough · prewritten results" : sample.live_available ? "Live Mubit selected" : "Live Mubit unavailable here"}</span></div>
    <nav className="driver-steps" aria-label="Demo steps">{steps.map((name,index)=><button key={name} className={step===index?"active":""} aria-current={step===index?"step":undefined} disabled={!!busy || index>step} onClick={()=>{setStep(index);setError("");}}><span>{String(index+1).padStart(2,"0")}</span>{name}</button>)}</nav>
    {busy&&<div className="driver-working" role="status"><span className="spinner"/>{busy === "scan" ? "Mubit is reading the sample ticket image…" : "Mubit is comparing the confirmed details and receipt…"}<small>This is a real model request using fictional documents.</small></div>}
    {error&&<div className="demo-error" role="alert"><strong>Live processing couldn’t finish.</strong><p>{error}</p><div className="driver-actions"><button className="btn" disabled={!!busy} onClick={()=>process(step===0?"scan":"assess")}>Try live Mubit again</button><button className="btn primary" disabled={!!busy} onClick={walkthrough}>Continue with sample walkthrough</button></div></div>}
    <div className="demo-layout"><aside className="demo-document"><div className="row-between"><span className="eyebrow">{step===2?"SUPPORTING RECEIPT":"SAMPLE TICKET / DEMO-001"}</span><a className="text-btn" href={step===2?sample.receipt_url:sample.ticket_url} target="_blank" rel="noreferrer">Open full size<Icon name="external" size={13}/></a></div><img src={step===2?sample.receipt_url:sample.ticket_url} alt={step===2?"Fictional payment receipt: DEMO123, Willow Yard, £6, 20 October 2026, 10:00 to 13:00":"Fictional parking charge DEMO-001, vehicle DEMO123, Willow Yard, £100, observed 20 October 2026 at 11:15"}/><p>Both documents are made for this demo. They contain no personal data.</p></aside>
      <section className="demo-panel">
        {step===0&&<><span className="eyebrow">01 / START WITH A PHOTO</span><h2>“I paid. Why did I get a ticket?”</h2><p className="demo-intro">{sample.description}</p><div className="demo-checklist"><p><Icon name="file" size={18}/>One sample notice, already attached</p><p><Icon name="shield" size={18}/>One matching payment receipt</p><p><Icon name="spark" size={18}/>The same Mubit reader and adviser used for real cases</p></div><p className="driver-note">Live processing sends only these fictional documents to Mubit. The scan fills the details; you check them before the assessment.</p>{!sample.live_available&&<p className="demo-unavailable">Mubit is not connected on this server. The sample walkthrough is available now.</p>}<div className="demo-start-actions"><button className="btn primary large" disabled={!!busy||!sample.live_available} onClick={()=>process("scan")}><Icon name="spark" size={17}/>Scan sample with Mubit</button><button className="text-btn" disabled={!!busy} onClick={walkthrough}>Use sample walkthrough<Icon name="arrow" size={15}/></button></div><small className="demo-small">The walkthrough uses prewritten example results and makes no AI calls. It is always labelled.</small></>}
        {step===1&&<><span className="eyebrow">02 / YOU CHECK THE FACTS</span><h2>The notice becomes details.</h2><ResultSource result={scan}/><p className="demo-intro">Compare these fields with the sample notice. In your own case, you can correct any reading errors before continuing.</p><dl className="demo-facts">{fields.map(([key,label])=><div key={key}><dt>{label}</dt><dd>{scan.extracted[key]||"Not shown on notice"}</dd></div>)}</dl>{scan.extracted.uncertainties?.length>0&&<div className="driver-note"><strong>Things to check</strong><ul>{scan.extracted.uncertainties.map((item,i)=><li key={i}>{item}</li>)}</ul></div>}<label className="driver-check"><input type="checkbox" checked={confirmed} disabled={!!busy} onChange={e=>setConfirmed(e.target.checked)}/><span>I’ve compared the extracted details with the fictional notice.</span></label><div className="driver-actions"><button className="btn primary" disabled={!confirmed||!!busy} onClick={()=>setStep(2)}>Continue to evidence<Icon name="arrow" size={16}/></button></div></>}
        {step===2&&<><span className="eyebrow">03 / JOIN UP THE EVIDENCE</span><h2>What does the receipt tell us?</h2><p className="demo-intro">The supplied receipt records a £6 payment for DEMO123 at Willow Yard from 10:00 to 13:00. The notice time is 11:15.</p><label className="driver-narrative">The sample driver’s account<textarea value={sample.facts.narrative} readOnly rows={6}/></label><div className="demo-evidence-row"><Icon name="file" size={24}/><div><strong>DEMO-PAY-001</strong><small>Matching receipt attached to the assessment</small></div><a className="text-btn" href={sample.receipt_url} target="_blank" rel="noreferrer">View<Icon name="external" size={13}/></a></div><p className="driver-note">In a live run, Mubit receives the confirmed scan, both images and our dated guidance sources. It checks possible grounds, missing evidence and risks before drafting.</p><div className="driver-actions"><button className="btn primary" disabled={!!busy||!confirmed} onClick={assess}><Icon name="spark" size={17}/>{mode === "walkthrough" ? "Show sample assessment" : "Assess sample with Mubit"}</button></div></>}
        {step===3&&output&&<><span className="eyebrow">04 / REVIEW BEFORE SENDING</span><h2>A reasoned next step.</h2><ResultSource result={assessment}/><div className={`driver-verdict ${output.verdict}`}><h3>{verdicts[output.verdict]||"Review the assessment"}</h3><p>{output.summary}</p></div>{output.grounds.map((ground,i)=><article className="driver-ground" key={i}><h4>{ground.title}</h4><p>{ground.explanation}</p></article>)}<DemoList title="What’s still missing" items={output.missing_evidence}/><DemoList title="Risks to consider" items={output.risks}/><DemoList title="Next steps" items={output.next_steps}/><details className="driver-sources"><summary>Guidance supplied to the assessment</summary>{output.sources.map(source=><a key={source.id} href={source.url} target="_blank" rel="noreferrer">{source.title}<Icon name="external" size={12}/></a>)}</details>{output.draft_letter?<><label className="driver-narrative demo-draft">Edit the sample appeal<textarea rows={12} value={draft} onChange={e=>{setDraft(e.target.value);setApproved(false);}}/></label><label className="driver-check"><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)}/><span>I’ve reviewed this fictional example draft.</span></label><div className="driver-actions"><button className="btn" disabled={!approved||!draft.trim()} onClick={download}><Icon name="file" size={16}/>Download sample draft</button></div></>:<p className="driver-note">This assessment did not produce a draft. Follow its next steps or start the demo again.</p>}<div className="demo-finish"><Icon name="check" size={22}/><div><strong>That’s the preparation journey.</strong><p>With a real ticket, you submit through the issuer’s route, save the confirmation and track its response. This demo has not sent anything or recorded a win.</p></div></div><div className="driver-actions"><button className="btn" onClick={reset}>Start again</button><button className="btn primary" onClick={onStartReal}>Try your own ticket<Icon name="arrow" size={16}/></button></div></>}
      </section>
    </div>
  </main>;
}

function ResultSource({result}) {return <div className={`demo-result-source ${result.mode === "live" ? "live" : ""}`}><Icon name={result.mode === "live"?"spark":"file"} size={15}/><div><strong>{result.mode === "live"?"Generated by live Mubit":"Prewritten sample result · no AI call"}</strong>{result.mode === "live"&&<small>{result.model} · {new Date(result.processed_at).toLocaleTimeString("en-GB")}{result.request_id&&<span>Request: {result.request_id}</span>}</small>}</div></div>;}
function DemoList({title,items}) {return items.length>0&&<section className="driver-advice-section"><h3>{title}</h3><ul>{items.map((item,i)=><li key={i}>{item}</li>)}</ul></section>;}
