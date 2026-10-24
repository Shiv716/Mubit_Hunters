async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: options.body instanceof FormData ? {} : { "content-type": "application/json" },
    ...options,
  });
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

const post = (path, body) => request(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  session: () => request("/session"),
  login: (body) => post("/session", body),
  logout: () => request("/session", { method: "DELETE" }),
  queue: () => request("/queue"),
  insights: () => request("/insights"),
  review: (id) => post(`/cases/${id}/review`),
  resolve: (id, body) => post(`/cases/${id}/resolve`, body),
  draft: (id, outcome, reason = "") => request(`/cases/${id}/draft?${new URLSearchParams({outcome, reason})}`),
  health: () => request("/health"),
  policy: () => request("/policy"),
  capabilities: () => request("/mubit/capabilities"),
  cases: () => request("/cases"),
  getCase: (id) => request(`/cases/${id}`),
  createCase: (c) => post("/cases", c),
  importCases: (list) => post("/cases/import", list),
  seedDemo: () => post("/demo/seed"),
  rerunChecks: (id) => post(`/cases/${id}/checks`),
  aiReview: (id, mode) => post(`/cases/${id}/ai-review?mode=${mode}`),
  decide: (id, body) => post(`/cases/${id}/decision`, body),
  uploadEvidence: (id, evidenceId, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request(`/cases/${id}/evidence/${evidenceId}/file`, { method: "POST", body: fd });
  },
  feedback: () => request("/feedback"),
  curate: (id, body) => post(`/feedback/${id}/curate`, body),
  audit: () => request("/audit"),
  evaluations: () => request("/evaluations"),
};
