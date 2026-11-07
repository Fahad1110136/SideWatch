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