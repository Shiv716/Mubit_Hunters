import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { Icon, Mark } from "./Icons.jsx";

export default function Login({onLogin, session}) {
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [requestAccess, setRequestAccess] = useState(false);
  const [usePassword, setUsePassword] = useState(!session.email_signin);
  const [seconds, setSeconds] = useState(0);
  useEffect(()=>{if(seconds){const timer=setTimeout(()=>setSeconds(s=>s-1),1000);return()=>clearTimeout(timer);}},[seconds]);

  async function signIn(event) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if(usePassword) await api.login({name,password});
      else if(!confirmation) {
        const result=await api.requestEmailCode({email:email.trim()});
        setConfirmation(result.message); setSeconds(60); return;
      } else await api.verifyEmailCode({email:email.trim(),name,code});
      onLogin(await api.session());
    } catch(err) {setError(err.message);} finally {setBusy(false);}
  }
  async function resend() {
    setBusy(true); setError("");
    try {await api.requestEmailCode({email:email.trim()});setSeconds(60);} catch(err){setError(err.message);} finally{setBusy(false);}
  }
  return <main className="login-screen">
    <form className="login-card" onSubmit={signIn}>
      <Mark/><div className="eyebrow">CIVIC / REVIEW WORKSPACE</div>
      <h1>Back to the desk.</h1><p>{session.email_signin ? "Sign in with your approved email address." : "Sign in to review your council’s synthetic appeals."}</p>
      {error&&<p role="alert" className="alert error">{error}</p>}
      {usePassword ? <>
        <label>Reviewer name<input required autoComplete="name" maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label>
        <label>Workspace password<input required type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)}/></label>
      </> : <>
        <label>Email address<input required type="email" autoComplete="email" maxLength={254} readOnly={Boolean(confirmation)} value={email} onChange={e=>setEmail(e.target.value)}/></label>
        {confirmation&&<>
          <p role="status" className="small muted">{confirmation}</p>
          <label>Reviewer name<input required autoComplete="name" maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label>
          <label>Sign-in code<input autoFocus className="signin-code" required inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6,8}" maxLength={8} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,""))}/></label>
        </>}
      </>}
      <button disabled={busy} className="btn primary large">{busy ? "Please wait…" : usePassword||confirmation ? "Open workspace" : "Email sign-in code"}<Icon name="arrow"/></button>
      {!usePassword&&confirmation&&<div className="email-access-recipient">
        <button className="text-btn" type="button" disabled={busy} onClick={()=>{setConfirmation("");setCode("");setError("");}}>Change email</button>
        <button className="text-btn" type="button" disabled={busy||seconds>0} onClick={resend}>{seconds?`Send again in ${seconds}s`:"Send another code"}</button>
      </div>}
      {session.email_signin&&session.password_signin&&<button type="button" className="text-btn" onClick={()=>{setUsePassword(v=>!v);setError("");}}>{usePassword?"Use email sign-in":"Owner password sign-in"}</button>}
      <div className="email-access-entry"><p>New here? Ask to join the workspace.</p>
        <button type="button" className="btn large" disabled={busy} onClick={()=>setRequestAccess(true)}>Request access<Icon name="arrow" size={16}/></button>
      </div>
    </form>
    {requestAccess&&<RequestAccess onClose={()=>setRequestAccess(false)}/>}
  </main>;
}

function RequestAccess({onClose}) {
  const dialog=useRef(null);
  const emailField=useRef(null);
  const [email,setEmail]=useState("");
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  useEffect(()=>{const node=dialog.current;node.showModal();emailField.current?.focus();return()=>node.close();},[]);
  async function submit(event){
    event.preventDefault();setBusy(true);setError("");
    try{setMessage((await api.requestAccess({email:email.trim()})).message);}catch(err){setError(err.message);}finally{setBusy(false);}
  }
  return <dialog ref={dialog} className="intake-dialog email-access-dialog" aria-labelledby="access-title" onCancel={event=>{if(busy)event.preventDefault();else onClose();}}>
    <div className="modal-heading"><div><span className="eyebrow">JOIN THE WORKSPACE</span><h2 id="access-title">{message?"Request received.":"A seat at the desk."}</h2></div><button type="button" className="icon-btn" disabled={busy} aria-label="Close access request" onClick={onClose}><Icon name="close"/></button></div>
    <p className="email-access-description" role={message?"status":undefined}>{message||"Enter your email. The workspace owner will review your request before you can sign in."}</p>
    {error&&<p role="alert" className="alert error">{error}</p>}
    {message?<button className="btn primary large" onClick={onClose}>Back to sign in<Icon name="arrow"/></button>:<form className="email-access-form" onSubmit={submit}>
      <label>Email address<input ref={emailField} required autoFocus type="email" autoComplete="email" maxLength={254} placeholder="you@example.com" value={email} onChange={e=>setEmail(e.target.value)}/></label>
      <button className="btn primary large" disabled={busy}>{busy?"Requesting…":"Request access"}<Icon name="arrow" size={16}/></button>
    </form>}
  </dialog>;
}

export function ApprovalPage({token,onClose}) {
  const [request,setRequest]=useState(null);
  const [result,setResult]=useState(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  useEffect(()=>{api.inspectApproval({token}).then(setRequest).catch(err=>setError(err.message));},[token]);
  async function approve(){
    setBusy(true);setError("");
    try{setResult(await api.approveAccess({token}));}catch(err){setError(err.message);}finally{setBusy(false);}
  }
  return <main className="login-screen"><div className="login-card">
    <Mark/><div className="eyebrow">WORKSPACE ACCESS</div><h1>{result?"A new seat, ready.":"Welcome them in."}</h1>
    {error&&<p className="alert error" role="alert">{error}</p>}
    {result?<p role="status">{result.email_sent?"Access approved. Their invitation email is on its way.":"Access approved. The notification email could not be sent. They can now sign in with their email; you can retry the notification in Workspace admin."}</p>:request?<>
      <p><strong className="access-email">{request.email}</strong> is asking to join your workspace.</p>
      <p className="small muted">They’ll be able to view appeals and record decisions. Approving does not sign them in.</p>
      <button className="btn primary large" disabled={busy} onClick={approve}>{busy?"Approving…":"Approve access"}<Icon name="check"/></button>
    </>:!error&&<p role="status">Loading request…</p>}
    <button className="text-btn" disabled={busy} onClick={onClose}>Back to workspace</button>
  </div></main>;
}
