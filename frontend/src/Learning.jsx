import { useEffect, useState } from "react";
import { api } from "./api.js";
import { Card, Chip, RecChip, fmt } from "./ui.jsx";

const listFields = [
  ["relevant_rule_references", "Policy and rule references"],
  ["evidence_references", "Evidence references"],
  ["missing_information", "Missing information"],
  ["uncertainty_flags", "Uncertainties"],
];

function CorrectionEditor({ item, canManage, onSave, onError }) {
  const initial = item.target || (item.parsed && {
    ...item.parsed,
    recommendation: item.human_judgement_required ? "needs_review" : item.final_label,
    reason_summary: item.correction_reason || item.parsed.reason_summary,
  });
  const [target, setTarget] = useState(initial);
  const [note, setNote] = useState(item.note || item.correction_reason || "");
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState("");
  const update = (key, value) => { setTarget(current => ({ ...current, [key]: value })); setDirty(true); setMessage(""); };
  const save = async state => {
    setBusy(true); setMessage("");
    try {
      const saved = await api.saveCorrection(item.id, {
        state, target: state === "approved" ? {
          ...target, ...Object.fromEntries(listFields.map(([key]) => [key, target[key].map(value => value.trim()).filter(Boolean)])),
        } : null, note, previous_revision: item.correction_id,
      });
      onError("");
      onSave(saved);
    } catch (error) { onError(error.message); setMessage(error.message); }
    finally { setBusy(false); }
  };
  return <div className="correction-comparison">
    <section className="correction-panel">
      <div className="eyebrow">01 / BEFORE</div>
      <h4>Original AI review</h4>
      <RecChip rec={item.effective_recommendation} />
      <p className="correction-text">{item.parsed?.reason_summary || "No successful AI answer was saved."}</p>
      <div className="small muted">Officer decided: <RecChip rec={item.final_label}/></div>
      {item.correction_reason && <p className="small">{item.correction_reason}</p>}
      <details className="correction-details"><summary>Original answer & provenance</summary>
        <p className="small">{item.provider} · {item.model || "No model"}<br/>
          Review #{item.review_id || "—"} · {item.policy_version || "Input not captured"}</p>
        {item.provider_request_id && <p className="small mono">{item.provider_request_id}</p>}
        <pre>{item.raw_output || "No original answer"}</pre>
      </details>
    </section>
    <section className="correction-panel correction-target">
      <div className="eyebrow">02 / OFFICER CORRECTION</div>
      <h4>{item.state === "approved" ? dirty ? "Proposed revision" : "Approved target" : "Proposed target"}</h4>
      {item.blocked_reason ? <p className="muted">{item.blocked_reason}</p> : target && <form onSubmit={event => { event.preventDefault(); save("approved"); }}>
        <fieldset disabled={busy || !canManage}>
          <label>What should the AI recommend?
            <select value={target.recommendation} onChange={e => update("recommendation", e.target.value)}>
              <option value="accept">Accept representation</option><option value="reject">Reject representation</option>
              <option value="needs_review">Needs officer review</option>
            </select>
          </label>
          <label className="field">Corrected explanation
            <textarea required rows={5} maxLength={2000} value={target.reason_summary} onChange={e => update("reason_summary", e.target.value)}/>
          </label>
          <label className="field">Missing facts (clear items that no longer apply)
            <textarea rows={2} value={target.missing_information.join("\n")} onChange={e => update("missing_information", e.target.value.split("\n"))}/>
          </label>
          {item.human_judgement_required && <p className="small warn-text">The officer can decide this case, but the AI must still refer discretionary decisions for human judgement.</p>}
          <details className="correction-details"><summary>References, missing facts & draft</summary>
            <p className="small muted">Use one entry per line. Available references: {item.allowed_policy_references.join(", ") || "none"}.
              Evidence: {item.allowed_evidence_references.join(", ") || "none"}.</p>
            {listFields.filter(([key]) => key !== "missing_information").map(([key, label]) => <label className="field" key={key}>{label}
              <textarea rows={2} value={target[key].join("\n")} onChange={e => update(key, e.target.value.split("\n"))}/>
            </label>)}
            <label className="field">Model draft, if appropriate
              <textarea rows={4} value={target.draft_response || ""} onChange={e => update("draft_response", e.target.value || null)}/>
            </label>
          </details>
          <label className="field">Why is this the right correction?
            <textarea required rows={2} maxLength={2000} value={note} onChange={e => { setNote(e.target.value); setDirty(true); setMessage(""); }}/>
          </label>
          <div className="correction-actions">
            <button className="btn primary" type="submit">{busy ? "Saving…" : item.state === "approved" ? "Approve new revision" : "Approve correction"}</button>
            {item.state === "approved" && <button className="btn" type="button" onClick={() => save("withdrawn")}>Withdraw</button>}
          </div>
        </fieldset>
        {!canManage && <p className="muted small">The workspace owner approves model corrections.</p>}
        {message && <p role="alert" className="small warn-text">{message}</p>}
      </form>}
      {item.state === "approved" && <p className="small muted" role="status">Approved by {item.approved_by} · {fmt(item.approved_at)}. Saved in the workspace; not submitted to Mubit.</p>}
      {item.state === "withdrawn" && <p className="small muted" role="status">Correction withdrawn. Previous revisions remain in the audit history.</p>}
    </section>
    <section className="correction-pending">
      <div><div className="eyebrow">03 / AFTER MODEL UPDATE</div><h4>Awaiting a trained Mubit version</h4></div>
      <Chip tone="warn">Not connected</Chip>
      <p>Next: submit approved corrections through Mubit's supported interface, then compare the trained version on separate test cases. No updated-model result is available yet.</p>
    </section>
  </div>;
}

