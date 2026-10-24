import { useState } from "react";
import { api } from "./api.js";
import { Card } from "./ui.jsx";

const GROUNDS = ["paid", "permit", "blue_badge", "loading", "signage", "medical_emergency", "breakdown", "other"];
const CODES = [["01", "Restricted street"], ["05", "After paid time"], ["11", "Without payment"],
  ["12", "Residents' bay without permit"], ["40", "Disabled bay without badge"]];

const today = () => new Date().toISOString().slice(0, 10);

const EXAMPLE_EXTRAS = {
  evidence: [
    { id: "E1", type: "ceo_photo", source: "council", description: "CEO photographs", vrm_seen: "SYN1234" },
    { id: "E2", type: "payment_receipt", source: "motorist", description: "App payment screenshot" },
  ],
  records: {
    payments: [{ reference: "PAY-001", vrm: "SYN1234", zone: "Z1", start: "2026-09-01T09:00:00", end: "2026-09-01T11:00:00" }],
  },
};

export default function CaseIntake({ onCreated, onImported }) {
  const [form, setForm] = useState({
    pcn_ref: `DMN${String(Date.now()).slice(-6)}`, vrm: "SYN1234", contravention_code: "11",
    contravention_datetime: "2026-09-01T10:15", location: "Elm Row, Demo Borough", zone: "Z1",
    notice_date: "2026-09-01", representation_received_date: today(), observation_minutes: "",
    representation_text: "", claimed_grounds: ["paid"],
  });
  const [extras, setExtras] = useState(JSON.stringify(EXAMPLE_EXTRAS, null, 2));
  const [bulk, setBulk] = useState("");
  const [msg, setMsg] = useState(null);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const toggle = (g) => setForm({
    ...form,
    claimed_grounds: form.claimed_grounds.includes(g) ? form.claimed_grounds.filter((x) => x !== g) : [...form.claimed_grounds, g],
  });

  const submit = async () => {
    setMsg(null);
    let ex;
    try { ex = JSON.parse(extras || "{}"); } catch { setMsg({ err: "Evidence/records JSON is not valid JSON." }); return; }
    const body = {
      ...form, ...ex, synthetic: true,
      observation_minutes: form.observation_minutes === "" ? null : Number(form.observation_minutes),
    };
    try {
      const created = await api.createCase(body);
      onCreated(created.id);
    } catch (e) {
      setMsg({ err: e.message });
    }
  };

  const importBulk = async () => {
    setMsg(null);
    try {
      const list = JSON.parse(bulk);
      const r = await api.importCases(Array.isArray(list) ? list : [list]);
      setMsg({ ok: `Imported ${r.created.length}; skipped duplicates: ${r.skipped_duplicates.join(", ") || "none"}` });
      onImported();
    } catch (e) {
      setMsg({ err: e.message });
    }
  };

  return (
    <div className="detail">
      <h2>New PCN challenge</h2>
      <p className="muted small">Use synthetic data only. Validation and deterministic checks run on save.</p>
      {msg && <div className={`banner ${msg.err ? "error" : "ok"}`}>{msg.err || msg.ok}</div>}
      <Card title="Case details">
        <div className="form-grid">
          <label>PCN reference<input value={form.pcn_ref} onChange={set("pcn_ref")} /></label>
          <label>VRM (synthetic)<input value={form.vrm} onChange={set("vrm")} /></label>
          <label>Contravention code
            <select value={form.contravention_code} onChange={set("contravention_code")}>
              {CODES.map(([c, l]) => <option key={c} value={c}>{c} · {l}</option>)}
            </select>
          </label>
          <label>Contravention time<input type="datetime-local" value={form.contravention_datetime} onChange={set("contravention_datetime")} /></label>
          <label>Location<input value={form.location} onChange={set("location")} /></label>
          <label>Zone<input value={form.zone} onChange={set("zone")} /></label>
          <label>Notice date<input type="date" value={form.notice_date} onChange={set("notice_date")} /></label>
          <label>Representation received<input type="date" value={form.representation_received_date} onChange={set("representation_received_date")} /></label>
          <label>Observation (min)<input type="number" min="0" value={form.observation_minutes} onChange={set("observation_minutes")} /></label>
        </div>
        <div className="grounds">
          <span className="muted small">Claimed grounds:</span>
          {GROUNDS.map((g) => (
            <label key={g} className="check"><input type="checkbox" checked={form.claimed_grounds.includes(g)} onChange={() => toggle(g)} />{g.replace("_", " ")}</label>
          ))}
        </div>
        <label className="block">Representation text
          <textarea rows={4} value={form.representation_text} onChange={set("representation_text")} placeholder="The motorist's representation…" />
        </label>
        <label className="block">Evidence metadata and council records (JSON)
          <textarea rows={12} className="mono" value={extras} onChange={(e) => setExtras(e.target.value)} />
        </label>
        <div className="btn-row end"><button className="btn primary" onClick={submit}>Create case</button></div>
      </Card>
      <Card title="Import cases (JSON array)">
        <textarea rows={6} className="mono" value={bulk} onChange={(e) => setBulk(e.target.value)} placeholder='[{"pcn_ref": "...", ...}]' />
        <div className="btn-row end"><button className="btn" onClick={importBulk} disabled={!bulk.trim()}>Import</button></div>
      </Card>
    </div>
  );
}
