// Dependency-free SVG charts (CSP-safe, work offline). Styling lives in style.css.
import { hs, h } from "./ui.js";

const W = 720;
function niceTicks(min, max, count = 5) {
  if (min === max) { min -= 1; max += 1; }
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
  const out = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}
const tickFmt = (v) => (Math.abs(v) >= 1000 ? v.toFixed(0) : Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(0) : v.toFixed(1)).replace(/\.0$/, "");

function plot(height, label, m = { l: 54, r: 18, t: 16, b: 44 }) {
  const svg = hs("svg", { class: "chart", viewBox: `0 0 ${W} ${height}`, role: "img", "aria-label": label });
  return { svg, m, iw: W - m.l - m.r, ih: height - m.t - m.b, H: height };
}
function drawAxes(c, xmin, xmax, ymin, ymax, xlabel, ylabel, { xticks, yticks } = {}) {
  const { svg, m, iw, ih, H } = c;
  const X = (v) => m.l + ((v - xmin) / (xmax - xmin || 1)) * iw;
  const Y = (v) => m.t + ih - ((v - ymin) / (ymax - ymin || 1)) * ih;
  for (const t of yticks || niceTicks(ymin, ymax, 4)) {
    svg.append(hs("line", { class: "c-grid", x1: m.l, x2: m.l + iw, y1: Y(t), y2: Y(t) }));
    svg.append(hs("text", { class: "c-text", x: m.l - 8, y: Y(t) + 4, "text-anchor": "end" }, tickFmt(t)));
  }
  for (const t of xticks || niceTicks(xmin, xmax, 6)) {
    svg.append(hs("text", { class: "c-text", x: X(t), y: m.t + ih + 17, "text-anchor": "middle" }, typeof t === "string" ? t : tickFmt(t)));
  }
  svg.append(hs("line", { class: "c-axis", x1: m.l, x2: m.l + iw, y1: m.t + ih, y2: m.t + ih }));
  svg.append(hs("text", { class: "c-label", x: m.l + iw / 2, y: H - 6, "text-anchor": "middle" }, xlabel));
  svg.append(hs("text", { class: "c-label", x: 13, y: m.t + ih / 2, "text-anchor": "middle", transform: `rotate(-90 13 ${m.t + ih / 2})` }, ylabel));
  return { X, Y };
}

const gauss = (x, m, sd) => Math.exp(-0.5 * ((x - m) / sd) ** 2) / (sd * Math.sqrt(2 * Math.PI));

/**
 * Main timing chart. The engine sends only 20 histogram bins and real timings have long outlier
 * tails, so the raw histogram squeezes the useful part into one or two bars. This view draws each
 * group as a bell curve from its mean and standard deviation (a normal approximation, said so in
 * the legend) and keeps the raw histogram, on a log scale, one click away.
 */
export function distribution(ev, labels = ["Control (no match)", "Tested input"]) {
  const b = ev.baseline_summary_ns, f = ev.fixture_summary_ns;
  const sdB = b.stddev || 1, sdF = f.stddev || 1;
  const lo = Math.max(0, Math.min(b.mean - 3.2 * sdB, f.mean - 3.2 * sdF)), hi = Math.max(b.mean + 3.2 * sdB, f.mean + 3.2 * sdF);
  const c = plot(300, "Estimated timing distributions for the control and the tested input", { l: 22, r: 22, t: 28, b: 44 });
  const ymax = Math.max(gauss(b.mean, b.mean, sdB), gauss(f.mean, f.mean, sdF)) * 1.08;
  const X = (v) => c.m.l + ((v - lo) / (hi - lo)) * c.iw, Y = (v) => c.m.t + c.ih - (v / ymax) * c.ih;
  for (const t of niceTicks(lo, hi, 6)) {
    c.svg.append(hs("line", { class: "c-grid", x1: X(t), x2: X(t), y1: c.m.t, y2: c.m.t + c.ih }));
    c.svg.append(hs("text", { class: "c-text", x: X(t), y: c.m.t + c.ih + 17, "text-anchor": "middle" }, tickFmt(t)));
  }
  c.svg.append(hs("line", { class: "c-axis", x1: c.m.l, x2: c.m.l + c.iw, y1: c.m.t + c.ih, y2: c.m.t + c.ih }));
  c.svg.append(hs("text", { class: "c-label", x: c.m.l + c.iw / 2, y: 294, "text-anchor": "middle" }, "time per comparison (ns)"));
  const curve = (m, sd, cls) => {
    const pts = [];
    for (let i = 0; i <= 120; i++) { const x = lo + ((hi - lo) * i) / 120; pts.push(`${X(x).toFixed(1)},${Y(gauss(x, m, sd)).toFixed(1)}`); }
    c.svg.append(hs("polygon", { class: cls, points: `${X(lo)},${Y(0)} ${pts.join(" ")} ${X(hi)},${Y(0)}` }));
  };
  curve(b.mean, sdB, "c-base"); curve(f.mean, sdF, "c-fix");
  const baseLeft = b.mean <= f.mean;
  const mark = (v, cls, left) => {
    c.svg.append(hs("line", { class: `c-mean ${cls}`, x1: X(v), x2: X(v), y1: c.m.t - 4, y2: c.m.t + c.ih }));
    c.svg.append(hs("text", { class: `c-text c-tag ${cls}`, x: X(v) + (left ? -6 : 6), y: c.m.t + 6, "text-anchor": left ? "end" : "start" }, `mean ${v.toFixed(1)} ns`));
  };
  mark(b.mean, "c-base-t", baseLeft); mark(f.mean, "c-fix-t", !baseLeft);
  const box = withLegend(c.svg, [["c-base", labels[0]], ["c-fix", labels[1]]]);
  box.append(h("p", { class: "muted small" }, "Curves are a normal approximation drawn from each group's mean and standard deviation. The raw samples are below."));
  box.append(rawHistogram(ev.histogram, labels));
  return box;
}

