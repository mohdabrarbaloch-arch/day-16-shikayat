/* Shikayat — SPA logic: auth, dashboards, report form, modal, admin */
let CURRENT_USER = null;
let CATEGORIES = [];

/* ---------- boot ---------- */
function boot() {
  bindAuth();
  bindNav();
  bindReport();
  bindModal();

  const token = localStorage.getItem("sk_token");
  if (token) {
    const saved = localStorage.getItem("sk_user");
    if (saved) {
      CURRENT_USER = JSON.parse(saved);
      enterApp();
    } else {
      API.get("/auth/me").then((u) => {
        CURRENT_USER = u;
        localStorage.setItem("sk_user", JSON.stringify(u));
        enterApp();
      }).catch(() => showAuth());
    }
  } else {
    showAuth();
  }
  loadCategories();
  loadPublicStats();
}

/* ---------- auth ---------- */
function bindAuth() {
  document.querySelectorAll(".tab[data-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const mode = tab.dataset.tab;
      $id("login-form").classList.toggle("hidden", mode !== "login");
      $id("register-form").classList.toggle("hidden", mode !== "register");
    });
  });

  $id("reg-role").addEventListener("change", (e) => {
    $id("reg-ward-wrap").classList.toggle("hidden", e.target.value !== "officer");
  });

  $id("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const data = await API.login($id("login-email").value.trim(), $id("login-password").value);
      saveSession(data);
      toast("Welcome back! 👋", "success");
    } catch (err) { toast(err.message, "error"); }
  });

  $id("register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: $id("reg-name").value.trim(),
      email: $id("reg-email").value.trim(),
      password: $id("reg-password").value,
      role: $id("reg-role").value,
    };
    const ward = $id("reg-ward").value.trim();
    if (payload.role === "officer") payload.ward = ward || "General";
    try {
      const data = await API.register(payload);
      saveSession(data);
      toast("Account created 🎉", "success");
    } catch (err) { toast(err.message, "error"); }
  });

  $id("logout-btn").addEventListener("click", () => {
    localStorage.removeItem("sk_token");
    localStorage.removeItem("sk_user");
    CURRENT_USER = null;
    showAuth();
  });
}

function saveSession(data) {
  localStorage.setItem("sk_token", data.access_token);
  localStorage.setItem("sk_user", JSON.stringify(data.user));
  CURRENT_USER = data.user;
  enterApp();
}

function showAuth() {
  $id("auth-screen").classList.add("active");
  $id("app-screen").classList.remove("active");
}

function enterApp() {
  $id("auth-screen").classList.remove("active");
  $id("app-screen").classList.add("active");
  $id("user-chip").textContent = `${CURRENT_USER.name} · ${CURRENT_USER.role}`;

  // Role-based nav
  document.querySelectorAll(".admin-only").forEach((el) => el.classList.toggle("hidden", CURRENT_USER.role !== "admin"));
  document.querySelectorAll(".officer-only").forEach((el) => el.classList.toggle("hidden", CURRENT_USER.role !== "officer"));

  switchView("dashboard");
  loadDashboard();
}

/* ---------- navigation ---------- */
function bindNav() {
  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".nav-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      switchView(tab.dataset.view);
    });
  });
}

function switchView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  $id(`view-${name}`)?.classList.add("active");

  if (name === "dashboard") loadDashboard();
  if (name === "report") populateCategorySelect();
  if (name === "admin") loadAdmin();
  if (name === "queue") loadQueue();
}

/* ---------- categories ---------- */
async function loadCategories() {
  try {
    CATEGORIES = await API.categories();
    populateCategorySelect();
  } catch { /* offline fallback */ }
}

function populateCategorySelect() {
  const sel = $id("rep-category");
  if (!sel || sel.options.length > 1) return;
  sel.innerHTML = `<option value="">Select category…</option>` +
    CATEGORIES.map((c) => `<option value="${c.slug}">${c.icon} ${esc(c.name)}</option>`).join("");
}

/* ---------- dashboard ---------- */
async function loadPublicStats() {
  try {
    const s = await API.publicStats();
    $id("stat-total").textContent = s.total_reported;
    $id("stat-resolved").textContent = s.resolved;
    $id("stat-rate").textContent = s.total_reported ? Math.round((s.resolved / s.total_reported) * 100) + "%" : "0%";
  } catch { /* keep dash */ }
}

async function loadDashboard() {
  loadPublicStats();
  const status = $id("filter-status").value;
  const mine = $id("filter-mine").checked;
  let list;
  try {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (mine && CURRENT_USER.role === "citizen") params.set("mine", "true");
    list = await API.complaints(params.toString() ? `?${params}` : "");
  } catch (err) { toast(err.message, "error"); return; }
  renderList($id("complaint-list"), list, "No complaints yet — report the first one!");
}

