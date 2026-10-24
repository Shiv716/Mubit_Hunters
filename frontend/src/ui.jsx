export function Chip({ tone = "neutral", children, title }) {
  return <span className={`chip ${tone}`} title={title}>{children}</span>;
}

const REC_TONE = { accept: "ok", reject: "bad", needs_review: "warn" };
const REC_LABEL = { accept: "Accept representation", reject: "Reject representation", needs_review: "Needs review" };

export function RecChip({ rec, prefix = "" }) {
  if (!rec) return null;
  return <Chip tone={REC_TONE[rec] || "neutral"}>{prefix}{rec.replace("_", " ")}</Chip>;
}

export function recLabel(rec) {
  return REC_LABEL[rec] || rec;
}

const OUT = {
  representation_accepted: ["ok", "Accepted"],
  representation_rejected: ["bad", "Rejected"],
  escalated: ["warn", "Escalated"],
};

export function OutcomeChip({ outcome }) {
  const [tone, label] = OUT[outcome] || ["neutral", outcome];
  return <Chip tone={tone}>Officer: {label}</Chip>;
}

const EFFECT = {
  supports_accept: ["ok", "supports accept"],
  supports_reject: ["bad", "supports reject"],
  needs_review: ["warn", "needs review"],
  neutral: ["neutral", "neutral"],
};

export function EffectChip({ effect }) {
  const [tone, label] = EFFECT[effect] || ["neutral", effect];
  return <Chip tone={tone}>{label}</Chip>;
}

export function Card({ title, aside, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || aside) && (
        <header className="card-head">
          <h3>{title}</h3>
          {aside}
        </header>
      )}
      {children}
    </section>
  );
}

export function List({ items, empty = "None" }) {
  if (!items || items.length === 0) return <p className="muted small">{empty}</p>;
  return <ul className="plain">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>;
}

export function fmt(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  return isNaN(d) ? ts : d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}