function rawHistogram(hist, labels) {
  const e = hist.bin_edges_ns, a = hist.baseline_counts, b = hist.fixture_counts;
  const c = plot(260, "Raw histogram of measured times, log scale", { l: 54, r: 18, t: 12, b: 44 });
  const L = (n) => Math.log10(1 + n), ymax = Math.max(L(Math.max(...a, ...b)), 1) * 1.08;
  const X = (v) => c.m.l + ((v - e[0]) / (e[e.length - 1] - e[0] || 1)) * c.iw, Y = (v) => c.m.t + c.ih - (L(v) / ymax) * c.ih;
  for (const n of [0, 10, 100, 1000, 10000].filter((n) => L(n) <= ymax)) {
    c.svg.append(hs("line", { class: "c-grid", x1: c.m.l, x2: c.m.l + c.iw, y1: Y(n), y2: Y(n) }));
    c.svg.append(hs("text", { class: "c-text", x: c.m.l - 8, y: Y(n) + 4, "text-anchor": "end" }, String(n)));
  }
  for (const t of niceTicks(e[0], e[e.length - 1], 6)) c.svg.append(hs("text", { class: "c-text", x: X(t), y: c.m.t + c.ih + 17, "text-anchor": "middle" }, tickFmt(t)));
  c.svg.append(hs("line", { class: "c-axis", x1: c.m.l, x2: c.m.l + c.iw, y1: c.m.t + c.ih, y2: c.m.t + c.ih }));
  c.svg.append(hs("text", { class: "c-label", x: c.m.l + c.iw / 2, y: 254, "text-anchor": "middle" }, "time per comparison (ns)"));
  c.svg.append(hs("text", { class: "c-label", x: 13, y: c.m.t + c.ih / 2, "text-anchor": "middle", transform: `rotate(-90 13 ${c.m.t + c.ih / 2})` }, "samples (log scale)"));
  const bars = (counts, cls, half) => counts.forEach((n, i) => {
    if (!n) return;
    const w = (X(e[i + 1]) - X(e[i]) - 2) / 2;
    c.svg.append(hs("rect", { class: cls, x: X(e[i]) + 1 + (half ? w : 0), y: Y(n), width: Math.max(1, w), height: c.m.t + c.ih - Y(n) }));
  });
  bars(a, "c-base", false); bars(b, "c-fix", true);
  const rows = a.map((n, i) => h("tr", {}, h("td", {}, `${e[i].toFixed(0)} to ${e[i + 1].toFixed(0)}`), h("td", {}, n), h("td", {}, b[i])));
  return h("details", { class: "data-details" }, h("summary", {}, "Show the raw histogram and its data"),
    h("p", { class: "muted small" }, "Real timings have occasional large spikes. The log scale keeps those rare samples visible next to the typical ones."),
    c.svg,
    h("div", { class: "table-wrap" }, h("table", {}, h("caption", {}, "Samples per time bin"),
      h("thead", {}, h("tr", {}, ["Time bin (ns)", labels[0], labels[1]].map((t) => h("th", { scope: "col" }, t)))), h("tbody", {}, rows))));
}

