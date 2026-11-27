import { h, hs, field, alertBox, setFieldError } from "../ui.js";
import { byteTower } from "../charts.js";
import { pointerTilt, enhance } from "../fx.js";

const ICONS = {
  timer: ["M12 8v5l3 2", "M9 2h6", "M12 5a8 8 0 1 0 0 16 8 8 0 0 0 0-16z"],
  chart: ["M4 20V11", "M10 20V5", "M16 20v-7", "M2 20h20"],
  shield: ["M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z", "M9 12l2 2 4-4"],
  lock: ["M6 11h12v9H6z", "M8 11V8a4 4 0 0 1 8 0v3"],
};
const icon = (name) => hs("svg", { class: "ico", viewBox: "0 0 24 24", "aria-hidden": "true" }, ICONS[name].map((d) => hs("path", { d })));

const POINTS = [
  ["timer", "Measure", "Repeated, seeded timing runs that anyone can reproduce."],
  ["chart", "Decide", "Verdicts backed by a p-value, a confidence interval and an effect size."],
  ["shield", "Defend", "Server-enforced roles and a tamper-evident audit trail."],
];

export function loginPage({ onLogin, message }) {
  const user = h("input", { id: "u", autocomplete: "username", maxlength: 32, autofocus: true, spellcheck: "false", placeholder: "Your username" });
  const pass = h("input", { id: "p", type: "password", autocomplete: "current-password", maxlength: 128, placeholder: "Your password" });
  const msg = h("div", { "aria-live": "assertive" }, message ? h("div", { class: "alert info" }, message) : null);
  const caps = h("div", { class: "caps-hint", "aria-live": "polite" });
  const arrow = () => h("span", { class: "btn-arrow", "aria-hidden": "true" }, "→");
  const btn = h("button", { class: "btn-login", type: "submit" }, "Sign in", arrow());
  const setBtn = (text, withArrow) => btn.replaceChildren(text, withArrow ? arrow() : null);

  const toggle = h("button", { class: "pw-toggle", type: "button", "aria-pressed": "false", "aria-label": "Show password", onclick: () => {
    const show = pass.type === "password";
    pass.type = show ? "text" : "password";
    toggle.textContent = show ? "Hide" : "Show";
    toggle.setAttribute("aria-pressed", String(show));
    toggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
  } }, "Show");
  pass.addEventListener("keyup", (e) => { caps.textContent = e.getModifierState && e.getModifierState("CapsLock") ? "Caps Lock is on." : ""; });
  pass.addEventListener("blur", () => { caps.textContent = ""; });

  const form = h("form", { novalidate: true, onsubmit: async (e) => {
    e.preventDefault();
    msg.replaceChildren(); setFieldError("u"); setFieldError("p");
    const u = user.value.trim();
    if (!u) { setFieldError("u", "Enter your username."); user.focus(); return; }
    if (!pass.value) { setFieldError("p", "Enter your password."); pass.focus(); return; }
    btn.disabled = true; setBtn("Signing in…", false);
    try { await onLogin(u, pass.value); }
    catch (ex) { msg.replaceChildren(alertBox(ex)); pass.value = ""; pass.focus(); }
    finally { btn.disabled = false; setBtn("Sign in", true); }
  } }, msg, field("u", "Username", user), field("p", "Password", h("div", { class: "pw-wrap" }, pass, toggle)), caps, btn);

  const tower = h("div", { class: "hero-tilt" }, byteTower(8, { animate: true }));
  pointerTilt(tower, 14);

  const node = h("div", { class: "login" },
    h("div", { class: "login-bg", "aria-hidden": "true" },
      h("div", { class: "orb o1", "data-depth": "-30" }),
      h("div", { class: "orb o2", "data-depth": "40" }),
      h("div", { class: "hero-floor" }, h("div", { class: "hero-floor-grid" })),
      h("div", { class: "hero-trace-wrap" },
        hs("svg", { class: "hero-trace", viewBox: "0 0 1200 200", preserveAspectRatio: "none" },
          hs("polyline", { points: "0,120 150,120 190,40 250,170 320,70 380,120 560,120 600,30 660,180 730,80 790,120 1000,120 1040,50 1100,150 1200,120" })))),
    h("div", { class: "login-shell" },
      h("section", { class: "login-intro", "aria-labelledby": "login-title" },
        h("div", { class: "login-brand" },
          hs("svg", { viewBox: "0 0 32 32", width: 32, height: 32, "aria-hidden": "true" },
            hs("polyline", { class: "brand-trace", points: "2,22 8,22 11,8 15,25 19,12 22,22 30,22" })),
          h("span", {}, "SideWatch")),
        h("div", { class: "login-visual", "data-depth": "-14" }, tower),
        h("p", { class: "eyebrow" }, "Timing leakage measurement lab"),
        h("h1", { id: "login-title", class: "s-title login-title" },
          ["Can a stopwatch", "recover a secret?"].map((t, n) => h("span", { class: "ln" }, h("span", { "data-n": String(n) }, t)))),
        h("p", { class: "login-lead" }, "SideWatch times authentication checks when a guess is partly right, then tests statistically whether those tiny differences give the secret away."),
        h("ul", { class: "login-points" }, POINTS.map(([ic, title, text]) =>
          h("li", {}, h("span", { class: "login-ico" }, icon(ic)), h("span", {}, h("strong", {}, title), h("span", {}, text))))),
        h("p", { class: "fine" }, "A local teaching lab. It measures simulated comparisons on this machine only and is not a scanner for real systems.")),
      h("section", { class: "login-card", "aria-labelledby": "login-head" },
        h("div", { class: "login-card-head" },
          h("span", { class: "login-badge" }, icon("lock")),
          h("div", {}, h("h2", { id: "login-head" }, "Welcome back"), h("p", {}, "Sign in to open your lab."))),
        form,
        h("div", { class: "login-foot" },
          h("p", { class: "fine" }, "Accounts are created by an administrator."),
          h("ul", { class: "login-assure", "aria-label": "Security features" },
            ["Sessions expire automatically", "Attempts are rate-limited", "Activity is audited"].map((t) => h("li", {}, t)))))));
  node.querySelectorAll(".ln > span").forEach((s) => s.style.setProperty("--n", s.dataset.n));
  requestAnimationFrame(() => enhance(node));   // parallax and entrance, once the page is on screen
  return node;
}