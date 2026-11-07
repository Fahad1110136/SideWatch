from fastapi.testclient import TestClient

from backend.app.core.enums import Role
from backend.app.main import app
from backend.app.repositories import audit_repo, user_repo

PW = "CorrectHorse123"
NEW = "BrandNewPass456"
BAD = "WrongPassword999"


def make(db, name, role):
    return user_repo.create_user(db, name, PW, role)


def login(c, name, pw=PW):
    return c.post("/api/auth/login", json={"username": name, "password": pw})


def csrf(r):
    return {"X-CSRF-Token": r.json()["csrf_token"]}


def audit_text(db):
    return str([e.details for e in audit_repo.list_events(db)])


def test_change_password_rotates_everything(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    first = login(client, "alice")
    other = TestClient(app)
    login(other, "alice")
    r = client.post("/api/auth/change-password", headers=csrf(first),
                    json={"current_password": PW, "new_password": NEW})
    assert r.status_code == 200 and r.json()["csrf_token"] != first.json()["csrf_token"]
    assert other.get("/api/auth/me").status_code == 401          # other sessions revoked
    assert client.get("/api/auth/me").status_code == 200         # this one got a fresh session
    assert client.post("/api/auth/logout", headers=csrf(first)).status_code == 403  # old CSRF dead
    assert login(TestClient(app), "alice", PW).status_code == 401
    assert login(TestClient(app), "alice", NEW).status_code == 200
    assert audit_repo.list_events(api_db, action="auth.password_change", outcome="success")


def test_change_password_wrong_current(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    h = csrf(login(client, "alice"))
    r = client.post("/api/auth/change-password", headers=h,
                    json={"current_password": BAD, "new_password": NEW})
    assert r.status_code == 400 and r.json()["code"] == "CURRENT_PASSWORD_INVALID"
    assert login(TestClient(app), "alice", PW).status_code == 200   # unchanged
    assert len(audit_repo.list_events(api_db, action="auth.password_change", outcome="failure")) == 1
    text = audit_text(api_db)
    assert BAD not in text and NEW not in text


def test_change_password_same_password_rejected(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    h = csrf(login(client, "alice"))
    r = client.post("/api/auth/change-password", headers=h,
                    json={"current_password": PW, "new_password": PW})
    assert r.status_code == 422 and r.json()["code"] == "PASSWORD_REUSE"


def test_change_password_weak_new_rejected(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    h = csrf(login(client, "alice"))
    for weak in ("short1", "alllettersnodigits"):
        r = client.post("/api/auth/change-password", headers=h,
                        json={"current_password": PW, "new_password": weak})
        assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ERROR"


def test_change_password_needs_csrf(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    login(client, "alice")
    r = client.post("/api/auth/change-password",
                    json={"current_password": PW, "new_password": NEW})
    assert r.status_code == 403 and r.json()["code"] == "CSRF_FAILED"


def test_change_password_is_rate_limited(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    h = csrf(login(client, "alice"))
    codes = [client.post("/api/auth/change-password", headers=h,
                         json={"current_password": BAD, "new_password": NEW}).status_code
             for _ in range(6)]
    assert codes == [400] * 5 + [429]


def test_admin_reset_revokes_sessions_and_clears_lockout(client, api_db):
    make(api_db, "root_admin", Role.ADMIN)
    alice = make(api_db, "alice", Role.OPERATOR)
    victim = TestClient(app)
    login(victim, "alice")
    for _ in range(5):
        user_repo.register_failed_login(api_db, alice)
    assert user_repo.is_locked(alice)
    h = csrf(login(client, "root_admin"))
    r = client.post(f"/api/users/{alice.id}/reset-password", headers=h,
                    json={"new_password": NEW, "confirm": True})
    assert r.status_code == 200
    assert victim.get("/api/auth/me").status_code == 401
    assert login(TestClient(app), "alice", PW).status_code == 401
    assert login(TestClient(app), "alice", NEW).status_code == 200
    assert audit_repo.list_events(api_db, action="admin.password_reset", outcome="success")
    assert NEW not in audit_text(api_db)


def test_admin_reset_needs_confirmation(client, api_db):
    make(api_db, "root_admin", Role.ADMIN)
    alice = make(api_db, "alice", Role.OPERATOR)
    h = csrf(login(client, "root_admin"))
    r = client.post(f"/api/users/{alice.id}/reset-password", headers=h,
                    json={"new_password": NEW, "confirm": False})
    assert r.status_code == 400 and r.json()["code"] == "CONFIRMATION_REQUIRED"
    assert login(TestClient(app), "alice", PW).status_code == 200


def test_operator_cannot_reset_passwords(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    bob = make(api_db, "bob_1", Role.OPERATOR)
    h = csrf(login(client, "alice"))
    r = client.post(f"/api/users/{bob.id}/reset-password", headers=h,
                    json={"new_password": NEW, "confirm": True})
    assert r.status_code == 403 and r.json()["code"] == "ACCESS_DENIED"
    assert login(TestClient(app), "bob_1", PW).status_code == 200


def test_admin_cannot_reset_own_password(client, api_db):
    admin = make(api_db, "root_admin", Role.ADMIN)
    h = csrf(login(client, "root_admin"))
    r = client.post(f"/api/users/{admin.id}/reset-password", headers=h,
                    json={"new_password": NEW, "confirm": True})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_OPERATION"


def test_reset_unknown_user_is_404(client, api_db):
    make(api_db, "root_admin", Role.ADMIN)
    h = csrf(login(client, "root_admin"))
    r = client.post(f"/api/users/{'0' * 32}/reset-password", headers=h,
                    json={"new_password": NEW, "confirm": True})
    assert r.status_code == 404


def test_csrf_endpoint_rotates_token(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    first = login(client, "alice")
    old = csrf(first)
    new = client.get("/api/auth/csrf").json()["csrf_token"]
    assert new != first.json()["csrf_token"]
    assert client.post("/api/auth/logout", headers=old).status_code == 403
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": new}).status_code == 200


def test_csrf_endpoint_requires_login(client):
    assert client.get("/api/auth/csrf").status_code == 401