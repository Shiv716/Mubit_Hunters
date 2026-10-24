import { useEffect, useMemo, useState } from "react";
import { api } from "./api.js";
import { Card, Chip, EffectChip, List, OutcomeChip, RecChip, fmt, recLabel } from "./ui.jsx";

const REASON_CODES = [
  ["", "— reason code —"],
  ["facts_misread", "AI misread the facts"],
  ["policy_discretion", "Officer discretion under policy"],
  ["new_evidence", "Further evidence considered"],
  ["evidence_insufficient", "Evidence insufficient"],
  ["draft_edited", "Draft response edited"],
  ["needs_senior_review", "Needs senior review / site check"],
  ["other", "Other"],
];

export default function CaseDetail({ caseId, policy, onChanged, onError }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = () => api.getCase(caseId).then(setD).catch((e) => onError(e.message));
  useEffect(() => { load(); }, [caseId]);

  const act = async (label, fn) => {
    setBusy(label);
    try {
      setD(await fn());
      onChanged();
    } catch (e) {
      onError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const refs = useMemo(() => Object.fromEntries((policy?.references || []).map((r) => [r.id, r])), [policy]);

  if (!d) return <div className="empty">Loading…</div>;
  const c = d.case;
  const check = d.checks;
  const review = d.ai_reviews[0];
  const decided = d.status === "decided";
  const uploads = Object.fromEntries(d.evidence_files.map((f) => [f.evidence_id, f]));

  return (
    <div className="detail">
      <div className="detail-head">
        <div>
          <h2 className="mono">{c.pcn_ref}</h2>
          <div className="muted">
            Code {c.contravention_code} · {d.contravention_description || "unknown code"}
          </div>
        </div>
        <div className="chips">
          {c.synthetic && <Chip tone="info">synthetic</Chip>}
          <Chip tone="neutral">{d.status.replace("_", " ")}</Chip>
          {d.decisions[0] && <OutcomeChip outcome={d.decisions[0].final_outcome} />}
        </div>
      </div>

      <div className="grid-2">
        <Card title="Case facts">
          <dl className="facts">
            <dt>Vehicle (VRM)</dt><dd className="mono">{c.vrm}</dd>
            <dt>Contravention</dt><dd>{fmt(c.contravention_datetime)}</dd>
            <dt>Location</dt><dd>{c.location}{c.zone ? ` · zone ${c.zone}` : ""}</dd>
            <dt>Notice date</dt><dd>{c.notice_date}</dd>
            <dt>Representation received</dt><dd>{c.representation_received_date}</dd>
            <dt>Observation</dt><dd>{c.observation_minutes ?? "—"} min</dd>
            <dt>Claimed grounds</dt><dd>{c.claimed_grounds.join(", ") || "—"}</dd>
          </dl>
        </Card>
        <Card title="Representation">
          <blockquote className="rep">{c.representation_text}</blockquote>
          <RecordsSummary records={c.records} />
        </Card>
      </div>

      <Card title="Evidence" aside={<span className="muted small">{c.evidence.length} item(s)</span>}>
        <table className="table">
          <thead><tr><th>ID</th><th>Type</th><th>Source</th><th>Description</th><th>File</th></tr></thead>
          <tbody>
            {c.evidence.map((e) => (
              <tr key={e.id}>
                <td className="mono">{e.id}</td>
                <td>{e.type.replace("_", " ")}</td>
                <td>{e.source}</td>
                <td>{e.description}{e.vrm_seen && <span className="muted small"> · VRM seen {e.vrm_seen}</span>}</td>
                <td>
                  {uploads[e.id] ? (
                    <span className="small" title={uploads[e.id].sha256}>✓ {uploads[e.id].filename}</span>
                  ) : (
                    <span className="muted small">{e.filename ? "metadata only" : "—"}</span>
                  )}
                  {!decided && (
                    <label className="upload">
                      upload
                      <input type="file" accept="image/*,application/pdf,text/plain" onChange={(ev) => {
                        const f = ev.target.files[0];
                        if (f) act("upload", () => api.uploadEvidence(d.id, e.id, f));
                      }} />
                    </label>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {check && (
        <div className="grid-2">
          <Card title="Validation" aside={<span className="muted small">{check.validation.length} issue(s)</span>}>
            {check.validation.length === 0 ? (
              <p className="muted small">No validation issues.</p>
            ) : (
              <ul className="issues">
                {check.validation.map((i, k) => (
                  <li key={k} className={i.severity}>
                    <span className="sev">{i.severity}</span> {i.message}
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Deterministic rule checks"
                aside={<span className="small">Indicator: <RecChip rec={check.indicator} /></span>}>
            <table className="table compact">
              <tbody>
                {check.rules.map((r) => (
                  <tr key={r.rule_id}>
                    <td className="mono nowrap">{r.rule_id}</td>
                    <td><EffectChip effect={r.effect} /><div className="muted small">{r.status.replace("_", " ")}</div></td>
                    <td>{r.finding}
                      {r.policy_refs.length > 0 && <div className="refs">{r.policy_refs.map((p) => <RefTag key={p} id={p} refs={refs} />)}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted small">{check.ruleset_version} · {check.policy_version} · run {fmt(check.created_at)}</p>
          </Card>
        </div>
      )}

      <Card title="AI review" className="ai-card" aside={
        !decided && (
          <div className="btn-row">
            <button className="btn" disabled={!!busy} onClick={() => act("baseline", () => api.aiReview(d.id, "baseline"))}>
              {busy === "baseline" ? "Running…" : "Run baseline"}
            </button>
            <button className="btn primary" disabled={!!busy} onClick={() => act("precedent", () => api.aiReview(d.id, "precedent"))}>
              {busy === "precedent" ? "Running…" : "Run with precedents"}
            </button>
          </div>
        )
      }>
        {!review ? (
          <p className="muted">No AI review yet. The AI drafts a recommendation; the officer decides.</p>
        ) : (
          <AIReview review={review} refs={refs} evidence={c.evidence} />
        )}
      </Card>

      {!decided && <DecisionForm d={d} review={review} busy={busy} act={act} />}

      <div className="grid-2">
        <Card title="Decisions">
          {d.decisions.length === 0 ? <p className="muted small">No decision recorded.</p> : d.decisions.map((x) => (
            <div key={x.id} className="decision">
              <div className="row-between">
                <OutcomeChip outcome={x.final_outcome} />
                <span className="muted small">{fmt(x.created_at)}</span>
              </div>
              <div className="small">
                <strong>{x.reviewer}</strong> · action <b>{x.action}</b> · AI said {x.ai_recommendation ? <RecChip rec={x.ai_recommendation} /> : "—"}
                {x.ai_review_id && <span className="muted"> (AI review #{x.ai_review_id})</span>}
              </div>
              {x.reason && <div className="small">Reason{x.reason_code ? ` [${x.reason_code}]` : ""}: {x.reason}</div>}
              {x.final_response && <details><summary className="small">Final response</summary><pre className="draft">{x.final_response}</pre></details>}
            </div>
          ))}
          {d.ai_reviews.length > 1 && (
            <details>
              <summary className="small">All AI reviews ({d.ai_reviews.length})</summary>
              <ul className="plain small">
                {d.ai_reviews.map((r) => (
                  <li key={r.id}>#{r.id} {fmt(r.created_at)} · {r.mode} · {r.status} · <RecChip rec={r.effective_recommendation} /></li>
                ))}
              </ul>
            </details>
          )}
        </Card>
        <Card title="Audit trail">
          <ol className="timeline">
            {d.audit.map((e) => (
              <li key={e.id}>
                <div className="row-between">
                  <strong className="small">{e.event_type.replaceAll("_", " ")}</strong>
                  <span className="muted small">{fmt(e.created_at)}</span>
                </div>
                <div className="muted small">by {e.actor} · {summarise(e.detail)}</div>
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </div>
  );
}

function summarise(detail) {
  const keys = ["ruleset_version", "indicator", "mode", "provider", "model", "provider_request_id", "status",
    "failure_kind", "effective_recommendation", "action", "final_outcome", "reason", "eligible", "evidence_id"];
  return keys.filter((k) => detail[k] !== undefined && detail[k] !== null).map((k) => `${k}: ${detail[k]}`).join(" · ");
}

function RefTag({ id, refs }) {
  const r = refs[id];
  return <span className="ref" title={r ? `${r.title}: ${r.text}` : "rule id"}>{id}</span>;
}

function RecordsSummary({ records }) {
  const rows = [
    ["Payment records", records.payments],
    ["Permit records", records.permits],
    ["Badge records", records.badges],
  ];
  return (
    <div className="records">
      {rows.map(([label, list]) => (
        <div key={label} className="small">
          <span className="muted">{label}: </span>
          {list == null ? <em className="muted">not supplied</em> : list.length === 0 ? "none" : list.map((x, i) => (
            <span key={i} className="mono record">
              {x.reference || x.permit_id || x.badge_id}
              {x.zone ? ` ${x.zone}` : ""} {fmt(x.start || x.valid_from)} → {fmt(x.end || x.valid_to)}
              {x.displayed === false ? " (not displayed)" : ""}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

function AIReview({ review, refs, evidence }) {
  const p = review.parsed;
  const failed = review.status === "failed";
  const ev = Object.fromEntries(evidence.map((e) => [e.id, e]));
  return (
    <div className="ai">
      <div className="ai-head">
        <div>
          <div className="muted small">Effective recommendation (shown to officer)</div>
          <div className={`big-rec ${review.effective_recommendation}`}>{recLabel(review.effective_recommendation)}</div>
          {p && p.recommendation !== review.effective_recommendation && (
            <div className="small warn-text">
              Model said “{p.recommendation}” — downgraded to needs review by safety checks.
            </div>
          )}
          {failed && <div className="small bad-text">AI review failed ({review.failure_kind}). Shown as needs review; decide manually.</div>}
        </div>
        <div className="meta small">
          <div><span className="muted">provider</span> {review.provider === "offline-stub" ? <Chip tone="warn">offline stub — not Mubit</Chip> : review.provider}</div>
          <div><span className="muted">model</span> {review.model || "—"}</div>
          <div><span className="muted">request id</span> <span className="mono">{review.provider_request_id || "—"}</span></div>
          <div><span className="muted">mode</span> {review.mode} · {review.prompt_version}</div>
          <div><span className="muted">latency</span> {review.latency_ms ?? "—"} ms · {fmt(review.created_at)}</div>
        </div>
      </div>

      {review.safety_flags.length > 0 && (
        <div className="flags">
          <strong className="small">Safety checks</strong>
          <ul className="plain small">{review.safety_flags.map((f) => <li key={f}>⚠ {f}</li>)}</ul>
        </div>
      )}

      {p && (
        <>
          <p className="reason">{p.reason_summary}</p>
          <div className="grid-3">
            <div>
              <h4>Supporting references</h4>
              {p.relevant_rule_references.length === 0 ? <p className="muted small">None</p> :
                <ul className="plain small">{p.relevant_rule_references.map((r) => (
                  <li key={r}><span className="ref">{r}</span> {refs[r]?.title || "rule result"}</li>))}</ul>}
              <h4>Evidence cited</h4>
              <List items={p.evidence_references.map((e) => `${e} · ${ev[e]?.type.replace("_", " ") || ""}`)} />
            </div>
            <div>
              <h4>Missing information</h4>
              <List items={p.missing_information} />
            </div>
            <div>
              <h4>Uncertainty flags</h4>
              <List items={p.uncertainty_flags} />
            </div>
          </div>
          {review.precedent_ids.length > 0 && (
            <p className="small"><span className="muted">Precedents supplied (retrieval, not training):</span> {review.precedent_ids.join(", ")}</p>
          )}
          {review.mode === "precedent" && review.precedent_ids.length === 0 && (
            <p className="muted small">No eligible reviewed precedents matched this case.</p>
          )}
          <h4>Draft response <span className="muted small">(for officer review only — not sent)</span></h4>
          <pre className="draft">{p.draft_response || "No draft."}</pre>
        </>
      )}
      {failed && review.raw_output && (
        <details><summary className="small">Raw provider output / error</summary><pre className="draft">{review.raw_output}</pre></details>
      )}
    </div>
  );
}

function DecisionForm({ d, review, busy, act }) {
  const [action, setAction] = useState("accept");
  const [outcome, setOutcome] = useState("representation_rejected");
  const [reasonCode, setReasonCode] = useState("");
  const [reason, setReason] = useState("");
  const [reviewer, setReviewer] = useState(() => localStorage.getItem("reviewer") || "officer.demo");
  const [response, setResponse] = useState(review?.parsed?.draft_response || "");

  useEffect(() => { setResponse(review?.parsed?.draft_response || ""); }, [review?.id]);

  const aiUsable = review && review.status !== "failed" && review.effective_recommendation !== "needs_review";
  useEffect(() => {
    if (!aiUsable && action === "accept") setAction(review ? "override" : "reject");
  }, [aiUsable, review?.id]);
  const needsReason = action !== "accept";
  const needsOutcome = action === "override" || action === "reject";
  const valid = reviewer.trim() && (!needsReason || reason.trim()) && (action !== "accept" || aiUsable)
    && (action !== "override" || review);

  const submit = () => {
    try { localStorage.setItem("reviewer", reviewer); } catch { /* storage unavailable */ }
    act("decide", () => api.decide(d.id, {
      ai_review_id: review?.id ?? null,
      action,
      final_outcome: needsOutcome ? outcome : null,
      reason_code: reasonCode || null,
      reason: reason || null,
      final_response: action === "escalate" ? null : response || null,
      reviewer,
    }));
  };

  const options = [
    ["accept", "Accept AI recommendation", aiUsable ? `Outcome: ${recLabel(review.effective_recommendation)}` : "Unavailable — no decisive AI recommendation"],
    ["override", "Edit / override", "Change the outcome or the draft; reason required"],
    ["reject", "Reject AI recommendation", "Decide manually without the AI; reason required"],
    ["escalate", "Escalate", "Send for senior review / site check; reason required"],
  ];

  return (
    <Card title="Officer decision" className="decision-card"
          aside={<span className="muted small">Records the decision only. This tool never issues, cancels or submits a PCN.</span>}>
      <div className="actions">
        {options.map(([id, label, hint]) => (
          <label key={id} className={`action ${action === id ? "on" : ""} ${id === "accept" && !aiUsable ? "disabled" : ""}`}>
            <input type="radio" name="action" value={id} checked={action === id}
                   disabled={id === "accept" && !aiUsable} onChange={() => setAction(id)} />
            <span><strong>{label}</strong><span className="muted small">{hint}</span></span>
          </label>
        ))}
      </div>
      <div className="form-grid">
        {needsOutcome && (
          <label>Final outcome
            <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
              <option value="representation_accepted">Accept representation (cancel PCN)</option>
              <option value="representation_rejected">Reject representation (PCN stands)</option>
            </select>
          </label>
        )}
        <label>Reason code
          <select value={reasonCode} onChange={(e) => setReasonCode(e.target.value)}>
            {REASON_CODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label>Reviewer
          <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
        </label>
      </div>
      <label className="block">Reason {needsReason ? <span className="req">required</span> : <span className="muted small">optional</span>}
        <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)}
                  placeholder="Why this decision? Stored separately from the AI output." />
      </label>
      {action !== "escalate" && (
        <label className="block">Final response to motorist (editable draft)
          <textarea rows={5} value={response} onChange={(e) => setResponse(e.target.value)} />
        </label>
      )}
      <div className="btn-row end">
        <button className="btn primary" disabled={!valid || !!busy} onClick={submit}>
          {busy === "decide" ? "Saving…" : "Record decision"}
        </button>
      </div>
    </Card>
  );
}
