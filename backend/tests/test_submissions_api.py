from fastapi.testclient import TestClient

from backend.app.core.enums import Role
from backend.app.main import app
from backend.app.repositories import audit_repo, submission_repo as sr, user_repo
from backend.app.schemas.submission import SubmissionCreate
from engine import interface as engine_interface

PW = "CorrectHorse123"
GOOD = dict(label="Run 1", implementation="vulnerable", fixture_id="no_match", sample_size=100)
RESULT = dict(decision="leak_detected", severity="high", confidence=0.99, evidence={},
              reasons=["x"], rule_name="welch", rule_version="1", engine_version="1",
              thresholds={"alpha": 0.01})


def make(db, name, role):
    return user_repo.create_user(db, name, PW, role)


def login(c, name):
    return c.post("/api/auth/login", json={"username": name, "password": PW})


def hdr(r):
    return {"X-CSRF-Token": r.json()["csrf_token"]}


def direct(db, user, **over):
    return sr.create(db, user.id, SubmissionCreate(**{**GOOD, **over}))


def test_operator_runs_submission_and_gets_explainable_result(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    h = hdr(login(client, "alice"))
    r = client.post("/api/submissions", headers=h, json=GOOD)
    assert r.status_code == 201 and r.json()["status"] == "completed"
    res = client.get(f"/api/submissions/{r.json()['id']}/result")
    body = res.json()
    assert res.status_code == 200 and body["decision"] == "leak_detected"
    assert body["reasons"] and body["rule_name"] and body["thresholds"]["alpha"] == 0.01
    assert audit_repo.list_events(api_db, action="submission.run", outcome="success")


def test_unknown_fixture_rejected_and_audited(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    h = hdr(login(client, "alice"))
    r = client.post("/api/submissions", headers=h, json={**GOOD, "fixture_id": "not_in_whitelist"})
    assert r.status_code == 422 and r.json()["code"] == "INVALID_FIXTURE"
    assert sr.list_submissions(api_db) == []
    assert audit_repo.list_events(api_db, action="submission.create", outcome="failure")


def test_viewer_cannot_submit(client, api_db):
    make(api_db, "vera", Role.VIEWER)
    h = hdr(login(client, "vera"))
    r = client.post("/api/submissions", headers=h, json=GOOD)
    assert r.status_code == 403 and r.json()["code"] == "ACCESS_DENIED"
    assert sr.list_submissions(api_db) == []
    assert audit_repo.list_events(api_db, action="security.access_denied")


def test_submit_requires_csrf(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    login(client, "alice")
    r = client.post("/api/submissions", json=GOOD)
    assert r.status_code == 403 and r.json()["code"] == "CSRF_FAILED"


def test_invalid_input_rejected(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    h = hdr(login(client, "alice"))
    assert client.post("/api/submissions", headers=h, json={**GOOD, "is_admin": True}).status_code == 422
    assert client.post("/api/submissions", headers=h, json={**GOOD, "sample_size": 10}).status_code == 422
    assert client.post("/api/submissions", headers=h, json={**GOOD, "sample_size": 999999}).status_code == 422
    assert sr.list_submissions(api_db) == []


def test_operator_cannot_read_others_submission(client, api_db):
    alice = make(api_db, "alice", Role.OPERATOR)
    make(api_db, "bob_1", Role.OPERATOR)
    sub = direct(api_db, alice)
    bob = TestClient(app)
    login(bob, "bob_1")
    hidden = bob.get(f"/api/submissions/{sub.id}")
    missing = bob.get("/api/submissions/" + "0" * 32)
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json()["code"] == missing.json()["code"] == "NOT_FOUND"
    assert bob.get(f"/api/submissions/{sub.id}/result").status_code == 404
    assert audit_repo.list_events(api_db, action="security.access_denied", outcome="denied")


def test_admin_sees_all_operator_sees_own(client, api_db):
    alice = make(api_db, "alice", Role.OPERATOR)
    bob = make(api_db, "bob_1", Role.OPERATOR)
    make(api_db, "root_admin", Role.ADMIN)
    direct(api_db, alice)
    direct(api_db, bob)
    login(client, "alice")
    assert len(client.get("/api/submissions").json()) == 1
    admin = TestClient(app)
    login(admin, "root_admin")
    assert len(admin.get("/api/submissions").json()) == 2


def test_viewer_sees_only_completed_and_can_read_result(client, api_db):
    alice = make(api_db, "alice", Role.OPERATOR)
    make(api_db, "vera", Role.VIEWER)
    queued = direct(api_db, alice)
    done = direct(api_db, alice)
    sr.save_result(api_db, done.id, RESULT)
    login(client, "vera")
    ids = [s["id"] for s in client.get("/api/submissions").json()]
    assert ids == [done.id]
    assert client.get(f"/api/submissions/{done.id}/result").status_code == 200
    assert client.get(f"/api/submissions/{queued.id}").status_code == 404


def test_filters(client, api_db):
    alice = make(api_db, "alice", Role.OPERATOR)
    direct(api_db, alice, implementation="vulnerable")
    direct(api_db, alice, implementation="constant_time")
    login(client, "alice")
    assert len(client.get("/api/submissions?implementation=constant_time").json()) == 1
    assert client.get("/api/submissions?status=completed").json() == []
    assert client.get("/api/submissions?status=bogus").status_code == 422


def test_engine_crash_fails_safely(client, api_db, monkeypatch):
    def boom(req):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(engine_interface, "run_analysis", boom)
    make(api_db, "alice", Role.OPERATOR)
    h = hdr(login(client, "alice"))
    r = client.post("/api/submissions", headers=h, json=GOOD)
    assert r.status_code == 201
    assert r.json()["status"] == "failed" and r.json()["error_code"] == "ENGINE_FAILED"
    assert "secret internal detail" not in r.text
    assert client.get(f"/api/submissions/{r.json()['id']}/result").status_code == 404


def test_malformed_engine_output_fails_safely(client, api_db, monkeypatch):
    real = engine_interface.run_analysis
    monkeypatch.setattr(engine_interface, "run_analysis", lambda req: {**real(req), "reasons": []})
    make(api_db, "alice", Role.OPERATOR)
    h = hdr(login(client, "alice"))
    r = client.post("/api/submissions", headers=h, json=GOOD)
    assert r.json()["status"] == "failed" and r.json()["error_code"] == "ENGINE_FAILED"