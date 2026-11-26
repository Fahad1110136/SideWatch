"""Adversarial checks for actual body size and session-bound CSRF tokens."""

import asyncio
import json

from fastapi.testclient import TestClient
import pytest

from backend.app.core.enums import Role
from backend.app.core.middleware import BodySizeLimitMiddleware
from backend.app.main import app
from backend.app.repositories import audit_repo, submission_repo, user_repo


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"1")]])
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_actual_oversized_stream_rejected_before_downstream(headers, method):
    messages, reached = [], []
    chunks = iter([b"a" * 6, b"b" * 6])

    async def receive():
        body = next(chunks)
        return {"type": "http.request", "body": body, "more_body": body.startswith(b"a")}

    async def send(message):
        messages.append(message)

    async def inner(scope, receive, send):
        reached.append(True)

    scope = dict(type="http", method=method, path="/", headers=headers)
    asyncio.run(BodySizeLimitMiddleware(inner, max_bytes=10)(scope, receive, send))
    assert not reached
    assert messages[0]["status"] == 413
    assert json.loads(messages[1]["body"])["code"] == "REQUEST_TOO_LARGE"


def test_exact_limit_multichunk_body_reaches_downstream_unchanged():
    chunks = iter([b"12345", b"67890"])
    received = bytearray()

    async def receive():
        body = next(chunks)
        return dict(type="http.request", body=body, more_body=body == b"12345")

    async def send(message):
        pass

    async def inner(scope, receive, send):
        while True:
            message = await receive()
            received.extend(message["body"])
            if not message.get("more_body", False):
                break

    scope = dict(type="http", method="POST", path="/", headers=[(b"content-length", b"10")])
    asyncio.run(BodySizeLimitMiddleware(inner, max_bytes=10)(scope, receive, send))
    assert received == b"1234567890"


def test_csrf_token_from_another_session_cannot_submit(client, api_db):
    user = user_repo.create_user(api_db, "analyst", "CorrectHorse123", Role.OPERATOR)
    first = client.post("/api/auth/login", json=dict(username=user.username, password="CorrectHorse123"))
    second = TestClient(app)
    try:
        second_login = second.post("/api/auth/login", json=dict(username=user.username, password="CorrectHorse123"))
        payload = dict(label="CSRF check", implementation="vulnerable", fixture_id="no_match", sample_size=30)
        denied = second.post("/api/submissions", json=payload,
                             headers={"X-CSRF-Token": first.json()["csrf_token"]})
        assert denied.status_code == 403 and denied.json()["code"] == "CSRF_FAILED"
        assert submission_repo.list_submissions(api_db) == []
        events = audit_repo.list_events(api_db, action="security.csrf_failed", outcome="denied")
        assert len(events) == 1 and events[0].actor_id == user.id
        allowed = second.post("/api/submissions", json=payload,
                              headers={"X-CSRF-Token": second_login.json()["csrf_token"]})
        assert allowed.status_code == 201 and allowed.json()["status"] == "completed"
    finally:
        second.close()