/** Confidence interval of the mean (fixture - control) difference, relative to zero. */
export function ciPlot(mean, lo, hi, levelText) {
  const c = plot(124, "Confidence interval of the timing difference", { l: 24, r: 24, t: 14, b: 40 });
  const pad = (hi - lo || Math.abs(mean) || 1) * 0.9;
  const xmin = Math.min(lo, 0) - pad * 0.4, xmax = Math.max(hi, 0) + pad * 0.4;
  const X = (v) => c.m.l + ((v - xmin) / (xmax - xmin)) * c.iw;
  const y = 52;
  for (const t of niceTicks(xmin, xmax, 6)) c.svg.append(hs("text", { class: "c-text", x: X(t), y: 98, "text-anchor": "middle" }, tickFmt(t)));
  c.svg.append(hs("line", { class: "c-zero", x1: X(0), x2: X(0), y1: 22, y2: 82 }));
  c.svg.append(hs("text", { class: "c-text", x: X(0) + 6, y: 20, "text-anchor": "start" }, "0 = no difference"));
  c.svg.append(hs("line", { class: "c-ci", x1: X(lo), x2: X(hi), y1: y, y2: y }));
  for (const v of [lo, hi]) {
    c.svg.append(hs("line", { class: "c-ci", x1: X(v), x2: X(v), y1: y - 8, y2: y + 8 }));
    c.svg.append(hs("text", { class: "c-text c-tag c-fix-t", x: X(v), y: y - 14, "text-anchor": "middle" }, v.toFixed(1)));
  }
  c.svg.append(hs("circle", { class: "c-fix-dot", cx: X(mean), cy: y, r: 6 }));
  c.svg.append(hs("text", { class: "c-label", x: c.m.l + c.iw / 2, y: 118, "text-anchor": "middle" }, `mean difference in ns, with its ${levelText} confidence interval`));
  return h("div", {}, c.svg);
}

/** Mean difference vs. number of correct leading bytes, one line per implementation. */
export function sweepChart(series) {
  const xs = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b);
  const c = plot(320, "Mean timing difference against the number of correct leading bytes");
  const all = series.flatMap((s) => s.points.flatMap((p) => [p.lo, p.hi, 0]));
  const ymin = Math.min(...all), ymax = Math.max(...all), pad = (ymax - ymin || 1) * 0.12;
  const pos = (x) => xs.indexOf(x);
  const xticks = xs.map((x) => `${x === 32 ? "all 32" : x} byte${x === 1 ? "" : "s"}`);
  const { Y } = drawAxes(c, -0.5, xs.length - 0.5, ymin - pad, ymax + pad, "leading bytes of the guess that are correct", "mean difference vs. control (ns)", { xticks: [] });
  const X = (i) => c.m.l + ((i + 0.5) / xs.length) * c.iw;
  xs.forEach((x, i) => c.svg.append(hs("text", { class: "c-text", x: X(i), y: c.m.t + c.ih + 17, "text-anchor": "middle" }, xticks[i])));
  c.svg.append(hs("line", { class: "c-zero", x1: c.m.l, x2: c.m.l + c.iw, y1: Y(0), y2: Y(0) }));
  series.forEach((s) => {
    const pts = s.points.map((p) => ({ ...p, px: X(pos(p.x)) }));
    c.svg.append(hs("polyline", { class: `c-line ${s.cls}`, points: pts.map((p) => `${p.px},${Y(p.y)}`).join(" ") }));
    pts.forEach((p) => {
      c.svg.append(hs("line", { class: `c-whisker ${s.cls}`, x1: p.px, x2: p.px, y1: Y(p.lo), y2: Y(p.hi) }));
      c.svg.append(hs("circle", { class: `c-dot ${s.cls}`, cx: p.px, cy: Y(p.y), r: 5 }));
    });
  });
  return withLegend(c.svg, series.map((s) => [s.cls, s.name]));
}

/** Tiny decorative glyph: two humps pulled apart in proportion to the effect size. */
export function traceGlyph(dz, tone) {
  const w = 132, hgt = 60, sep = Math.min(Math.abs(dz), 2.2) * 17;
  const curve = (cx) => {
    const pts = [];
    for (let x = 6; x <= w - 6; x += 3) pts.push(`${x},${(hgt - 6 - 44 * Math.exp(-((x - cx) ** 2) / (2 * 11 ** 2))).toFixed(1)}`);
    return pts.join(" ");
  };
  const mid = w / 2;
  return hs("svg", { class: `glyph tone-${tone}`, viewBox: `0 0 ${w} ${hgt}`, "aria-hidden": "true", width: w, height: hgt },
    hs("polyline", { class: "g-a", points: curve(mid - sep / 2) }),
    hs("polyline", { class: "g-b", points: curve(mid + sep / 2) }),
    hs("line", { class: "g-base", x1: 4, x2: w - 4, y1: hgt - 5, y2: hgt - 5 }));
}

function withLegend(svg, items) {
  return h("div", {}, svg, h("p", { class: "legend" },
    items.map(([cls, text]) => h("span", {}, h("i", { class: `swatch ${cls}` }), text))));
}
