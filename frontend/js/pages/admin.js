import { api } from "../api.js";
import { h, pageHead, field, setFieldError, alertBox, badge, toast, errorText, modal, confirmDialog, fmtDate, shortId, empty, spinner } from "../ui.js";
import { RULE_INFO, RULE_BOUNDS, ROLES } from "../config.js";

const strongPassword = (p) => p.length >= 12 && p.length <= 128 && /[A-Za-z]/.test(p) && /\d/.test(p);
const PW_HINT = "At least 12 characters, with letters and digits.";

// ---------------------------------------------------------------- detection rules
export async function rulesPage({ user }) {
  const rules = await api.rules();
  const admin = user.role === "admin";
  const page = h("div", { "data-title": "Rules" },
    pageHead("Detection rules", admin ? "These thresholds decide every verdict. Each change is confirmed, versioned and written to the audit log."
                                       : "These thresholds decide every verdict. Only administrators can change them."));
  const list = h("div", { class: "rules" });
  for (const rule of rules) {
    const info = RULE_INFO[rule.key] || { label: rule.key, help: "", step: "any" };
    const [lo, hi] = RULE_BOUNDS[rule.key] || [];
    const input = h("input", { id: "r-" + rule.key, type: "number", step: info.step, min: lo, max: hi, value: rule.value, disabled: !admin });
    const meta = h("p", { class: "muted small" });
    const showMeta = (r) => { meta.textContent = `Version ${r.version} · updated ${fmtDate(r.updated_at)}${lo !== undefined ? ` · allowed ${lo} to ${hi}` : ""}`; };
    showMeta(rule);
    const save = h("button", { class: "btn btn-primary", type: "button" }, "Save change");
    save.addEventListener("click", async () => {
      setFieldError("r-" + rule.key);
      const v = Number(input.value);
      if (input.value === "" || !Number.isFinite(v) || v < lo || v > hi) { setFieldError("r-" + rule.key, `Enter a number from ${lo} to ${hi}.`); return; }
      if (v === rule.value) { setFieldError("r-" + rule.key, "That is already the current value."); return; }
      const ok = await confirmDialog("Change this rule?", `${info.label} will change from ${rule.value} to ${v}. Every measurement from now on is judged with the new value. Past results keep the value they used.`, "Apply change", true);
      if (!ok) return;
      save.disabled = true;
      try { const nr = await api.updateRule(rule.key, v); rule.value = nr.value; rule.version = nr.version; input.value = nr.value; showMeta(nr); toast(`${info.label} updated to ${nr.value}`); }
      catch (ex) { setFieldError("r-" + rule.key, errorText(ex)); }
      finally { save.disabled = false; }
    });
    list.append(h("section", { class: "panel rule" }, h("h2", {}, info.label), h("p", {}, info.help),
      field("r-" + rule.key, "Value", input), meta, admin ? save : null));
  }
  page.append(list);
  return page;
}

