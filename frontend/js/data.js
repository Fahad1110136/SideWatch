import { api } from "./api.js";

/** Attach each completed submission's result. Fetched in small batches to stay gentle on the server. */
export async function withResults(subs, batch = 6) {
  const rows = subs.map((sub) => ({ sub, result: null }));
  for (let i = 0; i < rows.length; i += batch) {
    await Promise.all(rows.slice(i, i + batch).map(async (row) => {
      if (row.sub.status !== "completed") return;
      try { row.result = await api.getResult(row.sub.id); } catch { /* shown as "unavailable" */ }
    }));
  }
  return rows;
}

/** Re-derives the engine's decision rule so the UI can show each check. Mirrors engine/interface.py. */
export function ruleChecks(r) {
  const t = r.thresholds, ev = r.evidence;
  const p = r.p_value, dz = Math.abs(r.effect_size ?? 0);
  const ciExcludesZero = r.ci_low > 0 || r.ci_high < 0;
  return [
    { ok: p < t.alpha, text: `p-value ${p === 0 ? "< 1e-300" : p.toPrecision(2)} ${p < t.alpha ? "is below" : "is not below"} the significance level ${t.alpha}`, },
    { ok: ciExcludesZero, text: `${Math.round(t.ci_level * 100)}% interval ${r.ci_low.toFixed(1)} to ${r.ci_high.toFixed(1)} ns ${ciExcludesZero ? "does not include" : "includes"} 0` },
    { ok: dz >= t.min_effect_size, text: `effect size |dz| ${dz.toFixed(2)} ${dz >= t.min_effect_size ? "reaches" : "is below"} the minimum ${t.min_effect_size}` },
  ];
}
