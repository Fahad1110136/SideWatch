import { h, field, alertBox, setFieldError } from "../ui.js";
import { traceGlyph } from "../charts.js";

export function loginPage({ onLogin, message }) {
  const user = h("input", { id: "u", autocomplete: "username", maxlength: 32, autofocus: true, spellcheck: "false" });
  const pass = h("input", { id: "p", type: "password", autocomplete: "current-password", maxlength: 128 });
  const msg = h("div", { "aria-live": "assertive" }, message ? h("div", { class: "alert info" }, message) : null);
  const btn = h("button", { class: "btn btn-primary btn-block", type: "submit" }, "Sign in");

  const form = h("form", { novalidate: true, onsubmit: async (e) => {
    e.preventDefault();
    msg.replaceChildren(); setFieldError("u"); setFieldError("p");
    const u = user.value.trim();
    if (!u) { setFieldError("u", "Enter your username."); user.focus(); return; }
    if (!pass.value) { setFieldError("p", "Enter your password."); pass.focus(); return; }
    btn.disabled = true; btn.textContent = "Signing in…";
    try { await onLogin(u, pass.value); }
    catch (ex) { msg.replaceChildren(alertBox(ex)); pass.value = ""; pass.focus(); }
    finally { btn.disabled = false; btn.textContent = "Sign in"; }
  } }, msg, field("u", "Username", user), field("p", "Password", pass), btn);

  return h("div", { class: "login" },
    h("section", { class: "login-intro" },
      h("div", { class: "login-glyph" }, traceGlyph(0.2, "clean"), traceGlyph(1.8, "leak")),
      h("h1", {}, "Can a stopwatch recover a secret?"),
      h("p", {}, "SideWatch measures how long a comparison takes when a guess is partly right, and tests whether that timing gives the secret away."),
      h("p", { class: "fine" }, "A local teaching lab. It measures simulated comparisons on this machine only; it is not a scanner for real systems.")),
    h("section", { class: "login-card", "aria-label": "Sign in" }, h("h2", {}, "Sign in"), form,
      h("p", { class: "fine" }, "Accounts are created by an administrator.")));
}
