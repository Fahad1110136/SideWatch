import { api } from "../api.js";
import { h, pageHead, stat, badge, fmt, fmtNs, fmtSigned, fmtP, fmtDate, shortId, toast, errorText, downloadBlob, alertBox, empty } from "../ui.js";
import { DECISIONS, IMPLEMENTATIONS, FIXTURES } from "../config.js";
import { ruleChecks } from "../data.js";
import { distribution, ciPlot, sweepChart, traceGlyph } from "../charts.js";

const impl = (id) => IMPLEMENTATIONS[id]?.label ?? id;
const fixture = (id) => FIXTURES[id]?.label ?? id;
const SEVERITY_TONE = { info: "clean", low: "unsure", medium: "unsure", high: "leak" };

async function load(id) {
  const [sub, result] = await Promise.all([
    api.getSubmission(id),
    api.getResult(id).catch((e) => (e.status === 404 ? null : Promise.reject(e))),
  ]);
  return { sub, result };
}

function sentence(sub, r) {
  const ev = r.evidence, d = ev.mean_difference_ns;
  const level = `${Math.round(r.thresholds.ci_level * 100)}% interval ${fmt(r.ci_low, 1)} to ${fmt(r.ci_high, 1)} ns`;
  const what = (FIXTURES[sub.fixture_id]?.label || sub.fixture_id).toLowerCase();
  if (r.decision === "leak_detected") return `The "${what}" guess took ${fmtNs(Math.abs(d))} ${d >= 0 ? "longer" : "shorter"} than the control (${level}). That gap is large and consistent enough to count as a timing leak.`;
  if (r.decision === "no_leak_detected") return `The "${what}" guess differed from the control by ${fmtSigned(d)} ns (${level}), which is within noise at these settings. That does not prove the comparison is constant-time.`;
  return `The measured gap of ${fmtSigned(d)} ns (${level}) cannot yet be separated from noise. Collect more samples or reduce jitter, then run it again.`;
}

async function exportReport(id, btn) {
  btn.disabled = true;
  try {
    const { filename, blob } = await api.downloadReport(id);
    let digest = "";
    try { digest = JSON.parse(await blob.text()).integrity.report_digest.slice(0, 12); } catch { /* digest is a bonus */ }
    downloadBlob(filename, blob);
    toast(digest ? `Report saved. Integrity digest ${digest}…, recorded in the audit log.` : "Report saved.");
  } catch (ex) { toast(errorText(ex), "err"); }
  finally { btn.disabled = false; }
}

