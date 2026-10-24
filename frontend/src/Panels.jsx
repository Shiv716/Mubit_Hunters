import { useEffect, useState } from "react";
import { api } from "./api.js";
import { Card, Chip, RecChip, fmt } from "./ui.jsx";

export function FeedbackView({ onError }) {
  const [items, setItems] = useState([]);
  const [evals, setEvals] = useState([]);
  const load = () => {
    api.feedback().then(setItems).catch((e) => onError(e.message));
    api.evaluations().then(setEvals).catch(() => {});
  };
  useEffect(load, []);

  const curate = async (id, eligible) => {
    try {
      await api.curate(id, { eligible, curator: localStorage.getItem("reviewer") || "curator.demo" });
      load();
    } catch (e) {
      onError(e.message);
    }
  };

  return (
    <div className="page">
      <div className="banner info">
        <strong>Precedent retrieval is not model training.</strong> Curated officer decisions are retrieved for similar
        cases and passed to the model as guidance. Mubit adapter training is managed in the Mubit console and is
        <strong> pending</strong> for this app — see the Mubit integration tab.
      </div>
      <Card title="Reviewed feedback examples" aside={<span className="muted small">Only “eligible” examples are retrieved</span>}>
        {items.length === 0 ? <p className="muted">No reviewed decisions yet.</p> : (
          <table className="table">
            <thead><tr><th>#</th><th>Case</th><th>Code</th><th>AI</th><th>Officer</th><th>Reason</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {items.map((f) => (
                <tr key={f.id}>
                  <td className="mono">PREC-{f.id}</td>
                  <td className="mono">{f.pcn_ref}</td>
                  <td>{f.contravention_code}</td>
                  <td>{f.ai_label ? <RecChip rec={f.ai_label} /> : "—"}</td>
                  <td><RecChip rec={f.final_label} /></td>
                  <td className="small">{f.correction_reason || <span className="muted">—</span>}</td>
                  <td><Chip tone={f.curation_status === "eligible" ? "ok" : f.curation_status === "ineligible" ? "bad" : "neutral"}>{f.curation_status}</Chip></td>
                  <td className="nowrap">
                    <button className="btn tiny" onClick={() => curate(f.id, true)}>Eligible</button>
                    <button className="btn tiny" onClick={() => curate(f.id, false)}>Exclude</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Card title="Evaluation runs" aside={<code className="small">python eval/run_eval.py --record</code>}>
        {evals.length === 0 ? (
          <p className="muted">No recorded runs. Run the command above from <code>backend/</code>; it compares baseline vs
            precedent-informed on the fixed holdout set and writes a report to <code>eval/results/</code>.</p>
        ) : evals.map((e) => {
          const r = e.report;
          return (
            <div key={e.id} className="eval">
              <div className="row-between">
                <strong>{fmt(e.created_at)} · {r.provider} · {r.model}</strong>
                <span className="muted small">{r.dataset_version} · holdout n={r.baseline.n} · pool n={r.pool_size}</span>
              </div>
              {r.provider === "offline-stub" && <div className="small warn-text">Offline stub run — measures the pipeline, not Mubit.</div>}
              <table className="table compact">
                <thead><tr><th></th><th>Deterministic</th><th>Baseline</th><th>With precedents</th></tr></thead>
                <tbody>
                  <tr><td>Accuracy</td><td>{r.deterministic.accuracy}</td><td>{r.baseline.effective.accuracy}</td><td>{r.feedback.effective.accuracy}</td></tr>
                  <tr><td>Macro-F1</td><td>{r.deterministic.macro_f1}</td><td>{r.baseline.effective.macro_f1}</td><td>{r.feedback.effective.macro_f1}</td></tr>
                  <tr><td>Failure rate</td><td>–</td><td>{r.baseline.failure_rate}</td><td>{r.feedback.failure_rate}</td></tr>
                  <tr><td>Unsupported refs</td><td>–</td><td>{r.baseline.unsupported_reference_rate}</td><td>{r.feedback.unsupported_reference_rate}</td></tr>
                </tbody>
              </table>
              <div className="small">McNemar p = {r.paired.mcnemar_p} · <strong>{r.gates.verdict}</strong></div>
            </div>
          );
        })}
      </Card>
    </div>
  );
}

const STATUS_TONE = { implemented: "ok", configured: "ok", documented: "info", console_only: "warn", not_documented: "bad" };

export function MubitView({ health }) {
  const [caps, setCaps] = useState(null);
  useEffect(() => { api.capabilities().then(setCaps); }, []);
  return (
    <div className="page">
      <Card title="Connection">
        {health && (
          <p>
            Provider: <strong>{health.ai_provider === "mubit" ? "Mubit (live)" : "Offline stub — not Mubit"}</strong>
            {health.mubit_route && <> · route <span className="mono">{health.mubit_route}</span> · model <span className="mono">{health.model}</span></>}
            {health.mubit_base_url && <> · <span className="mono">{health.mubit_base_url}</span></>}
            {health.mubit_record && <> · recording: <span className="mono">{health.mubit_record}</span></>}
            {!health.mubit_configured && <span className="muted"> · set MUBIT_API_KEY in backend/.env to enable</span>}
          </p>
        )}
      </Card>
      {caps && (
        <Card title="Verified capability matrix" aside={<span className="muted small">checked {caps.verified_on} against public docs</span>}>
          <table className="table">
            <tbody>
              {caps.items.map((i) => (
                <tr key={i.capability}>
                  <td><strong>{i.capability}</strong></td>
                  <td><Chip tone={STATUS_TONE[i.status]}>{i.status.replace("_", " ")}</Chip></td>
                  <td className="small">{i.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">Sources: {caps.sources.join(" · ")}</p>
        </Card>
      )}
    </div>
  );
}

export function AuditView() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.audit().then(setRows); }, []);
  return (
    <div className="page">
      <Card title="Audit log (append-only)">
        <table className="table compact">
          <thead><tr><th>Time</th><th>Case</th><th>Event</th><th>Actor</th><th>Detail</th></tr></thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id}>
                <td className="nowrap small">{fmt(e.created_at)}</td>
                <td>{e.case_id ?? "—"}</td>
                <td>{e.event_type.replaceAll("_", " ")}</td>
                <td>{e.actor}</td>
                <td className="mono tiny-text">{JSON.stringify(e.detail)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
