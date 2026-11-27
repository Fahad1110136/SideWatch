import { api } from "../api.js";
import { h, hs, stat, badge, fmtDate, fmtSigned, empty } from "../ui.js";
import { withResults } from "../data.js";
import { DECISIONS, IMPLEMENTATIONS, FIXTURES, PRESETS } from "../config.js";
import { traceGlyph, byteTower, gauge } from "../charts.js";
import { pointerTilt, reduced } from "../fx.js";

// The story told beside the pinned 3D scene. `lit` = layers lit, `tone` = colour, `scan` = animated scan.
const CHAPTERS = [
  { title: "It starts with a simple comparison", tone: "leak", lit: 0, scan: true, cap: "A guess is checked against a secret, one byte at a time",
    text: "A login check compares your guess with a stored secret. A naive comparison stops at the first wrong byte, so a guess that starts correctly keeps the check busy a little longer than one that does not.",
    chips: ["Early exit", "Byte by byte"] },
  { title: "Time becomes a signal", tone: "leak", lit: 3, cap: "Each correct byte adds a little time",
    text: "Every correct leading byte adds a few nanoseconds. On its own that is noise. Repeated thousands of times it becomes a pattern, and an attacker can follow it one byte at a time.",
    chips: ["Nanoseconds", "Prefix guessing"] },
  { title: "So we measure, repeatedly", tone: "leak", lit: 5, cap: "Thousands of repeats until the pattern appears",
    text: "SideWatch times a guess against a control that is wrong from the first byte. It warms up the code, repeats the test thousands of times, and records the seed so a reviewer can reproduce the exact run.",
    chips: ["Warm-up runs", "Seeded schedule", "30 to 5,000 samples"] },
  { title: "Evidence, not a hunch", tone: "leak", lit: 6, gauge: true, cap: "A verdict needs three independent checks to agree",
    text: "A significance test, a confidence interval and an effect size must agree before a leak is reported. Every verdict names the rule, the threshold and the reason behind it, so it can be challenged and repeated.",
    chips: ["p-value", "Confidence interval", "Effect size"] },
  { title: "Then close the gap", tone: "clean", lit: 8, flat: true, cap: "Constant-time: every byte is inspected, so timing no longer shows progress",
    text: "A constant-time comparison examines every byte wherever the first difference lies, so the layers line up and timing stops revealing progress. SideWatch measures the fix too. A clean result is encouraging, but never proof.",
    chips: ["Constant-time", "Never proof"] },
  { title: "Accountable by design", tone: "clean", lit: 8, flat: true, cap: "Every decision is on the record",
    text: "Roles are enforced on the server, thresholds are versioned and confirmed, and every security-relevant action is written to a hash-chained audit log that an administrator can verify.",
    chips: ["Server-side roles", "Versioned rules", "Audit chain"] },
];

const PATHS = [
  { path: "run", roles: ["admin", "operator"], title: "Run a measurement", text: "Set up a controlled experiment and watch the evidence form." },
  { path: "history", roles: ["admin", "operator", "viewer"], title: "Review history", text: "Filter past runs, compare two results and export a sanitized report." },
  { path: "rules", roles: ["admin", "operator"], title: "Read the rules", text: "See the thresholds behind every verdict. Administrators can tune them." },
  { path: "users", roles: ["admin"], title: "Manage access", text: "Create accounts and keep every role at least privilege." },
  { path: "audit", roles: ["admin"], title: "Inspect the audit log", text: "Follow every action and verify that the log has not been altered." },
];

const smooth = () => (reduced() ? "auto" : "smooth");

/** Marks the chapter nearest the middle of the screen as active and reports it. Stops once the page is gone. */
function storyScroll(root, story, chapters, onStep, onProgress) {
  let cur = -1, queued = false;
  const tick = () => {
    if (!root.isConnected) { window.removeEventListener("scroll", tick); window.removeEventListener("resize", tick); return; }
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      const mid = window.innerHeight / 2;
      let best = 0, bestD = Infinity;
      chapters.forEach((c, i) => { const r = c.getBoundingClientRect(); const d = Math.abs(r.top + r.height / 2 - mid); if (d < bestD) { bestD = d; best = i; } });
      if (best !== cur) { cur = best; onStep(best); }
      const r = story.getBoundingClientRect();
      onProgress(r.top < mid && r.bottom > mid, Math.max(0, Math.min(1, -r.top / Math.max(1, r.height - window.innerHeight))));
    });
  };
  window.addEventListener("scroll", tick, { passive: true });
  window.addEventListener("resize", tick);
  tick();
}