export async function resultPage({ args, user, navigate }) {
  const { sub, result: r } = await load(args[0]);
  const page = h("div", { "data-title": sub.label });
  const exportBtn = h("button", { class: "btn", type: "button" }, "Export report");
  exportBtn.addEventListener("click", () => exportReport(sub.id, exportBtn));
  const again = user.role === "viewer" ? null : h("a", { class: "btn btn-quiet", href: `#/run/from-${sub.id}` }, "Run again");
  page.append(pageHead(sub.label, `${impl(sub.implementation)} · ${fixture(sub.fixture_id)} · ${fmtDate(sub.created_at)}`, again, r ? exportBtn : null));

  if (!r) {
    page.append(empty(sub.status === "failed" ? "This measurement failed" : "No result yet",
      sub.status === "failed" ? `The engine could not finish it (${sub.error_code || "ENGINE_FAILED"}). Nothing was stored except this record.` : "The result is not ready."));
    return page;
  }
  const d = DECISIONS[r.decision], ev = r.evidence;

  page.append(h("section", { class: `verdict tone-${d.tone}`, "aria-labelledby": "verdict-h" },
    h("div", { class: "verdict-glyph" }, traceGlyph(r.effect_size, d.tone)),
    h("div", { class: "verdict-body" },
      h("p", { class: "verdict-meta" }, badge(`Severity: ${r.severity}`, SEVERITY_TONE[r.severity] || "unsure"), badge(impl(sub.implementation), "plain")),
      h("h2", { id: "verdict-h" }, d.label),
      h("p", { class: "verdict-text" }, sentence(sub, r)))));

  page.append(h("section", { class: "panel" }, h("h2", {}, "How the two timings compare"),
    h("p", { class: "muted" }, `${ev.comparison}. Each sample is the average of ${ev.timed_calls_per_sample} back-to-back comparisons.`),
    distribution(ev, ["Control (wrong at first byte)", fixture(sub.fixture_id)])));

  page.append(h("section", { class: "panel" }, h("h2", {}, "The evidence"),
    h("dl", { class: "stats" },
      stat("Mean difference", fmtNs(ev.mean_difference_ns), "tested minus control", r.decision === "leak_detected" ? "leak" : null),
      stat("p-value", fmtP(r.p_value), "paired t-test"),
      stat("Effect size (dz)", fmt(r.effect_size, 2), "difference ÷ spread of the pairs"),
      stat("Control mean", fmtNs(ev.baseline_summary_ns.mean), `median ${fmt(ev.baseline_summary_ns.median, 1)}, sd ${fmt(ev.baseline_summary_ns.stddev, 1)}`),
      stat("Tested mean", fmtNs(ev.fixture_summary_ns.mean), `median ${fmt(ev.fixture_summary_ns.median, 1)}, sd ${fmt(ev.fixture_summary_ns.stddev, 1)}`),
      stat("Samples per group", ev.sample_size_per_group, `${ev.warmup_runs_per_group} warm-up runs`)),
    ciPlot(ev.mean_difference_ns, r.ci_low, r.ci_high, `${Math.round(r.thresholds.ci_level * 100)}%`)));

  const checks = ruleChecks(r);
  page.append(h("div", { class: "grid2" },
    h("section", { class: "panel" }, h("h2", {}, "Why this verdict"),
      h("ul", { class: "checks" }, checks.map((c) => h("li", { class: c.ok ? "yes" : "no" }, h("span", { class: "mark", "aria-hidden": "true" }, c.ok ? "✓" : "✗"), h("span", { class: "sr-only" }, c.ok ? "Met: " : "Not met: "), c.text))),
      h("p", { class: "muted small" }, `A leak needs all three. "No leak" needs the opposite of all three. Anything in between is inconclusive. Rule: ${r.rule_name} v${r.rule_version}.`)),
    h("section", { class: "panel" }, h("h2", {}, "What to do about it"),
      h("ul", { class: "reasons" }, r.reasons.map((t) => h("li", {}, t))),
      ev.jitter?.injected ? h("p", { class: "muted small" }, `This run injected ${ev.jitter.stddev_ns} ns of random jitter${ev.jitter.clamped_samples ? `; ${ev.jitter.clamped_samples} samples were clamped at zero` : ""}.`) : null)));

  const repro = [
    ["Implementation", sub.implementation], ["Guess tested", sub.fixture_id], ["Samples per group", sub.sample_size], ["Warm-up runs", sub.warmup_runs],
    ["Seed", sub.seed ?? "none (random)"],
    ["Thresholds", `alpha ${r.thresholds.alpha} · min effect ${r.thresholds.min_effect_size} · CI level ${r.thresholds.ci_level}`],
    ["Rule", `${r.rule_name} v${r.rule_version}`], ["Engine", r.engine_version], ["Schedule SHA-256", ev.schedule_sha256],
  ];
  page.append(h("section", { class: "panel" }, h("h2", {}, "How to reproduce this"),
    h("p", { class: "muted" }, "Re-running with these exact settings repeats the same measurement schedule. Wall-clock times will still vary a little between runs."),
    h("dl", { class: "kv" }, repro.map(([k, v]) => [h("dt", {}, k), h("dd", { class: "mono" }, String(v))])),
    h("p", { class: "muted small" }, `Interpretation of the interval level: ${ev.confidence_interpretation}.`)));
  page.append(h("p", { class: "caveat" }, "This is a local educational microbenchmark. Results depend on hardware, runtime and system load, and a clean result is not proof that code is constant-time."));
  return page;
}

