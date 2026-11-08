import { api } from "../api.js";
import { h, pageHead, field, setFieldError, alertBox, toast } from "../ui.js";
import { LIMITS, FIXTURES, SWEEP_FIXTURES, IMPLEMENTATIONS, PRESETS } from "../config.js";

const MODES = {
  single:  { title: "Single run", text: "One implementation, one input." },
  sweep:   { title: "Prefix sweep", text: "1, 4 and all 32 correct bytes, to see leakage grow." },
  faceoff: { title: "Face-off", text: "Vulnerable and constant-time, same input." },
};
const LABEL_RE = /^[\w .\-()]+$/;

export async function runPage({ args, navigate }) {
  let preset = PRESETS[args[0]]?.values || {};
  let again = null;
  if (args[0]?.startsWith("from-")) {              // "Run again" from a result page
    try {
      const old = await api.getSubmission(args[0].slice(5));
      again = old;
      preset = { implementation: old.implementation, fixture_id: old.fixture_id, sample_size: old.sample_size };
    } catch { /* fall back to defaults */ }
  }
  let fixtureIds = Object.keys(FIXTURES);
  try { const ids = await api.fixtures(); fixtureIds = ids.filter((id) => id !== "no_match" && FIXTURES[id]); } catch { /* fall back to known list */ }
  fixtureIds = fixtureIds.filter((id) => id !== "no_match");

  let mode = "single";
  const modeBtns = Object.entries(MODES).map(([key, m]) =>
    h("button", { type: "button", class: "seg", role: "tab", "aria-selected": key === mode, onclick: () => setMode(key) },
      h("strong", {}, m.title), h("span", {}, m.text)));

  const impl = h("select", { id: "impl" }, [
    ...Object.entries(IMPLEMENTATIONS).map(([v, i]) => h("option", { value: v }, i.long)),
    h("option", { value: "both" }, "Both implementations")]);
  impl.value = preset.implementation || "vulnerable";
  const fixture = h("select", { id: "fixture" }, fixtureIds.map((id) => h("option", { value: id }, `${FIXTURES[id].label}`)));
  fixture.value = preset.fixture_id && fixtureIds.includes(preset.fixture_id) ? preset.fixture_id : "prefix_4";
  const fixtureNote = h("span", {});
  const size = h("input", { id: "size", type: "number", min: LIMITS.sample_size.min, max: LIMITS.sample_size.max, step: 1, value: preset.sample_size || LIMITS.sample_size.def });
  const sizeRange = h("input", { type: "range", "aria-label": "Samples slider", min: LIMITS.sample_size.min, max: LIMITS.sample_size.max, step: 10, value: size.value, class: "range" });
  const warm = h("input", { id: "warm", type: "number", min: LIMITS.warmup_runs.min, max: LIMITS.warmup_runs.max, step: 1, value: again?.warmup_runs ?? LIMITS.warmup_runs.def });
  const seed = h("input", { id: "seed", type: "number", min: 0, max: LIMITS.seed.max, step: 1, placeholder: "random", value: again?.seed ?? "" });
  const label = h("input", { id: "label", maxlength: 80, placeholder: "Automatic" });
  const msg = h("div", { "aria-live": "assertive" });
  const progress = h("div", { class: "progress", hidden: true }, h("div", { class: "bar" }), h("span", {}));
  const go = h("button", { class: "btn btn-primary", type: "submit" }, "Run measurement");

  size.addEventListener("input", () => { sizeRange.value = size.value; });
  sizeRange.addEventListener("input", () => { size.value = sizeRange.value; });
  const implField = field("impl", "Implementation", impl);
  const fixtureField = field("fixture", "Guess to test", fixture, fixtureNote);
  const seedHint = "Use the same seed to repeat the same measurement schedule. Wall-clock times will still vary a little.";

  function showFixtureNote() { fixtureNote.textContent = FIXTURES[fixture.value]?.note || ""; }
  fixture.addEventListener("change", showFixtureNote); showFixtureNote();

  function setMode(next) {
    mode = next;
    modeBtns.forEach((b, i) => b.setAttribute("aria-selected", Object.keys(MODES)[i] === next));
    implField.hidden = next === "faceoff";
    fixtureField.hidden = next === "sweep";
    [...impl.options].forEach((o) => { o.disabled = next !== "sweep" && o.value === "both"; });
    if (next !== "sweep" && impl.value === "both") impl.value = "vulnerable";
  }

  const num = (el) => (el.value === "" ? NaN : Number(el.value));
  const int = Number.isInteger;

  function validate() {
    ["size", "warm", "seed", "label"].forEach((i) => setFieldError(i));
    let ok = true;
    const bad = (id, text) => { setFieldError(id, text); ok = false; };
    const n = num(size), w = num(warm), s = num(seed);
    if (!int(n) || n < LIMITS.sample_size.min || n > LIMITS.sample_size.max) bad("size", `Enter a whole number from ${LIMITS.sample_size.min} to ${LIMITS.sample_size.max}.`);
    if (!int(w) || w < LIMITS.warmup_runs.min || w > LIMITS.warmup_runs.max) bad("warm", `Enter a whole number from ${LIMITS.warmup_runs.min} to ${LIMITS.warmup_runs.max}.`);
    if (seed.value !== "" && (!int(s) || s < 0 || s > LIMITS.seed.max)) bad("seed", "Seed must be a whole number from 0 to 2147483647.");
    if (label.value.trim() && !LABEL_RE.test(label.value.trim())) bad("label", "Use letters, numbers, spaces and . - _ ( ) only.");
    return ok ? { sample_size: n, warmup_runs: w, seed: seed.value === "" ? null : s, label: label.value.trim() } : null;
  }

  async function submitOne(p, implementation, fixture_id, tag) {
    const body = { label: (p.label ? `${p.label} - ${tag}` : `${tag} (${p.sample_size} samples)`).slice(0, 80), implementation, fixture_id,
      sample_size: p.sample_size, warmup_runs: p.warmup_runs };
    if (p.seed !== null) body.seed = p.seed;
    const sub = await api.createSubmission(body);
    if (sub.status !== "completed") throw Object.assign(new Error(`The measurement could not be completed (${sub.error_code || "ENGINE_FAILED"}). Try again, or check the server log.`), { requestId: null });
    return sub;
  }

  const form = h("form", { novalidate: true, onsubmit: async (e) => {
    e.preventDefault();
    msg.replaceChildren();
    const p = validate();
    if (!p) return;
    const plan = mode === "single" ? [[impl.value, fixture.value]]
      : mode === "faceoff" ? Object.keys(IMPLEMENTATIONS).map((i) => [i, fixture.value])
      : (impl.value === "both" ? Object.keys(IMPLEMENTATIONS) : [impl.value]).flatMap((i) => SWEEP_FIXTURES.map((f) => [i, f]));
    go.disabled = true; progress.hidden = plan.length < 2;
    const ids = [];
    try {
      for (const [i, [implementation, fx]] of plan.entries()) {
        go.textContent = plan.length > 1 ? `Measuring ${i + 1} of ${plan.length}…` : "Measuring…";
        progress.querySelector(".bar").style.width = `${(i / plan.length) * 100}%`;
        progress.querySelector("span").textContent = `${IMPLEMENTATIONS[implementation].label}, ${FIXTURES[fx].label}`;
        ids.push((await submitOne(p, implementation, fx, `${implementation} ${fx}`)).id);
      }
      toast(plan.length > 1 ? "Measurements complete" : "Measurement complete");
      navigate(mode === "single" ? `results/${ids[0]}` : mode === "faceoff" ? `compare/${ids[0]}/${ids[1]}` : `sweep/${ids.join(",")}`);
    } catch (ex) {
      msg.replaceChildren(alertBox(ex));
      if (ex.status === 422) msg.append(h("p", { class: "muted" }, "Check the values above and try again."));
      go.disabled = false; go.textContent = "Run measurement"; progress.hidden = true;
    }
  } },
    msg,
    h("div", { class: "segs", role: "tablist", "aria-label": "Measurement type" }, modeBtns),
    h("div", { class: "form-grid" },
      implField, fixtureField,
      h("div", { class: "field" },
        h("label", { for: "size" }, "Samples per group"), h("div", { class: "pair" }, size, sizeRange),
        h("div", { class: "hint" }, "More samples make a small difference easier to trust. The minimum is 30."),
        h("div", { class: "field-error", id: "size-err", "aria-live": "polite" })),
      field("warm", "Warm-up runs", warm, "Comparisons run before timing starts, so caches are warm."),
      field("seed", "Seed (optional)", seed, seedHint),
      field("label", "Label (optional)", label, "A short name to find this run in the history.")),
    progress,
    h("div", { class: "form-actions" }, go, h("a", { class: "btn btn-quiet", href: "#/" }, "Cancel")));

  setMode("single");
  if (preset.implementation === "both") impl.value = "both";
  const page = h("div", { "data-title": "New measurement" },
    pageHead("New measurement", "Time a guess against a control that is wrong at the first byte. Only simulated comparisons on this machine are measured."),
    h("div", { class: "panel" }, form));
  return page;
}
