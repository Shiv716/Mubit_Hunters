async function request(path, options = {}) {
  const response = await fetch(`/api/consumer${path}`, {
    headers: options.body instanceof FormData ? {} : {"Content-Type": "application/json"},
    ...options,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(Array.isArray(detail) ? detail.map(item => item.msg).join(". ") : detail || "The request could not be completed. Please try again.");
  }
  return data;
}
const send = (path, body, method = "POST") => request(path, {method, ...(body !== undefined ? {body: JSON.stringify(body)} : {})});
export const driverApi = {
  session: () => request("/session"),
  requestCode: email => send("/session/request", {email}),
  verify: body => send("/session/verify", body),
  logout: () => send("/session", undefined, "DELETE"),
  publicInfo: () => request("/public"),
  cases: () => request("/cases"),
  create: () => send("/cases"),
  get: id => request(`/cases/${id}`),
  save: (id, body) => send(`/cases/${id}`, body, "PUT"),
  remove: id => send(`/cases/${id}`, undefined, "DELETE"),
  upload: (id, file, kind) => {const data = new FormData(); data.append("file", file); data.append("kind", kind); return request(`/cases/${id}/evidence`, {method: "POST", body: data});},
  removePhoto: (id, photo) => send(`/cases/${id}/evidence/${photo}`, undefined, "DELETE"),
  scan: id => send(`/cases/${id}/scan`),
  assess: id => send(`/cases/${id}/assess`),
  draft: (id, body) => send(`/cases/${id}/draft`, body, "PUT"),
  submitted: (id, body) => send(`/cases/${id}/tracking/submitted`, body),
  outcome: (id, body) => send(`/cases/${id}/tracking/outcome`, body),
};
