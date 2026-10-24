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
      setNotice(action==="revoke"?"Access revoked. Existing workspace sessions are blocked.":result.message||"Access approved. They can request a sign-in code from Civic.");
      await refresh();
    }catch(err){setError(err.message);}finally{setBusy("");}
  }
  return <section className="access-requests" aria-labelledby="requests-heading">
    <div className="row-between"><h2 id="requests-heading">Access requests</h2><button className="btn" onClick={()=>refresh().catch(err=>setError(err.message))}>Refresh</button></div>
    <p className="muted">You decide who can join. Approved members can review appeals and record decisions.</p>
    {data&&!data.email_signin_configured&&<p className="alert">Email sign-in is not configured. Add NEON_AUTH_BASE_URL to Render and redeploy so approved members can enter.</p>}
    {data&&!data.notifications_configured&&<p className="alert">Owner email notifications are not configured. You can review saved requests here.</p>}
    {error&&<p role="alert" className="alert error">{error}</p>}
    {notice&&<p role="status" className="alert">{notice}</p>}
    {!data?<p>Loading requests…</p>:!data.requests.length?<p>No access requests yet.</p>:<div className="access-request-list">{data.requests.map(row=><article key={row.id} className="access-request-row">
      <div><strong className="access-email">{row.email}</strong><p className="small muted">{new Date(row.requested_at*1000).toLocaleString()} · {row.status}{row.status==="pending"&&!row.owner_email_sent?" · owner notification not sent":""}</p></div>
      <div className="access-request-actions">{row.status!=="approved"?<button className="btn primary" disabled={Boolean(busy)} onClick={()=>decide(row.id,"approve")}>{busy===row.id?"Saving…":"Approve access"}</button>:<>
        {!row.applicant_email_sent&&<button className="btn" disabled={Boolean(busy)} onClick={()=>decide(row.id,"notify")}>Retry sign-in email</button>}
        <button className="btn" disabled={Boolean(busy)} onClick={()=>decide(row.id,"revoke")}>Revoke access</button>
      </>}</div>
    </article>)}</div>}
  </section>;
}
