from fastapi.testclient import TestClient

from backend.app.core.enums import Role
from backend.app.main import app
from backend.app.repositories import audit_repo, rule_repo, user_repo

PW = "CorrectHorse123"
GOOD = dict(label="Run 1", implementation="vulnerable", fixture_id="no_match", sample_size=100)


def make(db, name, role):
    return user_repo.create_user(db, name, PW, role)


def login(c, name):
    return c.post("/api/auth/login", json={"username": name, "password": PW})


def hdr(r):
    return {"X-CSRF-Token": r.json()["csrf_token"]}


def test_admin_changes_rule_and_it_is_traceable(client, api_db):
    rule_repo.seed_defaults(api_db)
    make(api_db, "root_admin", Role.ADMIN)
    h = hdr(login(client, "root_admin"))
    r = client.put("/api/rules/alpha", headers=h, json={"value": 0.05, "confirm": True})
    assert r.status_code == 200 and r.json()["value"] == 0.05 and r.json()["version"] == 2
    ev = audit_repo.list_events(api_db, action="admin.rule_change", outcome="success")[0]
    assert ev.details["old"] == 0.01 and ev.details["new"] == 0.05
    run = client.post("/api/submissions", headers=h, json=GOOD).json()
    result = client.get(f"/api/submissions/{run['id']}/result").json()
    assert result["thresholds"]["alpha"] == 0.05


def test_rule_change_requires_confirmation(client, api_db):
    rule_repo.seed_defaults(api_db)
    make(api_db, "root_admin", Role.ADMIN)
    h = hdr(login(client, "root_admin"))
    r = client.put("/api/rules/alpha", headers=h, json={"value": 0.05, "confirm": False})
    assert r.status_code == 400 and r.json()["code"] == "CONFIRMATION_REQUIRED"
    assert rule_repo.get_all(api_db)["alpha"] == 0.01


def test_rule_out_of_range_rejected(client, api_db):
    rule_repo.seed_defaults(api_db)
    make(api_db, "root_admin", Role.ADMIN)
    h = hdr(login(client, "root_admin"))
    r = client.put("/api/rules/alpha", headers=h, json={"value": 0.9, "confirm": True})
    assert r.status_code == 422 and r.json()["code"] == "INVALID_RULE_VALUE"
    assert rule_repo.get_all(api_db)["alpha"] == 0.01


def test_operator_can_read_but_not_change_rules(client, api_db):
    rule_repo.seed_defaults(api_db)
    make(api_db, "alice", Role.OPERATOR)
    h = hdr(login(client, "alice"))
    assert client.get("/api/rules").status_code == 200
    r = client.put("/api/rules/alpha", headers=h, json={"value": 0.05, "confirm": True})
    assert r.status_code == 403 and r.json()["code"] == "ACCESS_DENIED"
    assert rule_repo.get_all(api_db)["alpha"] == 0.01


def test_unknown_rule_key_is_404(client, api_db):
    rule_repo.seed_defaults(api_db)
    make(api_db, "root_admin", Role.ADMIN)
    h = hdr(login(client, "root_admin"))
    r = client.put("/api/rules/drop_table", headers=h, json={"value": 1, "confirm": True})
    assert r.status_code == 404