export function LearningCorrections({ canManage, onError }) {
  const [items, setItems] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const load = () => api.learningExamples().then(data => { setItems(data.items); setError(""); }).catch(e => setError(e.message));
  useEffect(() => { load(); }, []);
  const item = items?.find(row => row.id === selected) || items?.[0];
  const ready = items?.filter(row => row.exportable).length || 0;
  const download = async () => {
    setExporting(true);
    try {
      const data = await api.exportCorrections();
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const link = document.createElement("a"); link.href = url; link.download = "civic-corrections.json";
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { onError(e.message); }
    finally { setExporting(false); }
  };
  return <Card title="From correction to learning" aside={<Chip tone="warn">Training connection pending</Chip>}>
    <p className="small muted">Review the original answer, approve what the AI should have said, then test a trained version before deployment.</p>
    {error ? <p role="alert">{error} <button className="btn tiny" onClick={load}>Retry</button></p> : items === null ? <p className="muted">Loading corrections…</p> : !items.length ?
      <p className="muted">Save an officer decision after an AI review to prepare its correction here.</p> : <>
        <div className="correction-toolbar">
          <label>Reviewed case<select value={item.id} onChange={e => setSelected(Number(e.target.value))}>
            {items.map(row => <option value={row.id} key={row.id}>{row.pcn_ref} · {row.state || (row.blocked_reason ? "historical" : "awaiting approval")}</option>)}
          </select></label>
          {canManage && <button className="btn" disabled={!ready || exporting} onClick={download}>{exporting ? "Preparing…" : `Download corrections (${ready})`}</button>}
        </div>
        {item.provider === "offline-stub" && <p className="small warn-text">Local simulation — this example is excluded from the Mubit export.</p>}
        <CorrectionEditor key={`${item.id}-${item.correction_id}`} item={item} canManage={canManage} onError={onError}
          onSave={saved => setItems(current => current.map(row => row.id === saved.id ? saved : row))}/>
        <p className="small muted">Downloads use Civic's review format. Downloading does not send data to Mubit or train a model.</p>
      </>}
  </Card>;
}
