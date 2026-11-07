import asyncio

from backend.app.core.middleware import BodySizeLimitMiddleware


def test_security_headers_on_api_responses(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "no-store" in r.headers["cache-control"]
    assert "default-src 'none'" in r.headers["content-security-policy"]


def test_docs_page_not_blocked_by_csp(client):
    r = client.get("/api/docs")
    assert r.status_code == 200
    assert "content-security-policy" not in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


def test_oversized_body_rejected_413(client):
    r = client.post("/api/auth/login", content=b"x" * 70000,
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["code"] == "REQUEST_TOO_LARGE"
    assert "Traceback" not in r.text
    assert r.headers["x-content-type-options"] == "nosniff"


def test_normal_sized_body_still_accepted(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "whatever123"})
    assert r.status_code == 401


def test_chunked_body_without_length_rejected_411():
    reached, messages = [], []

    async def inner(scope, receive, send):
        reached.append(True)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {"type": "http", "method": "POST", "path": "/x",
             "headers": [(b"transfer-encoding", b"chunked")]}
    asyncio.run(BodySizeLimitMiddleware(inner, max_bytes=100)(scope, receive, send))
    assert messages[0]["status"] == 411 and reached == []