export async function homePage({ user }) {
  const canRun = user.role !== "viewer";
  const subs = await api.listSubmissions({ limit: 20 });
  const rows = await withResults(subs);
  const done = rows.filter((r) => r.result);
  const count = (d) => done.filter((r) => r.result.decision === d).length;
  const failed = rows.filter((r) => r.sub.status === "failed").length;
  const newest = done[0];

  const root = h("div", { class: "home", "data-title": "Home" });

  // ---------- Chapter 0: hero
  const story = h("div", { class: "story", "data-step": "0" });
  const heroTower = h("div", { class: "hero-tilt" }, byteTower(newest ? 5 : 3, { animate: true, size: "lg" }));
  pointerTilt(heroTower, 14);
  const trace = hs("svg", { class: "hero-trace", viewBox: "0 0 1200 200", preserveAspectRatio: "none", "aria-hidden": "true" },
    hs("polyline", { points: "0,120 150,120 190,40 250,170 320,70 380,120 560,120 600,30 660,180 730,80 790,120 1000,120 1040,50 1100,150 1200,120" }));
  const hero = h("section", { class: "s-hero", "aria-labelledby": "hero-title" },
    h("div", { class: "orb o1", "data-speed": "-0.12", "aria-hidden": "true" }),
    h("div", { class: "orb o2", "data-speed": "0.1", "aria-hidden": "true" }),
    h("div", { class: "hero-floor", "data-speed": "0.18", "aria-hidden": "true" }, h("div", { class: "hero-floor-grid" })),
    h("div", { class: "hero-trace-wrap", "data-speed": "0.06", "aria-hidden": "true" }, trace),
    h("div", { class: "s-text", "data-depth": "10" },
      h("p", { class: "eyebrow" }, `Welcome back, ${user.username}`),
      h("h1", { id: "hero-title", class: "s-title" },
        ["Find what your code", "gives away through", "timing alone."].map((t, n) => h("span", { class: "ln" }, h("span", { "data-n": String(n) }, t)))),
      h("p", { class: "s-sub" }, "SideWatch is a local laboratory that times authentication checks, tests the differences statistically, and shows exactly when a comparison leaks, with evidence you can reproduce and defend."),
      h("div", { class: "s-cta" },
        canRun ? h("a", { class: "btn btn-primary", href: "#/run" }, "Start a measurement") : h("a", { class: "btn btn-primary", href: "#/history" }, "Review results"),
        h("button", { class: "btn btn-ghost-light", type: "button", onclick: () => story.scrollIntoView({ behavior: smooth(), block: "start" }) }, "See how it works")),
      h("ul", { class: "s-chips", "aria-label": "Key properties" },
        ["Local targets only", "Reproducible runs", "Audited actions"].map((t) => h("li", { class: "s-chip" }, t)))),
    h("div", { class: "s-visual", "data-depth": "-18" }, heroTower),
    h("button", { class: "scroll-cue", type: "button", "aria-label": "Scroll to the story", onclick: () => story.scrollIntoView({ behavior: smooth(), block: "start" }) },
      h("span", { class: "mouse" }, h("i", {})), h("span", {}, "Scroll")));
  hero.querySelectorAll(".ln > span").forEach((s) => s.style.setProperty("--n", s.dataset.n));
  root.append(hero);

  // ---------- Chapters 1-6: pinned 3D scene + story
  const tower = byteTower(0, { animate: true, size: "lg", tone: "leak" });
  const slabs = [...tower.querySelectorAll(".slab")];
  const stageTilt = h("div", { class: "stage-tilt" }, tower);
  pointerTilt(stageTilt, 10);
  const stageNo = h("span", { class: "stage-no" }, "Chapter 1 of 6");
  const stageCap = h("p", { class: "stage-cap" }, CHAPTERS[0].cap);
  const gaugeHost = h("div", { class: "stage-gauge" });
  const gaugeNote = h("span", { class: "stage-gauge-note" }, newest ? "Your latest run" : "Illustrative example");
  const stage = h("div", { class: "story-stage", "aria-hidden": "true" }, stageNo, stageTilt, h("div", { class: "stage-gauge-wrap" }, gaugeHost, gaugeNote), stageCap);

  const chapterEls = CHAPTERS.map((c, i) => h("article", { class: "chapter", "aria-labelledby": `ch-${i}` },
    h("div", { class: "chapter-card" },
      h("p", { class: "chapter-no" }, `${String(i + 1).padStart(2, "0")} / 06`),
      h("h2", { id: `ch-${i}` }, c.title),
      h("p", {}, c.text),
      h("ul", { class: "chips" }, c.chips.map((t) => h("li", {}, t))))));
  story.append(stage, h("div", { class: "chapters" }, chapterEls));
  root.append(story);

  const dots = h("nav", { class: "story-dots", "aria-label": "Story chapters" },
    CHAPTERS.map((c, i) => h("button", { class: "dot", type: "button", title: c.title, "aria-label": `Chapter ${i + 1}: ${c.title}`,
      onclick: () => chapterEls[i].scrollIntoView({ behavior: smooth(), block: "center" }) })));
  root.append(dots);
  const dotEls = [...dots.children];

  let shownGauge = false;
  const setStep = (i) => {
    const c = CHAPTERS[i];
    story.dataset.step = String(i);
    chapterEls.forEach((el, k) => el.classList.toggle("active", k === i));
    dotEls.forEach((d, k) => { d.classList.toggle("on", k === i); if (k === i) d.setAttribute("aria-current", "true"); else d.removeAttribute("aria-current"); });
    slabs.forEach((s, k) => s.classList.toggle("on", k < c.lit));
    tower.classList.remove("tone-leak", "tone-clean", "tone-unsure");
    tower.classList.add(`tone-${c.tone}`);
    tower.classList.toggle("scan", !!c.scan);
    stageNo.textContent = `Chapter ${i + 1} of 6`;
    stageCap.textContent = c.cap;
    if (c.gauge && !shownGauge) {
      shownGauge = true;
      const d = newest ? DECISIONS[newest.result.decision] : null;
      gaugeHost.replaceChildren(gauge(newest ? newest.result.effect_size : 1.4, d ? d.tone : "leak", newest ? newest.result.thresholds.min_effect_size : 0.2));
    }
    if (!c.gauge) shownGauge = false;
  };
  setStep(0);
  storyScroll(root, story, chapterEls, setStep, (inside, p) => {
    dots.classList.toggle("show", inside);
    story.style.setProperty("--p", p.toFixed(3));
  });

  // ---------- Workspace: your own data
  root.append(h("div", { class: "sect-head" },
    h("p", { class: "eyebrow" }, "Your workspace"),
    h("h2", {}, "Where things stand"),
    h("p", { class: "muted" }, user.role === "viewer" ? "You can review completed measurements and their evidence." : "Start from a ready-made example or pick up where you left off.")));
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

  // ---------- Where to next
  const paths = PATHS.filter((p) => p.roles.includes(user.role));
  root.append(h("div", { class: "sect-head" },
    h("p", { class: "eyebrow" }, "Keep going"),
    h("h2", {}, "Where to next"),
    h("p", { class: "muted" }, "Each page picks up the story where the last one ends. Scroll to the bottom of any page to continue.")));
  root.append(h("div", { class: "paths" }, paths.map((p, i) =>
    h("a", { class: "path-card", href: `#/${p.path}` },
      h("span", { class: "path-no" }, String(i + 1).padStart(2, "0")),
      h("strong", {}, p.title), h("span", { class: "muted" }, p.text), h("span", { class: "path-go", "aria-hidden": "true" }, "→")))));

  root.append(h("section", { class: "block note" }, h("h2", {}, "A note on what this proves"),
    h("p", { class: "muted" }, "This is a local microbenchmark. It can show that a comparison leaks, but it can never prove that a comparison is constant-time.")));
  return root;
}
