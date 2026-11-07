from backend.app.core.enums import Role
from backend.app.repositories import submission_repo as sr, user_repo

PW = "CorrectHorse123"
GOOD = dict(label="Run 1", implementation="vulnerable", fixture_id="no_match", sample_size=100)


def make(db, name, role):
    return user_repo.create_user(db, name, PW, role)


def login(c, name):
    return c.post("/api/auth/login", json={"username": name, "password": PW})


def hdr(r):
    return {"X-CSRF-Token": r.json()["csrf_token"]}


def test_malformed_json_gets_safe_error(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    h = hdr(login(client, "alice"))
    r = client.post("/api/submissions", content=b"{not json",
                    headers={**h, "Content-Type": "application/json"})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ERROR"
    assert "Traceback" not in r.text and "not json" not in r.text


def test_unauthorized_submission_rejected_and_nothing_stored(client, api_db):
    r = client.post("/api/submissions", json=GOOD)
    assert r.status_code == 401 and r.json()["code"] == "AUTH_REQUIRED"
    assert sr.list_submissions(api_db) == []


def test_repeated_submission_creates_separate_runs(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    h = hdr(login(client, "alice"))
    ids = [client.post("/api/submissions", headers=h, json=GOOD).json()["id"] for _ in range(3)]
    assert len(set(ids)) == 3
    runs = client.get("/api/submissions").json()
    assert len(runs) == 3 and all(s["status"] == "completed" for s in runs)


def test_submission_rate_limit_kicks_in(client, api_db):
    make(api_db, "alice", Role.OPERATOR)
    h = hdr(login(client, "alice"))
    codes = [client.post("/api/submissions", headers=h, json=GOOD).status_code for _ in range(21)]
    assert codes[:20] == [201] * 20 and codes[20] == 429