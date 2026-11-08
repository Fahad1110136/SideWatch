def test_frontend_served_with_page_csp(client):
    r = client.get("/")
    assert r.status_code == 200 and "SideWatch" in r.text
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "default-src 'none'" not in csp
    assert r.headers["x-frame-options"] == "DENY"


def test_api_keeps_strict_csp(client):
    assert "default-src 'none'" in client.get("/api/health").headers["content-security-policy"]


def test_project_files_are_not_served(client):
    for path in ("/.env", "/requirements.txt", "/data/sidewatch.db"):
        r = client.get(path)
        assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_unknown_api_path_is_json_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"

# ---- Member C: static interface checks (the page CSP forbids inline script/style) ----
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def test_interface_assets_are_served(client):
    for path in ("/css/style.css", "/js/app.js", "/js/api.js", "/js/pages/result.js"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "script-src 'self'" in r.headers["content-security-policy"]


def test_index_has_no_inline_script_style_or_handlers():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert "<style" not in html and "style=" not in html
    assert " onclick=" not in html and " onload=" not in html
    assert "<script type=\"module\" src=" in html
    assert 'src="http' not in html and 'href="http' not in html     # no CDN or external hosts


def test_interface_code_never_writes_raw_html():
    """Server text is rendered with textContent only, so it can never inject markup."""
    for js in (FRONTEND / "js").rglob("*.js"):
        src = js.read_text(encoding="utf-8")
        for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "localStorage", "sessionStorage"):
            assert banned not in src, f"{js.name} uses {banned}"
