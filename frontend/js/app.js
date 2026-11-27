import { api } from "./api.js";
import { h, hs, errorText, alertBox, spinner, skeleton, badge } from "./ui.js";
import { enhance, initFx } from "./fx.js";
import { loginPage } from "./pages/login.js";
import { homePage } from "./pages/home.js";
import { runPage } from "./pages/run.js";
import { resultPage, comparePage, sweepPage } from "./pages/result.js";
import { historyPage } from "./pages/history.js";
import { rulesPage, usersPage, auditPage, accountPage } from "./pages/admin.js";

const root = document.getElementById("root");
let user = null;      // {id, username, role} - a UI hint only. The SERVER enforces every permission.
let main = null;

const NAV = [
  { path: "", label: "Home", roles: ["admin", "operator", "viewer"] },
  { path: "run", label: "New measurement", roles: ["admin", "operator"] },
  { path: "history", label: "History", roles: ["admin", "operator", "viewer"] },
  { path: "rules", label: "Rules", roles: ["admin", "operator"] },
  { path: "users", label: "Users", roles: ["admin"] },
  { path: "audit", label: "Audit log", roles: ["admin"] },
];
const ROUTES = {
  "": { roles: ["admin", "operator", "viewer"], page: homePage },
  run: { roles: ["admin", "operator"], page: runPage },
  results: { roles: ["admin", "operator", "viewer"], page: resultPage },
  compare: { roles: ["admin", "operator", "viewer"], page: comparePage },
  sweep: { roles: ["admin", "operator", "viewer"], page: sweepPage },
  history: { roles: ["admin", "operator", "viewer"], page: historyPage },
  rules: { roles: ["admin", "operator"], page: rulesPage },
  users: { roles: ["admin"], page: usersPage },
  audit: { roles: ["admin"], page: auditPage },
  account: { roles: ["admin", "operator", "viewer"], page: accountPage },
};

// Storytelling: where each page sits in the workflow, and one sentence of narrative for it.
const FLOW = ["Learn", "Measure", "Decide", "Review", "Tune", "Govern"];
const STORY = {
  run: [2, "Choose what to test and how hard to look. Each run is a controlled experiment, so more samples give a tighter answer."],
  results: [3, "Read the verdict from the top: what was found, how sure we are, and the evidence behind it."],
  compare: [3, "Put two runs side by side to see whether a change, a seed or a fix altered the outcome."],
  sweep: [3, "Watch the gap grow with every correct byte. That growth is the signature of an early-exit comparison."],
  history: [4, "Every measurement is kept, so any verdict can be revisited, filtered and compared."],
  rules: [5, "Thresholds decide what counts as a leak. Changes are versioned, confirmed and recorded."],
  users: [6, "Access follows least privilege: operators measure, viewers read, administrators manage."],
  audit: [6, "Security-relevant actions are chained in an append-only log that you can verify."],
};

function storyStrip(name) {
  const s = STORY[name];
  if (!s) return null;
  return h("aside", { class: "story-strip", "aria-label": "Where you are in the workflow" },
    h("ol", { class: "steps" }, FLOW.map((label, i) =>
      h("li", { class: i + 1 < s[0] ? "done" : i + 1 === s[0] ? "cur" : "", "aria-current": i + 1 === s[0] ? "step" : false }, h("b", {}, String(i + 1)), h("span", {}, label)))),
    h("p", { class: "strip-text" }, s[1]));
}

/** The footer of every page: the next page in the menu, so the story can be followed to the end. */
function nextBar(current) {
  const items = NAV.filter((n) => n.roles.includes(user.role));
  const at = items.findIndex((n) => n.path === current);
  if (at < 0) return null;
  const next = items[at + 1];
  return h("a", { class: "next-bar", href: "#/" + (next ? next.path : "") },
    h("span", {}, h("span", { class: "next-kicker" }, next ? "Continue to" : "You have reached the end"), h("strong", {}, next ? next.label : "Back to Home")),
    h("span", { class: "next-arrow", "aria-hidden": "true" }, next ? "→" : "↑"));
}

export const navigate = (path) => { location.hash = "#/" + path.replace(/^\//, ""); };

function showLogin(message) {
  user = null;
  main = null;
  root.replaceChildren(loginPage({
    message,
    onLogin: async (username, password) => {
      user = await api.login(username, password);
      location.hash = "";
      startApp();
    },
  }));
}

function shell() {
  const nav = h("nav", { class: "topnav", "aria-label": "Main", id: "nav" });
  main = h("main", { id: "main", tabindex: "-1" });
  const logout = h("button", { class: "btn btn-quiet", type: "button", onclick: async () => {
    try { await api.logout(); } catch { /* session may already be gone */ }
    location.hash = "";
    showLogin();
  } }, "Sign out");
  root.replaceChildren(
    h("header", { class: "top" },
      h("div", { class: "top-in" },
        h("a", { class: "brand", href: "#/" },
          hs("svg", { viewBox: "0 0 32 32", width: 26, height: 26, "aria-hidden": "true" },
            hs("polyline", { class: "brand-trace", points: "2,22 8,22 11,8 15,25 19,12 22,22 30,22" })), "SideWatch"),
        nav,
        h("div", { class: "me" },
          h("a", { class: "me-link", href: "#/account", title: "Account settings" }, user.username),
          badge(user.role, "role"), logout))),
    main);
}

function renderNav(current) {
  const nav = document.getElementById("nav");
  nav.replaceChildren(...NAV.filter((n) => n.roles.includes(user.role)).map((n) =>
    h("a", { href: "#/" + n.path, "aria-current": n.path === current ? "page" : false }, n.label)));
}

let routeToken = 0;
async function route() {
  if (!user || !main) return;
  const token = ++routeToken;
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const name = parts[0] || "";
  const def = ROUTES[name];
  if (!def) { navigate(""); return; }
  if (!def.roles.includes(user.role)) { navigate(""); return; }
  const current = ["results", "compare", "sweep"].includes(name) ? "history" : name;
  renderNav(current);
  main.replaceChildren(skeleton());
  try {
    const node = await def.page({ user, args: parts.slice(1).map(decodeURIComponent), navigate });
    if (token !== routeToken || !main) return;  // user moved on (or signed out) while we were loading
    const strip = storyStrip(name), head = node.querySelector(".page-head");
    if (strip) { if (head) head.after(strip); else node.prepend(strip); }
    const bar = nextBar(current);
    if (bar) node.append(bar);
    main.replaceChildren(node);
    enhance(node);
    main.focus({ preventScroll: true });
    window.scrollTo(0, 0);
    document.title = (node.dataset?.title ? node.dataset.title + " · " : "") + "SideWatch";
  } catch (ex) {
    if (token !== routeToken || !main) return;  // e.g. the session expired and the login page took over
    main.replaceChildren(alertBox(ex));
    if (ex.status === 404) main.append(h("p", {}, h("a", { href: "#/history" }, "Back to history")));
  }
}

function startApp() {
  shell();
  if (!location.hash || location.hash === "#") location.hash = "#/";
  route();
}

initFx();
window.addEventListener("hashchange", route);
window.addEventListener("sw:unauthenticated", () => { if (user) showLogin("Your session ended. Please sign in again."); });

// Resume an existing server session after a page reload.
(async () => {
  root.replaceChildren(spinner("Checking your session…"));
  try {
    user = await api.me();
    await api.refreshCsrf();
    startApp();
  } catch (ex) {
    showLogin(ex.status === 0 ? errorText(ex) : undefined);
  }
})();
