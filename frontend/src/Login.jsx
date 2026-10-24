import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { Icon, Mark } from "./Icons.jsx";

export default function Login({onLogin, session, onBrowseParking}) {
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [hasCode, setHasCode] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [requestAccess, setRequestAccess] = useState(false);
  const [usePassword, setUsePassword] = useState(!session.email_signin);
  const [seconds, setSeconds] = useState(0);
  const codeStep=hasCode||Boolean(confirmation);
  useEffect(()=>{if(seconds){const timer=setTimeout(()=>setSeconds(s=>s-1),1000);return()=>clearTimeout(timer);}},[seconds]);

  async function signIn(event) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if(usePassword) await api.login({name,password});
      else if(!codeStep) {
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
      <h1>Back to the desk.</h1><p>{session.email_signin ? "Sign in with your approved email address. Neon emails your sign-in code." : "Sign in to review your council’s synthetic appeals."}</p>
      {error&&<p role="alert" className="alert error">{error}</p>}
      {usePassword ? <>
        <label>Reviewer name<input required autoComplete="name" maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label>
        <label>Workspace password<input required type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)}/></label>
      </> : <>
        <label>Email address<input required type="email" autoComplete="email" maxLength={254} readOnly={Boolean(confirmation)} value={email} onChange={e=>setEmail(e.target.value)}/></label>
        {codeStep&&<>
          <p role="status" className="small muted">{confirmation||"Enter the email you requested access with and the code Neon sent after approval."}</p>
          <label>Reviewer name<input required autoComplete="name" maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label>
          <label>Sign-in code<input autoFocus className="signin-code" required inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6,8}" maxLength={8} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,""))}/></label>
        </>}
      </>}
      <button disabled={busy} className="btn primary large">{busy ? "Please wait…" : usePassword||codeStep ? "Open workspace" : "Email sign-in code"}<Icon name="arrow"/></button>
      {!usePassword&&!codeStep&&<button className="text-btn" type="button" disabled={busy} onClick={()=>{setHasCode(true);setError("");}}>I already have a code</button>}
      {!usePassword&&codeStep&&<div className="email-access-recipient">
        <button className="text-btn" type="button" disabled={busy} onClick={()=>{setConfirmation("");setHasCode(false);setCode("");setError("");}}>Back to email</button>
        <button className="text-btn" type="button" disabled={busy||seconds>0||!email.trim()} onClick={resend}>{seconds?`Send again in ${seconds}s`:"Send another code"}</button>
      </div>}
      {session.email_signin&&session.password_signin&&<button type="button" className="text-btn" onClick={()=>{setUsePassword(v=>!v);setError("");}}>{usePassword?"Use email sign-in":"Owner password sign-in"}</button>}
      <div className="email-access-entry"><p>New here? Ask to join the workspace.</p>
        <button type="button" className="btn large" disabled={busy} onClick={()=>setRequestAccess(true)}>Request access<Icon name="arrow" size={16}/></button>
      </div>
      {onBrowseParking && <button type="button" className="text-btn" onClick={onBrowseParking}><Icon name="map" size={16}/>Explore parking without signing in</button>}
    </form>
    {requestAccess&&<RequestAccess onClose={()=>setRequestAccess(false)} onRequested={address=>{setEmail(address);setConfirmation("");setHasCode(false);setCode("");setError("");if(session.email_signin)setUsePassword(false);}}/>}
  </main>;
}

function RequestAccess({onClose,onRequested}) {
  const dialog=useRef(null);
  const emailField=useRef(null);
  const [email,setEmail]=useState("");
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  useEffect(()=>{const node=dialog.current;node.showModal();emailField.current?.focus();return()=>node.close();},[]);
  async function submit(event){
    event.preventDefault();setBusy(true);setError("");
    try{setMessage((await api.requestAccess({email:email.trim()})).message);onRequested(email.trim());}catch(err){setError(err.message);}finally{setBusy(false);}
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
    <Mark/><div className="eyebrow">WORKSPACE ACCESS</div><h1>{result?"Access approved.":"Welcome them in."}</h1>
    {error&&<p className="alert error" role="alert">{error}</p>}
    {result?<p role="status">{result.message||"Access approved. They can request a sign-in code from Civic."}</p>:request?<>
      <p><strong className="access-email">{request.email}</strong> is asking to join your workspace.</p>
      <p className="small muted">They’ll be able to view appeals and record decisions. Approving does not sign them in.</p>
      <button className="btn primary large" disabled={busy} onClick={approve}>{busy?"Approving…":"Approve access"}<Icon name="check"/></button>
    </>:!error&&<p role="status">Loading request…</p>}
    <button className="text-btn" disabled={busy} onClick={onClose}>Back to workspace</button>
  </div></main>;
}