// ---------------------------------------------------------------- users
export async function usersPage({ user }) {
  const page = h("div", { "data-title": "Users" }, pageHead("Users", "Create accounts and control who can sign in."));
  const tbody = h("tbody");
  const msg = h("div", { "aria-live": "assertive" });

  async function reload() {
    try {
      const users = await api.users();
      tbody.replaceChildren(...users.map((u) => {
        const self = u.id === user.id;
        const toggle = h("button", { class: "btn btn-quiet", type: "button", disabled: self, title: self ? "You cannot deactivate yourself" : "" }, u.is_active ? "Deactivate" : "Activate");
        toggle.addEventListener("click", async () => {
          if (u.is_active && !(await confirmDialog("Deactivate this account?", `${u.username} will be signed out and cannot sign in until you activate the account again.`, "Deactivate", true))) return;
          try { await api.setUserActive(u.id, !u.is_active); toast(`${u.username} ${u.is_active ? "deactivated" : "activated"}`); reload(); } catch (ex) { toast(errorText(ex), "err"); }
        });
        const reset = h("button", { class: "btn btn-quiet", type: "button", disabled: self, title: self ? "Use Account to change your own password" : "" }, "Reset password");
        reset.addEventListener("click", async () => {
          const pw = h("input", { type: "password", autocomplete: "new-password", id: "reset-pw", maxlength: 128 });
          const ok = await modal({ title: `Reset password for ${u.username}?`, okLabel: "Reset password", danger: true,
            content: h("div", {}, h("p", {}, "They will be signed out everywhere and any lockout is cleared."), field("reset-pw", "New password", pw, PW_HINT)),
            validate: () => (strongPassword(pw.value) ? null : PW_HINT) });
          if (!ok) return;
          try { await api.resetPassword(u.id, pw.value); toast(`Password reset for ${u.username}`); } catch (ex) { toast(errorText(ex), "err"); }
        });
        return h("tr", {}, h("td", {}, u.username, self ? h("span", { class: "muted" }, " (you)") : null), h("td", {}, badge(u.role, "role")),
          h("td", {}, badge(u.is_active ? "Active" : "Inactive", u.is_active ? "clean" : "unsure")), h("td", { class: "actions" }, toggle, reset));
      }));
    } catch (ex) { tbody.replaceChildren(h("tr", {}, h("td", { colspan: 4 }, alertBox(ex)))); }
  }

  const name = h("input", { id: "nu", autocomplete: "off", maxlength: 32, spellcheck: "false" });
  const pass = h("input", { id: "np", type: "password", autocomplete: "new-password", maxlength: 128 });
  const role = h("select", { id: "nr" }, ROLES.map((r) => h("option", { value: r }, r)));
  role.value = "operator";
  const create = h("form", { class: "form-grid", novalidate: true, onsubmit: async (e) => {
    e.preventDefault(); msg.replaceChildren(); ["nu", "np"].forEach((i) => setFieldError(i));
    const un = name.value.trim();
    let bad = false;
    if (!/^[a-zA-Z0-9_.-]{3,32}$/.test(un)) { setFieldError("nu", "3 to 32 characters: letters, digits, . _ -"); bad = true; }
    if (!strongPassword(pass.value)) { setFieldError("np", PW_HINT); bad = true; }
    if (bad) return;
    try { await api.createUser(un, pass.value, role.value); toast(`Created ${un}`); name.value = ""; pass.value = ""; reload(); }
    catch (ex) { msg.replaceChildren(alertBox(ex)); }
  } }, field("nu", "Username", name), field("np", "Temporary password", pass, PW_HINT), field("nr", "Role", role),
    h("div", { class: "field end" }, h("button", { class: "btn btn-primary", type: "submit" }, "Create account")));

  page.append(h("section", { class: "panel" }, h("h2", {}, "Accounts"), h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, ["Username", "Role", "Status", ""].map((t) => h("th", { scope: "col" }, t)))), tbody))),
    h("section", { class: "panel" }, h("h2", {}, "New account"), msg, create,
      h("p", { class: "muted small" }, "Administrators run the lab and manage rules and users. Operators run and review their own measurements. Viewers can only read completed results.")));
  await reload();
  return page;
}