// ---------------------------------------------------------------- compare two runs
export async function comparePage({ args }) {
  const [a, b] = await Promise.all([load(args[0]), load(args[1])]);
  if (!a.result || !b.result) return alertBox("Both measurements need a finished result to be compared.");
  const sameSettings = ["implementation", "fixture_id", "sample_size", "warmup_runs", "seed"].every((k) => a.sub[k] === b.sub[k]);
  const sameSchedule = a.result.evidence.schedule_sha256 === b.result.evidence.schedule_sha256;
  const col = (x) => {
    const r = x.result, ev = r.evidence;
    return [
      badge(DECISIONS[r.decision].short, DECISIONS[r.decision].tone), r.severity, impl(x.sub.implementation), fixture(x.sub.fixture_id),
      x.sub.sample_size, x.sub.seed ?? "none", fmtNs(ev.mean_difference_ns), `${fmt(r.ci_low, 1)} to ${fmt(r.ci_high, 1)} ns`, fmtP(r.p_value), fmt(r.effect_size, 2),
      `alpha ${r.thresholds.alpha}, effect ${r.thresholds.min_effect_size}`, shortId(ev.schedule_sha256),
    ];
  };
  const labels = ["Decision", "Severity", "Implementation", "Guess tested", "Samples per group", "Seed", "Mean difference", "Confidence interval", "p-value", "Effect size (dz)", "Thresholds used", "Schedule hash"];
  const ca = col(a), cb = col(b);
  const page = h("div", { "data-title": "Compare" }, pageHead("Compare two runs", `${a.sub.label}  vs  ${b.sub.label}`));

  page.append(h("div", { class: `callout ${sameSettings && sameSchedule ? "tone-clean" : "tone-unsure"}` },
    sameSettings
      ? (sameSchedule ? h("p", {}, h("strong", {}, "Same measurement schedule. "), "Both runs used identical settings and produced the same randomized schedule hash, so any difference in timing comes from the machine, not from the setup.")
                      : h("p", {}, h("strong", {}, "Same settings, different schedule. "), "The settings match but the schedule hashes do not, so these are not an exact repeat."))
      : h("p", {}, h("strong", {}, "Different settings. "), "These runs differ in implementation, input, sample size, warm-up or seed, so differences are expected.")));

  page.append(h("section", { class: "panel" }, h("div", { class: "table-wrap" }, h("table", { class: "cmp" },
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Measure"),
      h("th", { scope: "col" }, h("a", { href: `#/results/${a.sub.id}` }, a.sub.label)), h("th", { scope: "col" }, h("a", { href: `#/results/${b.sub.id}` }, b.sub.label)))),
    h("tbody", {}, labels.map((l, i) => h("tr", {}, h("th", { scope: "row" }, l), h("td", { class: "mono-cell" }, ca[i]), h("td", { class: "mono-cell" }, cb[i]))))))));

  page.append(h("div", { class: "grid2" }, [a, b].map((x) => h("section", { class: "panel" }, h("h2", {}, x.sub.label),
    distribution(x.result.evidence, ["Control", "Tested input"])))));
  return page;
}

// ---------------------------------------------------------------- prefix sweep
export async function sweepPage({ args }) {
  const ids = (args[0] || "").split(",").filter(Boolean).slice(0, 12);
  if (!ids.length) return alertBox("No measurements selected.");
  const rows = await Promise.all(ids.map(async (id) => ({ id, ...(await load(id)) })));
  const ok = rows.filter((r) => r.result);
  const byImpl = new Map();
  ok.forEach((r) => {
    const key = r.result.evidence.implementation;
    if (!byImpl.has(key)) byImpl.set(key, []);
    byImpl.get(key).push({ x: r.result.evidence.fixture_matching_prefix_bytes, y: r.result.evidence.mean_difference_ns, lo: r.result.ci_low, hi: r.result.ci_high });
  });
  const series = [...byImpl].map(([k, points]) => ({ name: IMPLEMENTATIONS[k]?.long ?? k, cls: k === "vulnerable" ? "s-leak" : "s-safe", points: points.sort((p, q) => p.x - q.x) }));

  const page = h("div", { "data-title": "Prefix sweep" }, pageHead("Prefix sweep", "Does each extra correct byte cost measurable time? That is exactly what lets an attacker guess a secret one byte at a time."));
  if (!series.length) { page.append(empty("Nothing to plot", "None of these measurements has a result.")); return page; }
  page.append(h("section", { class: "panel" }, h("h2", {}, "Timing difference by correct prefix length"),
    h("p", { class: "muted" }, "Each point is the mean extra time versus the control, with its confidence interval. A line that climbs means the comparison leaks how much of the guess is right; a flat line near zero means it does not."),
    sweepChart(series)));
  page.append(h("section", { class: "panel" }, h("h2", {}, "Measurements"), h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, ["Implementation", "Correct bytes", "Mean difference", "Confidence interval", "p-value", "Decision", ""].map((t) => h("th", { scope: "col" }, t)))),
    h("tbody", {}, ok.sort((p, q) => p.sub.implementation.localeCompare(q.sub.implementation) || p.result.evidence.fixture_matching_prefix_bytes - q.result.evidence.fixture_matching_prefix_bytes).map(({ sub, result: r }) => h("tr", {},
      h("td", {}, impl(sub.implementation)), h("td", {}, r.evidence.fixture_matching_prefix_bytes), h("td", {}, fmtNs(r.evidence.mean_difference_ns)),
      h("td", {}, `${fmt(r.ci_low, 1)} to ${fmt(r.ci_high, 1)} ns`), h("td", {}, fmtP(r.p_value)),
      h("td", {}, badge(DECISIONS[r.decision].short, DECISIONS[r.decision].tone)), h("td", {}, h("a", { href: `#/results/${sub.id}` }, "Open")))))))));
  return page;
}
