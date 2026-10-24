import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { Icon } from "./Icons.jsx";
const day = () => new Date().toISOString().slice(0,10);
const grounds = {paid:"I paid for parking",permit:"I had a permit",blue_badge:"I had a Blue Badge",loading:"I was loading",signage:"The signs were unclear",medical_emergency:"Medical circumstances",breakdown:"Vehicle breakdown",other:"Another reason"};
export default function CaseIntake({onClose,onCreated}) {
  const dialog=useRef(null);
  const [form,setForm]=useState({pcn_ref:`DM${Date.now().toString().slice(-8)}`,vrm:"SYN1234",contravention_code:"11",contravention_datetime:`${day()}T10:00`,location:"",zone:"Z1",notice_date:day(),representation_received_date:day(),response_due_date:"",stage:"informal",representation_text:"",ground:"paid",observation_minutes:""});
  const [evidence,setEvidence]=useState([{id:"E1",type:"ceo_photo",source:"council",description:"",file:null}]);
  const [recordMode,setRecordMode]=useState("unknown");
  const [payment,setPayment]=useState({reference:"PAY-001",start:`${day()}T09:00`,end:`${day()}T11:00`});
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  const [createdId,setCreatedId]=useState(null);
  useEffect(()=>{dialog.current?.showModal();},[]);
  const set=k=>e=>setForm(f=>({...f,[k]:e.target.value}));
  async function submit(e){
    e.preventDefault();setBusy(true);setError("");
    try{
      let id=createdId;
      if(!id){
        const body={...form,contravention_datetime:new Date(form.contravention_datetime).toISOString(),claimed_grounds:[form.ground],response_due_date:form.response_due_date||null,observation_minutes:form.observation_minutes===""?null:Number(form.observation_minutes),synthetic:true,
          records:recordMode==="unknown"?{}:{payments:recordMode==="none"?[]:[{...payment,vrm:form.vrm,zone:form.zone,start:new Date(payment.start).toISOString(),end:new Date(payment.end).toISOString()}]},
          evidence:evidence.map(({file,...item})=>({...item,filename:file?.name||null}))};
        delete body.ground;
        const c=await api.createCase(body);id=c.id;setCreatedId(id);
      }
      for(const item of evidence){if(item.file)await api.uploadEvidence(id,item.id,item.file);}
      await onCreated(id);
    }catch(err){setError(err.message);}finally{setBusy(false);}
  }
  return <dialog className="intake-dialog" ref={dialog} onCancel={e=>{if(busy)e.preventDefault();else onClose();}}><form onSubmit={submit}>
    <div className="modal-heading"><div><span className="eyebrow">START A CASE</span><h2>A new appeal.</h2></div><button type="button" className="icon-btn" aria-label="Close new appeal" disabled={busy} onClick={onClose}><Icon name="close"/></button></div>
    <p className="muted">Use fictional information in this demonstration workspace.</p>
    {error&&<div className="alert error" role="alert">{error}{createdId&&<p>The case was saved. Retry to finish attaching the files.</p>}</div>}
    <fieldset disabled={busy||!!createdId} className="intake-fields"><legend className="sr-only">Case details</legend>
    <div className="form-grid"><label>PCN reference<input required value={form.pcn_ref} onChange={set("pcn_ref")}/></label><label>Vehicle registration<input required value={form.vrm} onChange={set("vrm")}/></label><label>Location<input autoFocus required placeholder="Street or car park" value={form.location} onChange={set("location")}/></label><label>Parking zone<input value={form.zone} onChange={set("zone")}/></label><label>Reason for the fine<select value={form.contravention_code} onChange={set("contravention_code")}>{[["01","Restricted street"],["05","Paid time expired"],["11","No payment"],["12","No valid permit"],["40","Disabled bay"]].map(([v,l])=><option key={v} value={v}>{v} · {l}</option>)}</select></label><label>Time of alleged contravention<input required type="datetime-local" value={form.contravention_datetime} onChange={set("contravention_datetime")}/></label></div>
    <div className="form-grid"><label>Notice date<input type="date" required value={form.notice_date} onChange={set("notice_date")}/></label><label>Appeal received<input type="date" required value={form.representation_received_date} onChange={set("representation_received_date")}/></label><label>Stage<select value={form.stage} onChange={set("stage")}><option value="informal">Informal challenge</option><option value="formal">Formal representation</option></select></label><label>Response due · optional<input type="date" min={form.representation_received_date} value={form.response_due_date} onChange={set("response_due_date")}/></label></div>
    <label className="field">Reason for the appeal<select value={form.ground} onChange={set("ground")}>{Object.entries(grounds).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label><label className="field">The driver’s words<textarea required rows={4} placeholder="Paste the appeal here…" value={form.representation_text} onChange={set("representation_text")}/></label>
    <div className="intake-section"><div className="row-between"><h3>Evidence</h3><button type="button" className="text-btn" onClick={()=>setEvidence(es=>[...es,{id:`E${Date.now().toString().slice(-10)}`,type:"correspondence",source:"motorist",description:"",file:null}])}><Icon name="plus" size={14}/>Add item</button></div>{evidence.map((item,i)=><div className="intake-evidence" key={item.id}><div className="form-grid"><label>Evidence type<select value={item.type} onChange={e=>setEvidence(es=>es.map((x,j)=>j===i?{...x,type:e.target.value}:x))}>{["ceo_photo","payment_receipt","permit_record","badge_record","delivery_note","signage_photo","medical_letter","breakdown_report","correspondence","other"].map(t=><option key={t} value={t}>{t.replaceAll("_"," ")}</option>)}</select></label><label>Source<select value={item.source} onChange={e=>setEvidence(es=>es.map((x,j)=>j===i?{...x,source:e.target.value}:x))}><option value="council">Council</option><option value="motorist">Driver</option></select></label></div><label>Description<input required placeholder="What does this evidence show?" value={item.description} onChange={e=>setEvidence(es=>es.map((x,j)=>j===i?{...x,description:e.target.value}:x))}/></label><div className="row-between"><label className="small">Attach file · optional<input type="file" accept="image/jpeg,image/png,image/webp,application/pdf,text/plain" onChange={e=>setEvidence(es=>es.map((x,j)=>j===i?{...x,file:e.target.files[0]}:x))}/></label><button type="button" className="icon-btn" aria-label={`Remove evidence ${i+1}`} onClick={()=>setEvidence(es=>es.filter((_,j)=>j!==i))}><Icon name="close" size={16}/></button></div></div>)}</div>
    <details className="record-detail"><summary>Council records & observation</summary><label className="field">Payment search result<select value={recordMode} onChange={e=>setRecordMode(e.target.value)}><option value="unknown">Records not supplied</option><option value="none">Checked — no payment found</option><option value="found">Payment found</option></select></label>{recordMode==="found"&&<div className="form-grid"><label>Payment reference<input required value={payment.reference} onChange={e=>setPayment({...payment,reference:e.target.value})}/></label><label>Paid from<input required type="datetime-local" value={payment.start} onChange={e=>setPayment({...payment,start:e.target.value})}/></label><label>Paid until<input required type="datetime-local" value={payment.end} onChange={e=>setPayment({...payment,end:e.target.value})}/></label></div>}<label>Observation time · minutes<input min="0" type="number" value={form.observation_minutes} onChange={set("observation_minutes")}/></label><p className="small muted">Permit and badge records can also be supplied through the Admin case import.</p></details>
    </fieldset><div className="modal-footer"><span className="small muted">Evidence checks run when you save.</span><button className="btn primary" disabled={busy}>{busy?"Saving…":createdId?"Finish attaching files":"Add to queue"}<Icon name="arrow" size={16}/></button></div>
  </form></dialog>;
}
