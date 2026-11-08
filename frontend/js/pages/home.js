import { api } from "../api.js";
import { h, pageHead, stat, badge, fmtDate, fmtNs, fmtSigned, empty } from "../ui.js";
import { withResults } from "../data.js";
import { DECISIONS, IMPLEMENTATIONS, FIXTURES, PRESETS } from "../config.js";
import { traceGlyph } from "../charts.js";

export async function homePage({ user }) {
  const canRun = user.role !== "viewer";
  const subs = await api.listSubmissions({ limit: 20 });
  const rows = await withResults(subs);
  const done = rows.filter((r) => r.result);
  const count = (d) => done.filter((r) => r.result.decision === d).length;
  const failed = rows.filter((r) => r.sub.status === "failed").length;

  const root = h("div", { "data-title": "Overview" });
  root.append(pageHead(`Welcome, ${user.username}`,
    user.role === "viewer" ? "You can review completed measurements." : "Run a measurement, then read the evidence behind the verdict.",
    canRun ? h("a", { class: "btn btn-primary", href: "#/run" }, "New measurement") : null));

  root.append(h("dl", { class: "stats" },
    stat("Recent runs", rows.length, "latest 20 you can see"),
    stat("Leaks detected", count("leak_detected"), null, count("leak_detected") ? "leak" : null),
    stat("No leak detected", count("no_leak_detected"), null, count("no_leak_detected") ? "clean" : null),
    stat("Inconclusive or failed", count("inconclusive") + failed)));

  if (canRun) {
    root.append(h("section", { class: "block" }, h("h2", {}, "Start from an example"),
      h("div", { class: "presets" }, Object.entries(PRESETS).map(([key, p]) =>
        h("a", { class: "preset", href: `#/run/${key}` }, h("strong", {}, p.title), h("span", {}, p.text))))));
  }

  const latest = h("section", { class: "block" }, h("h2", {}, "Latest results"));
  if (!rows.length) {
    latest.append(empty("No measurements yet", canRun ? "Run your first measurement to see how timing can leak a secret." : "Nothing has been completed yet.",
      canRun ? h("a", { class: "btn btn-primary", href: "#/run" }, "New measurement") : null));
  } else {
    latest.append(h("div", { class: "list" }, rows.slice(0, 6).map(({ sub, result }) => {
      const d = result && DECISIONS[result.decision];
      return h("a", { class: `row-card tone-${d ? d.tone : "unsure"}`, href: `#/results/${sub.id}` },
        result ? traceGlyph(result.effect_size, d.tone) : h("span", { class: "glyph-ph" }),
        h("div", { class: "row-main" }, h("strong", {}, sub.label),
          h("span", { class: "muted" }, `${IMPLEMENTATIONS[sub.implementation]?.label ?? sub.implementation} · ${FIXTURES[sub.fixture_id]?.label ?? sub.fixture_id} · ${sub.sample_size} samples`)),
        h("div", { class: "row-end" },
          d ? badge(d.short, d.tone) : badge(sub.status === "failed" ? "Failed" : sub.status, "unsure"),
          result ? h("span", { class: "muted num" }, `${fmtSigned(result.evidence.mean_difference_ns)} ns`) : null,
          h("span", { class: "muted" }, fmtDate(sub.created_at))));
    })));
    latest.append(h("p", {}, h("a", { href: "#/history" }, "See all history")));
  }
  root.append(latest);

  root.append(h("section", { class: "block note" }, h("h2", {}, "Reading a result"),
    h("p", {}, "Each run times a guess against a control that is wrong from the very first byte. If the guess takes measurably longer, the comparison is giving away how much of it was right. The verdict combines a significance test, a confidence interval and an effect size, so one lucky number cannot decide it."),
    h("p", { class: "muted" }, "This is a local microbenchmark. It can show a leak, but it can never prove a comparison is constant-time.")));
  return root;
}
