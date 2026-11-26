import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / "frontend"
CONFIG = (FRONT / "js" / "config.js").read_text(encoding="utf-8")
API_JS = (FRONT / "js" / "api.js").read_text(encoding="utf-8")
APP_JS = (FRONT / "js" / "app.js").read_text(encoding="utf-8")


def _js_object_keys(name: str) -> list[str]:
    body = re.search(rf"export const {name} = \{{(.*?)\n\}};", CONFIG, re.S).group(1)
    return re.findall(r"^\s{2}(\w+):", body, re.M)


def test_ui_fixtures_match_engine_whitelist():
    from engine.fixtures import FIXTURES
    assert set(_js_object_keys("FIXTURES")) == set(FIXTURES)


def test_ui_prefix_lengths_match_engine():
    from engine.fixtures import FIXTURES
    for fid, prefix in re.findall(r"^\s{2}(\w+):\s*\{[^}]*prefix: (\d+)", CONFIG, re.M):
        assert FIXTURES[fid].matching_prefix_bytes == int(prefix), fid


def test_ui_limits_match_backend_schema():
    src = (ROOT / "backend/app/schemas/submission.py").read_text(encoding="utf-8")
    live = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "ge=30, le=5000" in live and "ge=0, le=500" in live and "le=2**31 - 1" in live
    assert re.search(r"sample_size: \{ min: 30, max: 5000", CONFIG)
    assert re.search(r"warmup_runs: \{ min: 0, max: 500", CONFIG)
    assert "2 ** 31 - 1" in CONFIG


def test_ui_rule_bounds_match_rule_repo():
    src = (ROOT / "backend/app/repositories/rule_repo.py").read_text(encoding="utf-8")
    bounds = ast.literal_eval(re.search(r"^BOUNDS = (\{.*\})", src, re.M).group(1))
    js = re.search(r"RULE_BOUNDS = \{(.*?)\};", CONFIG).group(1)
    for key, (lo, hi) in bounds.items():
        m = re.search(rf"{key}: \[([\d.]+), ([\d.]+)\]", js)
        assert m and (float(m[1]), float(m[2])) == (lo, hi), key


def test_every_api_call_targets_a_real_backend_route():
    backend = "\n".join(
        (ROOT / "backend/app/api" / f).read_text(encoding="utf-8")
        for f in ("auth.py", "users.py", "audit.py", "rules.py", "submissions.py")
    )
    prefixes = set(re.findall(r'APIRouter\(prefix="(/api/[a-z]+)"', backend))
    called = set(re.findall(r"/api/[a-z]+", API_JS))
    assert called, "api.js makes no calls?"
    assert called <= prefixes, called - prefixes


def test_state_changing_requests_send_csrf_and_rule_changes_confirm():
    assert '"X-CSRF-Token"' in API_JS and 'new Set(["POST", "PUT", "PATCH", "DELETE"])' in API_JS
    assert re.search(r"updateRule.*confirm: true", API_JS)
    assert re.search(r"resetPassword.*confirm: true", API_JS)


def test_admin_screens_are_not_routable_by_other_roles():
    routes = dict(re.findall(r"^\s+(\w+): \{ roles: (\[[^\]]*\])", APP_JS, re.M))
    for admin_only in ("users", "audit"):
        assert json.loads(routes[admin_only]) == ["admin"]
    assert "viewer" not in json.loads(routes["run"])
    assert "viewer" not in json.loads(routes["rules"])


def test_no_third_party_hosts_or_inline_handlers_in_scripts():
    for js in (FRONT / "js").rglob("*.js"):
        src = js.read_text(encoding="utf-8")
        assert not re.search(r"https?://(?!www\.w3\.org)", src), js.name
        assert "setAttribute(\"on" not in src and "javascript:" not in src, js.name


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_every_script_parses():
    for js in sorted((FRONT / "js").rglob("*.js")):
        r = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True)
        assert r.returncode == 0, f"{js.name}: {r.stderr}"


def test_result_screen_shows_every_proposal_dashboard_field():
    result = (FRONT / "js/pages/result.js").read_text(encoding="utf-8")
    for needle in ("r.severity", "r.confidence", "ev.", "r.reasons", "Export report", "window.print"):
        assert needle in result, needle


def test_history_offers_the_required_filters():
    hist = (FRONT / "js/pages/history.js").read_text(encoding="utf-8")
    for needle in ('"f-impl"', '"f-status"', '"f-decision"', '"f-severity"', '"f-search"'):
        assert needle in hist, needle


def test_print_stylesheet_hides_chrome():
    css = (FRONT / "css/style.css").read_text(encoding="utf-8")
    assert "@media print" in css and ".top" in css.split("@media print")[1]


def test_effects_module_is_wired_in_and_respects_reduced_motion():
    fx = (FRONT / "js/fx.js").read_text(encoding="utf-8")
    css = (FRONT / "css/style.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in fx and "prefers-reduced-motion: reduce" in css
    assert 'from "./fx.js"' in APP_JS and "initFx()" in APP_JS and "enhance(node)" in APP_JS
    assert "@media print" in css and any(".reveal" in part for part in css.split("@media print")[1:])


def test_home_is_named_home_and_tells_a_story():
    home = (FRONT / "js/pages/home.js").read_text(encoding="utf-8")
    assert 'label: "Home"' in APP_JS and "Overview" not in APP_JS and 'data-title": "Home"' in home
    assert "CHAPTERS" in home and "storyScroll" in home and "pointerTilt" in home
    assert "storyStrip(name)" in APP_JS and "nextBar(current)" in APP_JS


def test_parallax_and_story_styles_exist_with_print_fallback():
    css = (FRONT / "css/style.css").read_text(encoding="utf-8")
    fx = (FRONT / "js/fx.js").read_text(encoding="utf-8")
    assert "data-speed" in fx and "data-depth" in fx
    for needle in (".story-stage", ".chapter-card", ".next-bar", ".story-strip", ".s-hero"):
        assert needle in css, needle
    assert ".story-stage" in css.split("@media print")[-1]