// The only file that talks to the server. Same-origin, so no CORS and no URLs to configure.
// The CSRF token lives in memory only (never in browser storage), as the backend guide requires.
let csrfToken = null;
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export class ApiError extends Error {
  constructor(status, code, message, requestId) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId || null;
  }
}

const SESSION_CODES = new Set(["AUTH_REQUIRED", "AUTH_SESSION_EXPIRED"]);

async function request(method, path, body, { raw = false, retry = true } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (UNSAFE.has(method) && csrfToken) headers["X-CSRF-Token"] = csrfToken;

  let res;
  try {
    res = await fetch(path, {
      method, headers, credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Cannot reach the SideWatch server. Check that it is running.");
  }

  if (!res.ok) {
    let j = {};
    try { j = await res.json(); } catch { /* non-JSON body: never show raw text */ }
    const err = new ApiError(res.status, j.code || "ERROR", j.message || "Request failed.", j.request_id);
    if (err.code === "CSRF_FAILED" && retry && path !== "/api/auth/csrf") {
      await api.refreshCsrf();                       // token may have rotated in another tab
      return request(method, path, body, { raw, retry: false });
    }
    if (SESSION_CODES.has(err.code) && path !== "/api/auth/me") {
      window.dispatchEvent(new CustomEvent("sw:unauthenticated"));
    }
    throw err;
  }
  return raw ? res : res.json();
}

const qs = (o = {}) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v !== "" && v != null) p.set(k, v);
  const s = p.toString();
  return s ? "?" + s : "";
};

const resultCache = new Map();   // results never change once stored, so caching is safe

export const api = {
  async login(username, password) {
    const r = await request("POST", "/api/auth/login", { username, password });
    csrfToken = r.csrf_token;
    return r.user;
  },
  async logout() { try { await request("POST", "/api/auth/logout", {}); } finally { csrfToken = null; resultCache.clear(); } },
  me: () => request("GET", "/api/auth/me"),
  async refreshCsrf() { csrfToken = (await request("GET", "/api/auth/csrf")).csrf_token; },
  async changePassword(current_password, new_password) {
    const r = await request("POST", "/api/auth/change-password", { current_password, new_password });
    csrfToken = r.csrf_token;
    return r.user;
  },

  fixtures: () => request("GET", "/api/fixtures"),
  createSubmission: (b) => request("POST", "/api/submissions", b),
  listSubmissions: (q) => request("GET", "/api/submissions" + qs(q)),
  getSubmission: (id) => request("GET", `/api/submissions/${encodeURIComponent(id)}`),
  async getResult(id) {
    if (resultCache.has(id)) return resultCache.get(id);
    const r = await request("GET", `/api/submissions/${encodeURIComponent(id)}/result`);
    resultCache.set(id, r);
    return r;
  },
  async downloadReport(id) {
    const res = await request("GET", `/api/submissions/${encodeURIComponent(id)}/report`, undefined, { raw: true });
    return { filename: `sidewatch-report-${id}.json`, blob: await res.blob() };
  },

  rules: () => request("GET", "/api/rules"),
  updateRule: (key, value) => request("PUT", `/api/rules/${encodeURIComponent(key)}`, { value, confirm: true }),

  users: () => request("GET", "/api/users"),
  createUser: (username, password, role) => request("POST", "/api/users", { username, password, role }),
  setUserActive: (id, is_active) => request("PATCH", `/api/users/${encodeURIComponent(id)}/active`, { is_active }),
  resetPassword: (id, new_password) => request("POST", `/api/users/${encodeURIComponent(id)}/reset-password`, { new_password, confirm: true }),

  audit: (q) => request("GET", "/api/audit" + qs(q)),
  verifyAudit: () => request("GET", "/api/audit/verify"),
};
