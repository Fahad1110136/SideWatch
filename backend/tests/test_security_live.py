"""T-final against real HTTP and real server processes with a disposable database."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[2]
GOOD = dict(label="Live QA", implementation="vulnerable", fixture_id="no_match",
            sample_size=30, warmup_runs=0, seed=2026)


class LiveServer:
    def __init__(self, directory):
        self.directory = directory
        self.process = None
        self.clients = []
        self.logs = []
        self.port_file = directory / "port.txt"
        self.marker = directory / "engine-entered.txt"
        self.password = secrets.token_urlsafe(24) + "A1"
        self.env = {**os.environ, "APP_ENV": "development",
                    "DATABASE_URL": "sqlite:///" + (directory / "live.db").as_posix(),
                    "SECRET_KEY": secrets.token_urlsafe(48), "MAX_BODY_BYTES": "65536",
                    "SESSION_TTL_MINUTES": "30", "PYTHONIOENCODING": "utf-8",
                    "SIDEWATCH_TEST_PASSWORD": self.password,
                    "SIDEWATCH_TEST_PORT": str(self.port_file), "SIDEWATCH_TEST_MARKER": str(self.marker)}

    def start(self):
        self.port_file.unlink(missing_ok=True)
        log = (self.directory / f"server-{len(self.logs) + 1}.log").open("w", encoding="utf-8")
        self.logs.append(log)
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        self.process = subprocess.Popen([sys.executable, "-m", "backend.tests.live_server"],
                                        cwd=ROOT, env=self.env, stdout=log, stderr=log, **options)
        deadline = time.monotonic() + 20
        with httpx.Client(trust_env=False, timeout=0.5) as probe:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    pytest.fail(f"Server exited: {(Path(log.name)).read_text(encoding='utf-8')}")
                if self.port_file.exists():
                    port = self.port_file.read_text(encoding="ascii")
                    if port:
                        self.url = f"http://127.0.0.1:{int(port)}"
                        try:
                            if probe.get(self.url + "/api/health").status_code == 200:
                                return
                        except httpx.HTTPError:
                            pass
                time.sleep(0.05)
        pytest.fail(f"Server did not become healthy; see {log.name}")

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=10)

    def client(self, name=None):
        client = httpx.Client(base_url=self.url, trust_env=False, timeout=10)
        self.clients.append(client)
        if name:
            response = client.post("/api/auth/login", json=dict(username=name, password=self.password))
            assert response.status_code == 200, response.text
            client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        return client


@pytest.fixture
def live(tmp_path):
    server = LiveServer(tmp_path)
    try:
        server.start()
        yield server
    finally:
        server.stop()
        for client in server.clients:
            client.close()
        for log in server.logs:
            log.close()


def test_live_invalid_unauthorized_repeated_and_safe_failures(live):
    anonymous = live.client()
    denied = anonymous.post("/api/submissions", json=GOOD)
    assert denied.status_code == 401 and denied.json()["code"] == "AUTH_REQUIRED"
    viewer = live.client("qa_viewer")
    denied = viewer.post("/api/submissions", json=GOOD)
    assert denied.status_code == 403 and denied.json()["code"] == "ACCESS_DENIED"
    operator = live.client("qa_operator")
    malformed = operator.post("/api/submissions", content=b'{PRIVATE_INVALID_JSON',
                              headers={"Content-Type": "application/json"})
    assert malformed.status_code == 422 and malformed.json()["code"] == "VALIDATION_ERROR"
    assert "PRIVATE_INVALID_JSON" not in malformed.text
    oversized = operator.post("/api/submissions", content=b"x" * 65537)
    assert oversized.status_code == 413 and oversized.json()["code"] == "REQUEST_TOO_LARGE"
    assert operator.get("/api/submissions").json() == []

    ids = []
    for _ in range(2):
        response = operator.post("/api/submissions", json=GOOD)
        assert response.status_code == 201 and response.json()["status"] == "completed"
        ids.append(response.json()["id"])
    assert len(set(ids)) == 2
    for fixture in ("prefix_1", "prefix_4"):
        response = operator.post("/api/submissions", json={**GOOD, "fixture_id": fixture})
        assert response.status_code == 201
        failed = response.json()
        assert failed["status"] == "failed" and failed["error_code"] == "ENGINE_FAILED"
        assert "PRIVATE_ENGINE_DETAIL" not in response.text and "Traceback" not in response.text
        for suffix in ("result", "report"):
            assert operator.get(f"/api/submissions/{failed['id']}/{suffix}").status_code == 404
    # A failure must not strand the measurement lock or poison the next request.
    assert operator.post("/api/submissions", json=GOOD).json()["status"] == "completed"
    admin = live.client("qa_admin")
    failures = admin.get("/api/audit", params={"action": "submission.run", "outcome": "failure"}).json()
    assert len(failures) == 2
    assert all(event["details"] == {"error_code": "ENGINE_FAILED"} for event in failures)
    assert "PRIVATE_ENGINE_DETAIL" not in str(failures)
    assert admin.get("/api/audit", params={"action": "security.access_denied"}).json()
    assert admin.get("/api/audit/verify").json()["intact"] is True


def test_live_crash_restart_recovers_once_and_preserves_state(live):
    operator = live.client("qa_operator")
    admin = live.client("qa_admin")
    revoked = live.client("qa_viewer")
    # Keep the revoked cookie to verify it is still rejected after restart.
    old_cookies = httpx.Cookies(revoked.cookies)
    assert revoked.post("/api/auth/logout").status_code == 200
    revoked.cookies = old_cookies
    change = admin.put("/api/rules/alpha", json={"value": 0.05, "confirm": True})
    assert change.status_code == 200
    done = operator.post("/api/submissions", json=GOOD).json()
    assert done["status"] == "completed"
    saved_result = operator.get(f"/api/submissions/{done['id']}/result").json()

    def interrupted_request():
        try:
            operator.post("/api/submissions", json={**GOOD, "fixture_id": "full_match"})
        except httpx.HTTPError:
            return
        pytest.fail("Blocked measurement unexpectedly completed")

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(interrupted_request)
        deadline = time.monotonic() + 10
        while not live.marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        try:
            assert live.marker.exists(), "Measurement never entered the blocking test engine"
            running = admin.get("/api/submissions", params={"status": "running"}).json()
            assert len(running) == 1
            interrupted_id = running[0]["id"]
        finally:
            live.stop()  # actual abrupt process termination, not an in-process DB reconnect
        pending.result(timeout=12)

    for _ in range(2):
        live.start()
        for client in (operator, admin, revoked):
            client.base_url = httpx.URL(live.url)
        assert operator.get("/api/auth/me").status_code == 200
        assert revoked.get("/api/auth/me").status_code == 401
        restored = operator.get(f"/api/submissions/{interrupted_id}").json()
        assert restored["status"] == "failed" and restored["error_code"] == "INTERRUPTED_BY_RESTART"
        for suffix in ("result", "report"):
            assert operator.get(f"/api/submissions/{interrupted_id}/{suffix}").status_code == 404
        assert operator.get(f"/api/submissions/{done['id']}/result").json() == saved_result
        rules = admin.get("/api/rules").json()
        alpha = next(rule for rule in rules if rule["key"] == "alpha")
        assert alpha["value"] == 0.05 and alpha["version"] == change.json()["version"]
        recovery = admin.get("/api/audit", params={"action": "system.recovery"}).json()
        assert len(recovery) == 1 and recovery[0]["resource_id"] == interrupted_id
        assert recovery[0]["details"]["previous_status"] == "running"
        assert admin.get("/api/audit/verify").json()["intact"] is True
        # The persisted CSRF token and session still authorize useful work.
        assert operator.post("/api/submissions", json=GOOD).json()["status"] == "completed"
        live.stop()