function renderList(el, complaints, emptyMsg) {
  if (!complaints.length) {
    el.innerHTML = `<div class="empty">${emptyMsg}</div>`;
    return;
  }
  el.innerHTML = complaints.map((c) => `
    <div class="complaint-card" data-id="${c.id}">
      <div class="cc-head">
        <span class="ticket">${esc(c.ticket)}</span>
        ${statusBadge(c.status)}
      </div>
      <div class="cc-title">${esc(c.title)}</div>
      <div class="cc-desc">${esc(c.description)}</div>
      <div class="cc-meta">
        <span class="badge badge-gray">${esc(c.category_name || "—")}</span>
        <span class="badge badge-gold">P${c.priority}</span>
        <span class="badge badge-gray">${esc(c.ward || "No ward")}</span>
        <span class="badge badge-gray">${fmtDate(c.created_at)}</span>
      </div>
    </div>`).join("");

  el.querySelectorAll(".complaint-card").forEach((card) => {
    card.addEventListener("click", () => openModal(Number(card.dataset.id)));
  });
}

$id("filter-status")?.addEventListener("change", loadDashboard);
$id("filter-mine")?.addEventListener("change", loadDashboard);

/* ---------- report ---------- */
function bindReport() {
  $id("report-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      title: $id("rep-title").value.trim(),
      description: $id("rep-desc").value.trim(),
      category_slug: $id("rep-category").value,
      ward: $id("rep-ward").value.trim() || null,
      severity: $id("rep-severity").value,
    };
    if (!payload.category_slug) { toast("Pick a category", "error"); return; }
    try {
      const c = await API.createComplaint(payload);
      toast(`Filed ${c.ticket} — status: ${c.status}`, "success");
      e.target.reset();
      switchView("dashboard");
    } catch (err) { toast(err.message, "error"); }
  });
}

/* ---------- admin ---------- */
async function loadAdmin() {
  try {
    const s = await API.adminStats();
    $id("adm-total").textContent = s.total;
    $id("adm-open").textContent = s.open;
    $id("adm-resolved").textContent = s.resolved;

    const officers = await API.officers();
    $id("officer-list").innerHTML = officers.map((o) =>
      `<span class="chip-item">👤 ${esc(o.name)} <small>· ${esc(o.ward || "—")}</small></span>`).join("") || `<div class="empty">No officers yet.</div>`;

    const list = await API.complaints("?status=submitted");
    renderList($id("admin-complaint-list"), list, "No pending complaints to verify. 🎉");
  } catch (err) { toast(err.message, "error"); }
}

/* ---------- officer queue ---------- */
async function loadQueue() {
  try {
    const list = await API.myQueue();
    renderList($id("queue-list"), list, "Your queue is empty — nice work! 🎉");
  } catch (err) { toast(err.message, "error"); }
}

/* ---------- modal ---------- */
let MODAL_COMPLAINT = null;

function bindModal() {
  $id("modal-close").addEventListener("click", closeModal);
  $id("modal").addEventListener("click", (e) => { if (e.target === $id("modal")) closeModal(); });

  $id("comment-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = $id("comment-body").value.trim();
    if (!body || !MODAL_COMPLAINT) return;
    try {
      await API.comment(MODAL_COMPLAINT.id, body);
      $id("comment-body").value = "";
      openModal(MODAL_COMPLAINT.id);
    } catch (err) { toast(err.message, "error"); }
  });
}

async function openModal(id) {
  try {
    MODAL_COMPLAINT = await API.complaint(id);
  } catch (err) { toast(err.message, "error"); return; }
  const c = MODAL_COMPLAINT;

  $id("modal-ticket").textContent = c.ticket;
  $id("modal-title").textContent = c.title;
  $id("modal-status").outerHTML = `<span id="modal-status" class="badge ${statusClass(c.status)}">${statusLabel(c.status)}</span>`;
  $id("modal-priority").textContent = `Priority ${c.priority}/20`;
  $id("modal-desc").textContent = c.description;

  $id("modal-meta").innerHTML = `
    <div>Category <b>${esc(c.category_name || "—")}</b></div>
    <div>Severity <b>${esc(c.severity)}</b></div>
    <div>Ward <b>${esc(c.ward || "—")}</b></div>
    <div>Area <b>${esc(c.area || "—")}</b></div>
    <div>Reporter <b>${esc(c.reporter_name || "—")}</b></div>
    <div>Assignee <b>${esc(c.assignee_name || "Unassigned")}</b></div>
    <div>Reported <b>${fmtDate(c.created_at)}</b></div>
    <div>Updated <b>${fmtDate(c.updated_at)}</b></div>`;

  renderActions(c);
  renderHistory(c);
  renderComments(c);

  $id("modal").classList.remove("hidden");
}

