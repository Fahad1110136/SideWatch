import { h } from "./ui.js";

export const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const finePointer = () => window.matchMedia("(hover: hover) and (pointer: fine)").matches;

const REVEAL = ".panel, .stat, .preset, .row-card, .callout, .hero, .note, .empty, .next-bar, .path-card, .sect-head";
const TILT = ".preset, .row-card, .stats > .stat, .path-card";

let io = null;
function observer() {
  if (io || !("IntersectionObserver" in window)) return io;
  io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const el = e.target;
      io.unobserve(el);
      el.classList.add("in");
      // Drop the helper classes afterwards so hover and tilt transforms are free to work.
      setTimeout(() => el.classList.remove("reveal", "in"), 1600);
    }
  }, { threshold: 0.08, rootMargin: "0px 0px -6% 0px" });
  return io;
}

function reveal(root) {
  const obs = observer();
  if (!obs) return;
  let i = 0;
  for (const el of root.querySelectorAll(REVEAL)) {
    if (el.parentElement && el.parentElement.closest(REVEAL)) continue;   // only the outer card animates
    el.style.setProperty("--d", `${Math.min(i++, 8) * 70}ms`);
    el.classList.add("reveal");
    obs.observe(el);
  }
}

function tilt(el, max = 7) {
  el.classList.add("tilt");
  el.addEventListener("pointermove", (e) => {
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    el.style.transform = `perspective(900px) rotateX(${((0.5 - y) * max).toFixed(2)}deg) rotateY(${((x - 0.5) * max).toFixed(2)}deg)`;
    el.style.setProperty("--mx", `${(x * 100).toFixed(1)}%`);
    el.style.setProperty("--my", `${(y * 100).toFixed(1)}%`);
  });
  el.addEventListener("pointerleave", () => { el.style.transform = ""; });
}

/** Tilts `el` in 3D towards the pointer anywhere on the page. Stops by itself once `el` leaves the page. */
export function pointerTilt(el, max = 12) {
  if (reduced() || !finePointer()) return;
  const move = (e) => {
    if (!el.isConnected) { window.removeEventListener("pointermove", move); return; }
    const x = e.clientX / window.innerWidth - 0.5, y = e.clientY / window.innerHeight - 0.5;
    el.style.transform = `perspective(1000px) rotateX(${(-y * max).toFixed(2)}deg) rotateY(${(x * max).toFixed(2)}deg)`;
  };
  window.addEventListener("pointermove", move, { passive: true });
}

/** Parallax: [data-speed] moves with scroll (fraction of scroll distance); [data-depth] follows the pointer (pixels). */
function parallax(node) {
  const slow = [...node.querySelectorAll("[data-speed]")], deep = [...node.querySelectorAll("[data-depth]")];
  if (slow.length) {
    let queued = false;
    const onScroll = () => {
      if (!node.isConnected) { window.removeEventListener("scroll", onScroll); return; }
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        const y = window.scrollY;
        for (const el of slow) el.style.transform = `translate3d(0, ${(y * Number(el.dataset.speed)).toFixed(1)}px, 0)`;
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }
  if (deep.length && finePointer()) {
    const onMove = (e) => {
      if (!node.isConnected) { window.removeEventListener("pointermove", onMove); return; }
      const x = e.clientX / window.innerWidth - 0.5, y = e.clientY / window.innerHeight - 0.5;
      for (const el of deep) { const d = Number(el.dataset.depth); el.style.transform = `translate3d(${(x * d).toFixed(1)}px, ${(y * d).toFixed(1)}px, 0)`; }
    };
    window.addEventListener("pointermove", onMove, { passive: true });
  }
}

function countUp(el) {
  const target = Number(el.textContent.trim());
  const t0 = performance.now(), dur = 800;
  const step = (now) => {
    const k = Math.min(1, (now - t0) / dur);
    el.textContent = String(Math.round(target * (1 - (1 - k) ** 3)));
    if (k < 1) requestAnimationFrame(step);
  };
  el.textContent = "0";
  requestAnimationFrame(step);
}

/** Call after a page node has been put on screen. */
export function enhance(node) {
  if (reduced()) return;
  node.classList.add("page-in");
  reveal(node);
  parallax(node);
  for (const dd of node.querySelectorAll(".stat dd")) if (/^\d{1,6}$/.test(dd.textContent.trim()) && dd.textContent.trim() !== "0") countUp(dd);
  if (finePointer()) node.querySelectorAll(TILT).forEach((el) => tilt(el));
}

/** Call once at start-up: scroll progress bar, header shadow, back-to-top button. */
export function initFx() {
  const bar = h("div", { class: "scroll-progress", "aria-hidden": "true" });
  const top = h("button", { class: "to-top", type: "button", "aria-label": "Back to top", hidden: true,
    onclick: () => window.scrollTo({ top: 0, behavior: reduced() ? "auto" : "smooth" }) }, "↑");
  document.body.append(bar, top);
  let queued = false;
  const update = () => {
    queued = false;
    const y = window.scrollY, max = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.transform = `scaleX(${max > 0 ? Math.min(1, y / max).toFixed(4) : 0})`;
    top.hidden = y < 500;
    document.querySelector(".top")?.classList.toggle("scrolled", y > 8);
  };
  window.addEventListener("scroll", () => { if (!queued) { queued = true; requestAnimationFrame(update); } }, { passive: true });
  window.addEventListener("hashchange", update);
}