// ---------------------------------------------------------------- audit log
export async function auditPage() {
  const PAGE = 50;
  const q = { action: "", outcome: "", offset: 0 };
  let names = {};
  try { (await api.users()).forEach((u) => { names[u.id] = u.username; }); } catch { /* ids are shown instead */ }
  const body = h("div", { "aria-live": "polite" });
  const pager = h("div", { class: "pager" });
  const verifyOut = h("div", { "aria-live": "polite" });
  const verify = h("button", { class: "btn", type: "button" }, "Verify log integrity");
  verify.addEventListener("click", async () => {
    verify.disabled = true; verifyOut.replaceChildren();
    try {
      const v = await api.verifyAudit();
      verifyOut.replaceChildren(h("div", { class: `callout ${v.intact ? "tone-clean" : "tone-leak"}`, role: "status" },
        v.intact ? `The hash chain is intact across ${v.events_checked} events. No entry has been altered or removed.`
                 : `The chain breaks at event ${v.first_bad_event_id}. The log has been altered or damaged.`));
    } catch (ex) { verifyOut.replaceChildren(alertBox(ex)); }
    finally { verify.disabled = false; }
  });
  const action = h("input", { id: "a-action", maxlength: 48, placeholder: "for example auth.login" });
  const outcome = h("select", { id: "a-out" }, [h("option", { value: "" }, "All"), ...["success", "failure", "denied"].map((o) => h("option", { value: o }, o))]);
  const apply = () => { q.action = action.value.trim(); q.outcome = outcome.value; q.offset = 0; load(); };
  action.addEventListener("change", apply); outcome.addEventListener("change", apply);

  async function load() {
    body.replaceChildren(spinner());
    try {
      const ev = await api.audit({ action: q.action, outcome: q.outcome, limit: PAGE + 1, offset: q.offset });
      const more = ev.length > PAGE, rows = ev.slice(0, PAGE);
      body.replaceChildren(rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "audit" },
        h("caption", { class: "sr-only" }, "Audit events, newest first"),
        h("thead", {}, h("tr", {}, ["#", "When", "Who", "Action", "Outcome", "Resource", "Details"].map((t) => h("th", { scope: "col" }, t)))),
        h("tbody", {}, rows.map((e) => h("tr", {},
          h("td", { class: "num" }, e.id), h("td", { class: "nowrap" }, fmtDate(e.timestamp)),
          h("td", {}, e.actor_id ? `${names[e.actor_id] || shortId(e.actor_id)}${e.actor_role ? " (" + e.actor_role + ")" : ""}` : "anonymous"),
          h("td", { class: "mono-cell" }, e.action), h("td", {}, badge(e.outcome, e.outcome === "success" ? "clean" : e.outcome === "denied" ? "leak" : "unsure")),
          h("td", { class: "mono-cell" }, e.resource_type ? `${e.resource_type} ${shortId(e.resource_id || "")}` : "–"),
          h("td", {}, Object.keys(e.details || {}).length ? h("details", {}, h("summary", {}, "view"), h("pre", {}, JSON.stringify(e.details, null, 2))) : "–")))))) : empty("No events match", "Clear the filters to see everything."));
      pager.replaceChildren(
        h("button", { class: "btn btn-quiet", type: "button", disabled: q.offset === 0, onclick: () => { q.offset = Math.max(0, q.offset - PAGE); load(); } }, "Newer"),
        h("span", { class: "muted" }, rows.length ? `Showing ${q.offset + 1} to ${q.offset + rows.length}` : ""),
        h("button", { class: "btn btn-quiet", type: "button", disabled: !more, onclick: () => { q.offset += PAGE; load(); } }, "Older"));
    } catch (ex) { body.replaceChildren(alertBox(ex)); }
  }
  const page = h("div", { "data-title": "Audit log" },
    pageHead("Audit log", "An append-only, hash-chained record of sign-ins, measurements, rule changes, exports and denied requests.", verify),
    verifyOut,
    h("div", { class: "panel filters" }, field("a-action", "Action contains exact name", action), field("a-out", "Outcome", outcome)),
    h("div", { class: "panel" }, body, pager));
  await load();
  return page;
}

// ---------------------------------------------------------------- my account
export async function accountPage({ user }) {
  const cur = h("input", { id: "pw-cur", type: "password", autocomplete: "current-password", maxlength: 128 });
  const nw = h("input", { id: "pw-new", type: "password", autocomplete: "new-password", maxlength: 128 });
  const rep = h("input", { id: "pw-rep", type: "password", autocomplete: "new-password", maxlength: 128 });
  const msg = h("div", { "aria-live": "assertive" });
  const btn = h("button", { class: "btn btn-primary", type: "submit" }, "Change password");
  const form = h("form", { novalidate: true, onsubmit: async (e) => {
    e.preventDefault(); msg.replaceChildren(); ["pw-cur", "pw-new", "pw-rep"].forEach((i) => setFieldError(i));
    let bad = false;
    if (!cur.value) { setFieldError("pw-cur", "Enter your current password."); bad = true; }
    if (!strongPassword(nw.value)) { setFieldError("pw-new", PW_HINT); bad = true; }
    if (nw.value !== rep.value) { setFieldError("pw-rep", "The two passwords do not match."); bad = true; }
    if (bad) return;
    btn.disabled = true;
    try { await api.changePassword(cur.value, nw.value); cur.value = nw.value = rep.value = ""; toast("Password changed. Other sessions were signed out."); }
    catch (ex) { msg.replaceChildren(alertBox(ex)); }
    finally { btn.disabled = false; }
  } }, msg, field("pw-cur", "Current password", cur), field("pw-new", "New password", nw, PW_HINT), field("pw-rep", "Repeat new password", rep), btn);
  return h("div", { "data-title": "Account" }, pageHead("Your account", `${user.username} · ${user.role}`), h("section", { class: "panel narrow" }, h("h2", {}, "Change password"), form));
}