function closeModal() {
  $id("modal").classList.add("hidden");
  MODAL_COMPLAINT = null;
}

function statusLabel(s) {
  return { submitted: "Submitted", verified: "Verified", in_progress: "In Progress", resolved: "Resolved", rejected: "Rejected", reopened: "Reopened" }[s] || s;
}
function statusClass(s) {
  return { submitted: "badge-blue", verified: "badge-gold", in_progress: "badge-gold", resolved: "badge-green", rejected: "badge-red", reopened: "badge-red" }[s] || "badge-gray";
}

async function doTransition(to_status, note = "") {
  try {
    const updated = await API.transition(MODAL_COMPLAINT.id, { to_status, note });
    toast(`→ ${statusLabel(updated.status)}`, "success");
    openModal(updated.id);
    loadDashboard();
  } catch (err) { toast(err.message, "error"); }
}

function renderActions(c) {
  const box = $id("modal-actions");
  const role = CURRENT_USER.role;
  const buttons = [];

  if (role === "admin") {
    if (c.status === "submitted") {
      buttons.push({ label: "✅ Verify", cls: "btn-success", fn: () => doTransition("verified", "Verified by admin") });
      buttons.push({ label: "❌ Reject", cls: "btn-danger", fn: () => promptReject() });
    }
    if (c.status === "verified" || c.status === "reopened") {
      buttons.push({ label: "👷 Assign officer", cls: "btn-primary", fn: () => promptAssign() });
    }
    if (c.status === "in_progress") {
      buttons.push({ label: "❌ Reject", cls: "btn-danger", fn: () => promptReject() });
    }
  }

  if (role === "officer" && (c.status === "in_progress" || c.status === "reopened") && c.assignee_id === CURRENT_USER.id) {
    buttons.push({ label: "✅ Mark resolved", cls: "btn-success", fn: () => promptResolve() });
  }

  if (role === "citizen" && c.reporter_id === CURRENT_USER.id && c.status === "resolved") {
    buttons.push({ label: "↩️ Reopen (not fixed!)", cls: "btn-danger", fn: () => promptReopen() });
  }

  box.innerHTML = buttons.map((b) => `<button class="btn ${b.cls}">${b.label}</button>`).join("");
  box.querySelectorAll("button").forEach((btn, i) => btn.addEventListener("click", buttons[i].fn));
}

function promptReject() {
  const note = prompt("Reject reason (optional):") || "Rejected";
  doTransition("rejected", note);
}
function promptResolve() {
  const note = prompt("Resolution note (what was done?):") || "Issue addressed";
  doTransition("resolved", note);
}
function promptReopen() {
  if (confirm("The complaint is resolved — reopen it if the issue is still there?")) doTransition("reopened", "Reporter says issue is not fixed");
}
async function promptAssign() {
  try {
    const officers = await API.officers();
    if (!officers.length) { toast("No officers registered yet", "error"); return; }
    const opts = officers.map((o, i) => `${i + 1}. ${o.name} (${o.ward || "no ward"})`).join("\n");
    const choice = prompt(`Pick an officer:\n${opts}`);
    const idx = parseInt(choice, 10);
    if (!idx || idx < 1 || idx > officers.length) return;
    await API.assign(MODAL_COMPLAINT.id, { officer_id: officers[idx - 1].id });
    toast("Assigned 👷", "success");
    openModal(MODAL_COMPLAINT.id);
  } catch (err) { toast(err.message, "error"); }
}

function renderHistory(c) {
  $id("modal-history").innerHTML = c.history.map((h) => `
    <div class="tl-item">
      <div class="tl-dot"></div>
      <div class="tl-body">
        <b>${esc(statusLabel(h.to_status))}</b>
        <small>${esc(h.actor_name || "System")} · ${fmtDate(h.created_at)}</small>
        ${h.note ? `<p class="muted" style="margin-top:3px">${esc(h.note)}</p>` : ""}
      </div>
    </div>`).join("") || `<div class="empty">No activity yet.</div>`;
}

function renderComments(c) {
  $id("modal-comments").innerHTML = c.comments.map((cm) => `
    <div class="comment"><small>💬 ${esc(cm.author_name || "User")} · ${fmtDate(cm.created_at)}</small>${esc(cm.body)}</div>`).join("") ||
    `<div class="empty">No comments yet.</div>`;
}

document.addEventListener("DOMContentLoaded", boot);
