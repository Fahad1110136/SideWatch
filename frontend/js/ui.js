// DOM helpers. All dynamic text goes through createTextNode (never raw HTML), so anything
// the server returns - labels, audit details, reasons - can never inject markup.
const SVG_NS = "http://www.w3.org/2000/svg";

function apply(el, props) {
  for (const [k, v] of Object.entries(props || {})) {
    if (v === false || v == null) continue;
    if (k === "class") el.setAttribute("class", v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, String(v));
  }
}
function append(el, kids) {
  for (const c of kids.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}
export function h(tag, props, ...kids) { const el = document.createElement(tag); apply(el, props); append(el, kids); return el; }
export function hs(tag, props, ...kids) { const el = document.createElementNS(SVG_NS, tag); apply(el, props); append(el, kids); return el; }

// ---------- formatting
const num = (x) => (x == null || Number.isNaN(Number(x)) ? null : Number(x));
export function fmt(x, d = 2) { const n = num(x); return n === null ? "–" : n.toFixed(d); }
export function fmtNs(x, d = 1) { const n = num(x); return n === null ? "–" : `${n.toFixed(d)} ns`; }
export function fmtSigned(x, d = 1) { const n = num(x); return n === null ? "–" : `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(d)}`; }
export function fmtP(p) {
  const n = num(p);
  if (n === null) return "–";
  if (n === 0) return "< 1e-300";
  return n < 0.001 ? n.toExponential(1).replace("e-", "e−") : n.toFixed(4);
}
// The API sends UTC timestamps without a zone suffix; treat them as UTC.
export function fmtDate(iso) {
  if (!iso) return "–";
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
export const shortId = (id) => String(id).slice(0, 8);

// ---------- feedback
export function toast(msg, kind = "ok") {
  const box = document.getElementById("toasts");
  const t = h("div", { class: `toast ${kind}` }, msg);
  box.append(t);
  setTimeout(() => t.remove(), kind === "err" ? 6000 : 3200);
}
export function errorText(err) {
  const base = err?.message || "Something went wrong.";
  return err?.requestId ? `${base} (ref ${err.requestId})` : base;
}
export const alertBox = (err) => h("div", { class: "alert", role: "alert" }, typeof err === "string" ? err : errorText(err));

/** Modal dialog. `content` is a Node. `validate()` may return an error string to keep it open. */
export function modal({ title, content, okLabel = "Confirm", danger = false, validate }) {
  return new Promise((resolve) => {
    const err = h("div", { class: "field-error", "aria-live": "assertive" });
    const ok = h("button", { type: "button", class: `btn ${danger ? "btn-danger" : "btn-primary"}` }, okLabel);
    const cancel = h("button", { type: "button", class: "btn btn-quiet" }, "Cancel");
    const dlg = h("dialog", { "aria-labelledby": "dlg-title" },
      h("div", { class: "dlg" }, h("h2", { id: "dlg-title" }, title), content, err, h("div", { class: "dlg-actions" }, cancel, ok)));
    const done = (v) => { dlg.close(); dlg.remove(); resolve(v); };
    cancel.addEventListener("click", () => done(false));
    dlg.addEventListener("cancel", (e) => { e.preventDefault(); done(false); });
    ok.addEventListener("click", () => {
      const msg = validate ? validate() : null;
      if (msg) { err.textContent = msg; return; }
      done(true);
    });
    document.body.append(dlg);
    dlg.showModal();
    (dlg.querySelector("input,select") || cancel).focus();
  });
}
export const confirmDialog = (title, text, okLabel, danger) =>
  modal({ title, content: h("p", {}, text), okLabel, danger });

export function downloadBlob(filename, blob) {
  const a = h("a", { href: URL.createObjectURL(blob), download: filename });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1500);
}

// ---------- small components
export function pageHead(title, sub, ...actions) {
  return h("header", { class: "page-head" },
    h("div", {}, h("h1", {}, title), sub ? h("p", { class: "sub" }, sub) : null),
    actions.length ? h("div", { class: "head-actions" }, actions) : null);
}
export function field(id, label, input, hint) {
  return h("div", { class: "field" },
    h("label", { for: id }, label),
    input,
    hint ? h("div", { class: "hint", id: id + "-hint" }, hint) : null,
    h("div", { class: "field-error", id: id + "-err", "aria-live": "polite" }));
}
export const setFieldError = (id, msg) => { const e = document.getElementById(id + "-err"); if (e) e.textContent = msg || ""; };
export const badge = (text, tone) => h("span", { class: `badge tone-${tone}` }, text);
export const spinner = (text = "Loading…") => h("p", { class: "loading", role: "status" }, h("span", { class: "dots", "aria-hidden": "true" }), text);
export const empty = (title, text, action) => h("div", { class: "empty" }, h("h3", {}, title), text ? h("p", {}, text) : null, action || null);
export function stat(label, value, sub, tone) {
  return h("div", { class: `stat${tone ? " tone-" + tone : ""}` }, h("dt", {}, label), h("dd", {}, value), sub ? h("div", { class: "stat-sub" }, sub) : null);
}
