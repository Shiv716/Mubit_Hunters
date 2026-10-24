import {useCallback,useEffect,useState} from "react";
import {api} from "./api.js";

export default function AccessRequests(){
  const [data,setData]=useState(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState("");
  const [notice,setNotice]=useState("");
  const refresh=useCallback(()=>api.accessRequests().then(setData),[]);
  useEffect(()=>{refresh().catch(err=>setError(err.message));},[refresh]);
  async function decide(id,action){
    setBusy(id);setError("");setNotice("");
    try{
      const result=await api.accessDecision(id,{action});
      setNotice(action==="revoke"?"Access revoked. Existing workspace sessions are blocked.":result.email_sent?"Access approved and notification sent.":"Access is approved, but the email was not sent. Check email settings and retry the notification.");
      await refresh();
    }catch(err){setError(err.message);}finally{setBusy("");}
  }
  return <section className="access-requests" aria-labelledby="requests-heading">
    <div className="row-between"><h2 id="requests-heading">Access requests</h2><button className="btn" onClick={()=>refresh().catch(err=>setError(err.message))}>Refresh</button></div>
    <p className="muted">You decide who can join. Approved members can review appeals and record decisions.</p>
    {data&&!data.notifications_configured&&<p className="alert">Email notifications are not configured. Requests are saved here; approved people can sign in with their email.</p>}
    {error&&<p role="alert" className="alert error">{error}</p>}
    {notice&&<p role="status" className="alert">{notice}</p>}
    {!data?<p>Loading requests…</p>:!data.requests.length?<p>No access requests yet.</p>:<div className="access-request-list">{data.requests.map(row=><article key={row.id} className="access-request-row">
      <div><strong className="access-email">{row.email}</strong><p className="small muted">{new Date(row.requested_at*1000).toLocaleString()} · {row.status}{row.status==="pending"&&!row.owner_email_sent?" · owner notification not delivered":""}</p></div>
      <div className="access-request-actions">{row.status!=="approved"?<button className="btn primary" disabled={Boolean(busy)} onClick={()=>decide(row.id,"approve")}>{busy===row.id?"Saving…":"Approve access"}</button>:<>
        {!row.applicant_email_sent&&<button className="btn" disabled={Boolean(busy)} onClick={()=>decide(row.id,"notify")}>Retry notification</button>}
        <button className="btn" disabled={Boolean(busy)} onClick={()=>decide(row.id,"revoke")}>Revoke access</button>
      </>}</div>
    </article>)}</div>}
  </section>;
}
