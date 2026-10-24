const reads = new Map();
const READ_TTL = 10_000;

export function clearReadCache() { reads.clear(); }

// Memory only: short-lived navigation data, never sessions or access requests.
function cachedGet(path) {
  const existing = reads.get(path);
  if (existing && existing.expiresAt > Date.now()) return existing.promise;
  const entry = { expiresAt: Infinity, promise: null };
  entry.promise = request(path).then(data => {
    entry.expiresAt = Date.now() + READ_TTL;
    return data;
  }).catch(error => {
    if (reads.get(path) === entry) reads.delete(path);
    throw error;
  });
  if (reads.size >= 100) reads.delete(reads.keys().next().value);
  reads.set(path, entry);
  return entry.promise;
}

if (typeof window !== "undefined") {
  window.addEventListener("focus", clearReadCache);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") clearReadCache();
  });
}

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: options.body instanceof FormData ? {} : { "content-type": "application/json" },
    ...options,
  });
  if (res.status === 401 || res.status === 403) clearReadCache();
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : null; } catch { throw new Error("The server returned an unexpected response. Please try again."); }
  if (!res.ok) {
    const detail = data?.detail;
    const msg = Array.isArray(detail)
      ? detail.map((d) => `${d.loc?.slice(1).join(".")}: ${d.msg}`).join("; ")
      : detail || res.statusText;
    throw new Error(msg);
  }
  return data;
}

async function mutate(path, options) {
  clearReadCache();
  try { return await request(path, options); }
  finally { clearReadCache(); }
}
const post = (path, body) => mutate(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  session: () => request("/session"),
  login: (body) => post("/session", body),
  requestEmailCode: (body) => post("/session/email/request", body),
  verifyEmailCode: (body) => post("/session/email/verify", body),
  requestAccess: body => post("/access-requests", body),
  inspectApproval: body => post("/access-requests/inspect", body),
  approveAccess: body => post("/access-requests/approve", body),
  accessRequests: () => request("/access-requests"),
  accessDecision: (id, body) => post(`/access-requests/${id}/decision`, body),
  logout: () => mutate("/session", { method: "DELETE" }),
  queue: () => cachedGet("/queue"),
  insights: () => cachedGet("/insights"),
  review: (id) => post(`/cases/${id}/review`),
  resolve: (id, body) => post(`/cases/${id}/resolve`, body),
  draft: (id, outcome, reason = "") => request(`/cases/${id}/draft?${new URLSearchParams({outcome, reason})}`),
  health: () => request("/health"),
  policy: () => cachedGet("/policy"),
  capabilities: () => cachedGet("/mubit/capabilities"),
  cases: () => request("/cases"),
  getCase: (id) => cachedGet(`/cases/${id}`),
  createCase: (c) => post("/cases", c),
  importCases: (list) => post("/cases/import", list),
  seedDemo: () => post("/demo/seed"),
  rerunChecks: (id) => post(`/cases/${id}/checks`),
  aiReview: (id, mode) => post(`/cases/${id}/ai-review?mode=${mode}`),
  decide: (id, body) => post(`/cases/${id}/decision`, body),
  uploadEvidence: (id, evidenceId, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return mutate(`/cases/${id}/evidence/${evidenceId}/file`, { method: "POST", body: fd });
  },
  feedback: () => cachedGet("/feedback"),
  curate: (id, body) => post(`/feedback/${id}/curate`, body),
  audit: () => cachedGet("/audit"),
  evaluations: () => cachedGet("/evaluations"),
};
