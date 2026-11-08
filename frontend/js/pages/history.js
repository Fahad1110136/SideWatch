import { api } from "../api.js";
import { h, pageHead, badge, fmt, fmtNs, fmtDate, alertBox, empty, toast, spinner } from "../ui.js";
import { withResults } from "../data.js";
import { DECISIONS, IMPLEMENTATIONS, FIXTURES } from "../config.js";

const PAGE = 20;

export async function historyPage({ user, navigate }) {
  const q = { status: "", implementation: "", offset: 0 };
  const selected = new Set();
  let search = "";
  const body = h("div", { "aria-live": "polite" });
  const cmp = h("button", { class: "btn btn-primary", type: "button", disabled: true }, "Compare selected");
  cmp.addEventListener("click", () => { const [a, b] = [...selected]; navigate(`compare/${a}/${b}`); });
  const pager = h("div", { class: "pager" });
  let rowsNow = [];

  const select = (id, label, opts, key) => h("div", { class: "field" }, h("label", { for: id }, label),
    h("select", { id, onchange: (e) => { q[key] = e.target.value; q.offset = 0; selected.clear(); load(); } },
      h("option", { value: "" }, "All"), opts.map(([v, l]) => h("option", { value: v }, l))));
  const searchBox = h("input", { id: "f-search", type: "search", placeholder: "Search labels", "aria-label": "Search labels on this page" });
  searchBox.addEventListener("input", () => { search = searchBox.value.trim().toLowerCase(); draw(); });
  const sync = () => { cmp.disabled = selected.size !== 2; cmp.textContent = `Compare selected (${selected.size}/2)`; };

  function draw() {
    const rows = rowsNow.filter(({ sub }) => !search || sub.label.toLowerCase().includes(search));
    if (!rows.length) { body.replaceChildren(empty(rowsNow.length ? "No labels match" : "No measurements found", rowsNow.length ? "Try a different search." : "Run a measurement, or clear the filters.")); return; }
    body.replaceChildren(h("div", { class: "table-wrap" }, h("table", { class: "hist" },
      h("caption", { class: "sr-only" }, "Measurement history"),
      h("thead", {}, h("tr", {}, ["", "Run", "When", "Implementation", "Guess", "Samples", "Decision", "Difference", "Effect"].map((t) => h("th", { scope: "col" }, t)))),
      h("tbody", {}, rows.map(({ sub, result: r }) => {
        const d = r && DECISIONS[r.decision];
        const box = h("input", { type: "checkbox", class: "check", "aria-label": `Select ${sub.label} to compare`, checked: selected.has(sub.id) });
        box.addEventListener("change", () => {
          if (box.checked && selected.size >= 2) { box.checked = false; toast("Pick only two runs to compare.", "err"); return; }
          box.checked ? selected.add(sub.id) : selected.delete(sub.id); sync();
        });
        return h("tr", {},
          h("td", {}, sub.status === "completed" ? box : null),
          h("td", {}, h("a", { href: `#/results/${sub.id}` }, sub.label)),
          h("td", { class: "nowrap" }, fmtDate(sub.created_at)),
          h("td", {}, IMPLEMENTATIONS[sub.implementation]?.label ?? sub.implementation),
          h("td", {}, FIXTURES[sub.fixture_id]?.label ?? sub.fixture_id),
          h("td", { class: "num" }, sub.sample_size),
          h("td", {}, d ? badge(d.short, d.tone) : badge(sub.status === "failed" ? `Failed (${sub.error_code || "error"})` : sub.status, "unsure")),
          h("td", { class: "num" }, r ? fmtNs(r.evidence.mean_difference_ns) : "–"),
          h("td", { class: "num" }, r ? fmt(r.effect_size, 2) : "–"));
      })))));
  }

  async function load() {
    body.replaceChildren(spinner());
    sync();
    try {
      const subs = await api.listSubmissions({ status: q.status, implementation: q.implementation, limit: PAGE + 1, offset: q.offset });
      const more = subs.length > PAGE;
      rowsNow = await withResults(subs.slice(0, PAGE));
      draw();
      pager.replaceChildren(
        h("button", { class: "btn btn-quiet", type: "button", disabled: q.offset === 0, onclick: () => { q.offset = Math.max(0, q.offset - PAGE); load(); } }, "Newer"),
        h("span", { class: "muted" }, rowsNow.length ? `Showing ${q.offset + 1} to ${q.offset + rowsNow.length}` : ""),
        h("button", { class: "btn btn-quiet", type: "button", disabled: !more, onclick: () => { q.offset += PAGE; load(); } }, "Older"));
    } catch (ex) { body.replaceChildren(alertBox(ex)); }
  }

  const page = h("div", { "data-title": "History" },
    pageHead("History", user.role === "operator" ? "Your measurements. Pick two to compare them." : user.role === "viewer" ? "Completed measurements. Pick two to compare them." : "Every measurement. Pick two to compare them.", cmp),
    h("div", { class: "panel filters" },
      select("f-impl", "Implementation", Object.entries(IMPLEMENTATIONS).map(([v, i]) => [v, i.label]), "implementation"),
      select("f-status", "Status", [["completed", "Completed"], ["failed", "Failed"]], "status"),
      h("div", { class: "field" }, h("label", { for: "f-search" }, "Search"), searchBox)),
    h("div", { class: "panel" }, body, pager));
  await load();
  return page;
}
