from fastapi.testclient import TestClient

from backend.app.core.enums import Role
from backend.app.main import app
from backend.app.repositories import audit_repo, user_repo

PW = "CorrectHorse123"
BAD = "WrongPassword999"


def make(db, name, role):
    return user_repo.create_user(db, name, PW, role)


def login(c, name, pw=PW):
    return c.post("/api/auth/login", json={"username": name, "password": pw})


def csrf(r):
    return {"X-CSRF-Token": r.json()["csrf_token"]}


def test_login_sets_httponly_cookie_and_hides_hashes(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    r = login(client, "alice")
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()
    assert "password_hash" not in r.text and r.json()["user"]["role"] == "operator"


def test_unknown_user_and_wrong_password_look_identical(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    a, b = login(client, "alice", BAD), login(client, "nobody", BAD)
    assert a.status_code == b.status_code == 401
    assert a.json()["code"] == b.json()["code"] == "AUTH_INVALID_CREDENTIALS"
    assert a.json()["message"] == b.json()["message"]


def test_lockout_blocks_even_correct_password(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    for _ in range(5):
        login(client, "alice", BAD)
    r = login(client, "alice")
    assert r.status_code == 423 and r.json()["code"] == "AUTH_ACCOUNT_LOCKED"


def test_protected_route_requires_login(client):
    assert client.get("/api/auth/me").json()["code"] == "AUTH_REQUIRED"


def test_logout_revokes_session(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    r = login(client, "alice")
    assert client.post("/api/auth/logout", headers=csrf(r)).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_state_changing_request_needs_csrf(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    login(client, "alice")
    r = client.post("/api/auth/logout")
    assert r.status_code == 403 and r.json()["code"] == "CSRF_FAILED"
    assert client.get("/api/auth/me").status_code == 200


def test_operator_cannot_create_users_and_attempt_is_logged(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    r = login(client, "alice")
    resp = client.post("/api/users", headers=csrf(r),
                       json={"username": "eve_1", "password": PW, "role": "admin"})
    assert resp.status_code == 403 and resp.json()["code"] == "ACCESS_DENIED"
    assert user_repo.get_by_username(api_db, "eve_1") is None
    assert audit_repo.list_events(api_db, action="security.access_denied", outcome="denied")


def test_admin_creates_user_duplicate_and_weak_password(client, api_db):
    make(api_db, "root_admin", Role.ADMIN)
    h = csrf(login(client, "root_admin"))
    ok = client.post("/api/users", headers=h,
                     json={"username": "bob_1", "password": PW, "role": "viewer"})
    assert ok.status_code == 201 and ok.json()["role"] == "viewer"
    dup = client.post("/api/users", headers=h,
                      json={"username": "BOB_1", "password": PW, "role": "viewer"})
    assert dup.status_code == 409 and dup.json()["code"] == "USER_EXISTS"
    weak = client.post("/api/users", headers=h,
                       json={"username": "carol", "password": "short1", "role": "viewer"})
    assert weak.status_code == 422


def test_deactivating_user_kills_their_sessions(client, api_db):
    make(api_db, "root_admin", Role.ADMIN)
    alice = make(api_db, "alice", Role.OPERATOR)
    r = login(client, "root_admin")
    other = TestClient(app)
    login(other, "alice")
    assert other.get("/api/auth/me").status_code == 200
    resp = client.patch(f"/api/users/{alice.id}/active", headers=csrf(r),
                        json={"is_active": False})
    assert resp.status_code == 200
    assert other.get("/api/auth/me").status_code == 401
    assert login(other, "alice").status_code == 401


def test_admin_cannot_deactivate_self(client, api_db):
    admin = make(api_db, "root_admin", Role.ADMIN)
    r = login(client, "root_admin")
    resp = client.patch(f"/api/users/{admin.id}/active", headers=csrf(r),
                        json={"is_active": False})
    assert resp.status_code == 400 and resp.json()["code"] == "INVALID_OPERATION"


def test_audit_log_is_admin_only_and_verifiable(client, api_db):
    make(api_db, "root_admin", Role.ADMIN)
    make(api_db, "alice", Role.OPERATOR)
    op = TestClient(app)
    login(op, "alice")
    assert op.get("/api/audit").status_code == 403
    login(client, "root_admin")
    assert client.get("/api/audit").status_code == 200
    assert client.get("/api/audit/verify").json()["intact"] is True


def test_logins_are_audited_without_passwords(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    login(client, "alice", BAD)
    login(client, "alice")
    assert len(audit_repo.list_events(api_db, action="auth.login", outcome="failure")) == 1
    assert len(audit_repo.list_events(api_db, action="auth.login", outcome="success")) == 1
    assert BAD not in str([e.details for e in audit_repo.list_events(api_db)])


def test_login_is_rate_limited(client):
    codes = [login(client, f"ghost{i}").status_code for i in range(12)]
    assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]