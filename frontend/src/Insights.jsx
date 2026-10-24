import {useEffect,useState} from "react";
import {api} from "./api.js";
import {Icon} from "./Icons.jsx";

export default function Insights({revision}) {
  const [data,setData]=useState(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  const [attempt,setAttempt]=useState(0);
  useEffect(()=>{
    let active=true;
    setLoading(true);setError("");
    api.insights({refresh:attempt>0})
      .then(result=>{if(active)setData(result);})
      .catch(err=>{if(active)setError(err.message);})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[revision,attempt]);

  const stats=data?[
    ["Appeals in workspace",data.total,`${data.pending} awaiting a final decision`,"inbox"],
    ["Cases reviewed",data.reviewed,"With a current copilot recommendation","file"],
    ["Decisions recorded",data.decided,"Final outcomes saved by an officer","check"],
    ["Appeals accepted",data.accepted,"Recorded for cancellation","check"],
    ["Referred for investigation",data.investigating,"Waiting for a closer look","flag"],
    ["Officer agreement",data.agreement===null?"—":`${data.agreement}%`,data.compared?`${data.compared} decisive reviews compared`:"Available after a decision on an accept/reject recommendation","chart"],
  ]:[];

  return <div className="insights-page">
    <div className="section-heading row-between insights-heading">
      <div><span className="eyebrow">THE BIGGER PICTURE</span><h1>Every decision tells a story<span className="blue">.</span></h1><p>Case activity and saved outcomes across this workspace.</p></div>
      <button className="btn" disabled={loading} onClick={()=>setAttempt(n=>n+1)}>{loading?"Loading…":error?"Try again":"Refresh"}</button>
    </div>
    {error&&<p className="alert error" role="alert">Couldn’t {data?"refresh":"load"} insights: {error}{data?" Showing the last loaded figures.":" Use Try again to retry."}</p>}
    {loading&&!data&&<div className="empty-state" role="status">Loading insights…</div>}
    {data&&<>
      <div className="stat-grid insights-stats">{stats.map(([label,value,detail,icon])=><section className="stat-card" key={label}>
        <div className="row-between"><span>{label}</span><Icon name={icon}/></div><strong>{value}</strong><small>{detail}</small>
      </section>)}</div>
      {!data.decided&&<p className="alert insights-explanation" role="status">{data.total?<><strong>No final decisions saved yet.</strong> A copilot review saves a recommendation. To populate outcome charts, open a case, choose an outcome and select “Save decision &amp; next case” or “Save and stay on this case”.</>:<>No appeals have been added yet. Add or import cases from the Cases page to start seeing activity here.</>}</p>}
      <div className="insights-grid">
        <section className="insight-card">
          <div className="section-label"><span className="number-label">01</span><h2>Decisions at a glance</h2></div>
          {data.decided?<>
            <div className="distribution" aria-label={`${data.accepted} accepted, ${data.rejected} rejected`}><span style={{width:`${data.accepted/data.decided*100}%`}}/><span style={{width:`${data.rejected/data.decided*100}%`}}/></div>
            <div className="distribution-legend"><span><i className="legend-dot lime"/>{data.accepted} accepted</span><span><i className="legend-dot blue-bg"/>{data.rejected} rejected</span></div>
          </>:<div className="insight-empty"><Icon name="chart" size={30}/><p>Waiting for a saved accept or reject decision.</p></div>}
          <p className="small muted">Agreement is a workflow measure, not proof of correctness. Quality needs independent review.</p>
        </section>
        <section className="insight-card learning-card">
          <span className="eyebrow">LEARNING FROM EXPERIENCE</span><h2>{data.corrections}<span> officer corrections</span></h2>
          <p>{data.eligible} reviewed examples are approved for use in future case reviews.</p>
          <div className="learning-path"><span>Decision</span><Icon name="arrow" size={13}/><span>Human QA</span><Icon name="arrow" size={13}/><span>Future reviews</span></div>
          <p className="small muted">Examples provide context. A trained model update has not yet been verified.</p>
        </section>
        <section className="insight-card locations-card">
          <div className="section-label"><span className="number-label">02</span><h2>Locations to keep an eye on</h2></div>
          <p className="muted">Accepted appeals by location. A pattern is a reason to investigate, not proof of a street defect.</p>
          {data.locations.length?<table className="table"><thead><tr><th>Location</th><th>Accepted</th><th>Cases</th></tr></thead><tbody>{data.locations.map(l=><tr key={l.location}><td><strong>{l.location}</strong></td><td>{l.accepted}</td><td className="mono small">{l.cases.join(", ")}</td></tr>)}</tbody></table>:<p className="insight-empty">No accepted appeal decisions yet. Locations will appear when an officer saves an acceptance.</p>}
        </section>
      </div>
    </>}
  </div>;
}
