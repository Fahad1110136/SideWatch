import hashlib
import json

from fastapi.testclient import TestClient

from backend.app.core.enums import Role
from backend.app.main import app
from backend.app.repositories import audit_repo, submission_repo as sr, user_repo
from backend.app.schemas.submission import SubmissionCreate

PW = "CorrectHorse123"
GOOD = dict(label="Run 1", implementation="vulnerable", fixture_id="no_match", sample_size=100)
RESULT = dict(decision="leak_detected", severity="high", confidence=0.99,
              evidence={"samples": 100, "api_token": "secret-value"},
              reasons=["x"], rule_name="welch", rule_version="1", engine_version="1",
              thresholds={"alpha": 0.01})


def make(db, name, role):
    return user_repo.create_user(db, name, PW, role)


def login(c, name):
    return c.post("/api/auth/login", json={"username": name, "password": PW})


def hdr(r):
    return {"X-CSRF-Token": r.json()["csrf_token"]}


def completed(db, user):
    sub = sr.create(db, user.id, SubmissionCreate(**GOOD))
    sr.save_result(db, sub.id, RESULT)
    return sub


def api_run(client, name):
    h = hdr(login(client, name))
    return client.post("/api/submissions", headers=h, json=GOOD).json()["id"]


def test_operator_exports_sanitized_report(client, api_db):
    alice = make(api_db, "alice", Role.OPERATOR)
    sub_id = api_run(client, "alice")
    r = client.get(f"/api/submissions/{sub_id}/report")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    body = r.json()
    assert body["result"]["decision"] in {
        "leak_detected",
        "no_leak_detected",
        "inconclusive",
    }
    assert body["result"]["reasons"]
    assert body["evidence_links"]["result_id"]
    actions = [e["action"] for e in body["evidence_links"]["audit_events"]]
    assert actions == ["submission.create", "submission.run"]
    assert alice.id not in r.text and "testclient" not in r.text and "password" not in r.text


def test_report_redacts_evidence_secrets(client, api_db):
    alice = make(api_db, "alice", Role.OPERATOR)
    sub = completed(api_db, alice)
    login(client, "alice")
    r = client.get(f"/api/submissions/{sub.id}/report")
    assert "secret-value" not in r.text
    assert r.json()["result"]["evidence"]["api_token"] == "[REDACTED]"


def test_report_digest_matches_content(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    sub_id = api_run(client, "alice")
    body = client.get(f"/api/submissions/{sub_id}/report").json()
    digest = body["integrity"]["report_digest"]
    del body["integrity"]
    recomputed = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert recomputed == digest


def test_export_is_audited_with_digest(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    sub_id = api_run(client, "alice")
    digest = client.get(f"/api/submissions/{sub_id}/report").json()["integrity"]["report_digest"]
    ev = audit_repo.list_events(api_db, action="report.export", outcome="success")
    assert len(ev) == 1 and ev[0].details["report_digest"] == digest
    assert ev[0].resource_id == sub_id


def test_other_operator_cannot_export(client, api_db):
    alice = make(api_db, "alice", Role.OPERATOR)
    make(api_db, "bob_1", Role.OPERATOR)
    sub = completed(api_db, alice)
    bob = TestClient(app)
    login(bob, "bob_1")
    assert bob.get(f"/api/submissions/{sub.id}/report").status_code == 404
    assert audit_repo.list_events(api_db, action="security.access_denied", outcome="denied")
    assert audit_repo.list_events(api_db, action="report.export") == []


def test_report_needs_completed_result(client, api_db):
    alice = make(api_db, "alice", Role.OPERATOR)
    queued = sr.create(api_db, alice.id, SubmissionCreate(**GOOD))
    login(client, "alice")
    assert client.get(f"/api/submissions/{queued.id}/report").status_code == 404


def test_viewer_can_export_completed(client, api_db):
    alice = make(api_db, "alice", Role.OPERATOR)
    make(api_db, "vera", Role.VIEWER)
    sub = completed(api_db, alice)
    login(client, "vera")
    assert client.get(f"/api/submissions/{sub.id}/report").status_code == 200


def test_export_requires_login(client):
    r = client.get(f"/api/submissions/{'0' * 32}/report")
    assert r.status_code == 401 and r.json()["code"] == "AUTH_REQUIRED"