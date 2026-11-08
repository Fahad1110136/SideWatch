// Constants that mirror the backend/engine contract. The SERVER enforces all of these;
// the UI repeats them only to give instant, friendly feedback.
export const LIMITS = {
  sample_size: { min: 30, max: 5000, def: 1000 },
  warmup_runs: { min: 0, max: 500, def: 50 },
  seed: { min: 0, max: 2 ** 31 - 1 },
};

export const FIXTURES = {
  no_match:        { label: "No match (control)",       prefix: 0,  note: "Differs at the very first byte. Always used as the comparison baseline." },
  prefix_1:        { label: "1 byte correct",           prefix: 1,  note: "Matches one leading byte before the first mismatch." },
  prefix_4:        { label: "4 bytes correct",          prefix: 4,  note: "Matches four leading bytes before the first mismatch." },
  full_match:      { label: "All 32 bytes correct",     prefix: 32, note: "Matches the whole 32-byte reference." },
  prefix_1_jitter: { label: "1 byte correct + jitter",  prefix: 1,  note: "Same as 1 byte, with 250 ns of injected noise." },
  prefix_4_jitter: { label: "4 bytes correct + jitter", prefix: 4,  note: "Same as 4 bytes, with 250 ns of injected noise." },
};
export const SWEEP_FIXTURES = ["prefix_1", "prefix_4", "full_match"];

export const IMPLEMENTATIONS = {
  vulnerable:    { label: "Vulnerable", long: "Vulnerable (early-exit byte loop)" },
  constant_time: { label: "Constant-time", long: "Constant-time (hmac.compare_digest)" },
};

export const DECISIONS = {
  leak_detected:    { label: "Timing leak detected", short: "Leak", tone: "leak" },
  no_leak_detected: { label: "No timing leak detected", short: "No leak", tone: "clean" },
  inconclusive:     { label: "Inconclusive", short: "Inconclusive", tone: "unsure" },
};

export const RULE_INFO = {
  alpha: {
    label: "Significance level (alpha)",
    help: "A difference only counts if its p-value is below this. Smaller means stricter.",
    step: 0.001,
  },
  min_effect_size: {
    label: "Minimum effect size (Cohen's dz)",
    help: "Differences smaller than this are treated as too small to matter, even if they are statistically significant.",
    step: 0.05,
  },
  ci_level: {
    label: "Confidence-interval level",
    help: "How wide the confidence interval is (0.99 means 99%). This is not the chance that a leak exists.",
    step: 0.001,
  },
};

export const ROLES = ["admin", "operator", "viewer"];

// One-click starting points. Each maps to a case from the project's evaluation plan.
export const PRESETS = {
  leak:    { title: "Show a leak",        text: "Vulnerable comparison, 4 correct bytes, 2000 samples.", values: { implementation: "vulnerable",    fixture_id: "prefix_4",        sample_size: 2000 } },
  control: { title: "Constant-time control", text: "Same input against the safe comparison. Should show no leak.", values: { implementation: "constant_time", fixture_id: "prefix_4",        sample_size: 2000 } },
  few:     { title: "Too few samples",    text: "Only 30 samples: watch the result become unreliable.", values: { implementation: "vulnerable",    fixture_id: "prefix_1",        sample_size: 30 } },
  noisy:   { title: "Noisy timing",       text: "Adds 250 ns of random jitter to hide the signal.",     values: { implementation: "vulnerable",    fixture_id: "prefix_4_jitter", sample_size: 1000 } },
};

export const RULE_BOUNDS = { alpha: [0.0001, 0.1], min_effect_size: [0, 5], ci_level: [0.8, 0.999] };
