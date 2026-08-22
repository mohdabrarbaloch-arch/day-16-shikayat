/* Shikayat — tiny API client (no frameworks, no build step) */
const API = {
  base: "/api",

  async request(method, path, body, auth = true) {
    const headers = { "Content-Type": "application/json" };
    const token = localStorage.getItem("sk_token");
    if (auth && token) headers.Authorization = `Bearer ${token}`;

    const res = await fetch(this.base + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (res.status === 401 && auth) {
      localStorage.removeItem("sk_token");
      localStorage.removeItem("sk_user");
      showAuth();
      throw new Error("Session expired. Please log in again.");
    }

    let data = null;
    try { data = await res.json(); } catch { /* empty body */ }
    if (!res.ok) {
      const detail = data?.detail;
      const msg = Array.isArray(detail) ? detail.map((d) => d.msg).join(", ") : detail || `Request failed (${res.status})`;
      throw new Error(msg);
    }
    return data;
  },

  get(path, auth = true) { return this.request("GET", path, null, auth); },
  post(path, body, auth = true) { return this.request("POST", path, body, auth); },
  patch(path, body, auth = true) { return this.request("PATCH", path, body, auth); },

  // Auth
  login: (email, password) => API.post("/auth/login", { email, password }, false),
  register: (payload) => API.post("/auth/register", payload, false),

  // Data
  categories: () => API.get("/categories", false),
  publicStats: () => API.get("/stats/public", false),
  complaints: (params = "") => API.get(`/complaints${params}`),
  complaint: (id) => API.get(`/complaints/${id}`),
  createComplaint: (payload) => API.post("/complaints", payload),
  transition: (id, payload) => API.post(`/complaints/${id}/transition`, payload),
  assign: (id, payload) => API.post(`/complaints/${id}/assign`, payload),
  comment: (id, body) => API.post(`/complaints/${id}/comments`, { body }),
  officers: () => API.get("/admin/officers"),
  adminStats: () => API.get("/admin/stats"),
  myQueue: () => API.get("/officers/me/queue"),
};

/* ---------- helpers ---------- */
function $id(id) { return document.getElementById(id); }
function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}
function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}
function statusBadge(status) {
  const map = {
    submitted: ["Submitted", "badge-blue"],
    verified: ["Verified", "badge-gold"],
    in_progress: ["In Progress", "badge-gold"],
    resolved: ["Resolved", "badge-green"],
    rejected: ["Rejected", "badge-red"],
    reopened: ["Reopened", "badge-red"],
  };
  const [label, cls] = map[status] || [status, "badge-gray"];
  return `<span class="badge ${cls}">${label}</span>`;
}
function toast(msg, type = "") {
  const t = $id("toast");
  t.textContent = msg;
  t.className = `toast ${type}`;
  t.classList.remove("hidden");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add("hidden"), 3200);
}
