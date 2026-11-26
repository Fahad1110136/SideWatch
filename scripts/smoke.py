"""Verify the real application with disposable local data: python -m scripts.smoke."""

import argparse
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import httpx

from scripts.qa import ROOT, environment_details


@contextmanager
def workspace():
    directory = tempfile.TemporaryDirectory(prefix="sidewatch-smoke-")
    try:
        yield directory.name
    finally:
        # Windows can briefly retain file handles after the child exits.
        # Retry only this newly created directory, never a user-supplied path.
        for attempt in range(10):
            try:
                directory.cleanup()
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.2)


def serve():
    """Child entry point: the unchanged application, without test engine hooks."""
    import uvicorn

    port_file = Path(os.environ["SIDEWATCH_SMOKE_PORT"])
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        port_file.write_text(str(port), encoding="ascii")
        uvicorn.Server(uvicorn.Config("backend.app.main:app", host="127.0.0.1", port=port,
                                     log_level="info", access_log=False)).run(sockets=[listener])


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "packaging")
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.serve:
        serve()
        return 0
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="smoke-", dir=args.output_dir))
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "environment": environment_details(), "checks": [], "passed": False}
    process = None
    clients, logs = [], []
    step = "initialize"
    print(f"Packaging evidence: {output}", flush=True)

    def passed(name, **evidence):
        report["checks"].append({"name": name, "passed": True, **evidence})
        print(f"PASS: {name}", flush=True)

    def stop():
        nonlocal process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)

    try:
        with ExitStack() as cleanup:
            scratch = cleanup.enter_context(workspace())
            cleanup.callback(stop)  # stop the child before cleaning its SQLite directory on failure
            port_file = Path(scratch) / "port.txt"
            password = secrets.token_urlsafe(24) + "A1"
            env = {**os.environ, "APP_ENV": "development", "SECRET_KEY": secrets.token_urlsafe(48),
                   "DATABASE_URL": "sqlite:///" + (Path(scratch) / "smoke.db").as_posix(),
                   "MAX_BODY_BYTES": "65536", "SESSION_TTL_MINUTES": "30",
                   "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
                   "SIDEWATCH_SMOKE_PORT": str(port_file), "SIDEWATCH_SMOKE_PASSWORD": password}
            step = "seed administrator"
            # Exercise the seed CLI with an automated hidden-prompt callback.
            # The password is supplied through the child environment, not argv or saved output.
            seed = subprocess.run(
                [sys.executable, "-c", "import getpass,os,runpy; "
                 "getpass.getpass=lambda prompt: os.environ['SIDEWATCH_SMOKE_PASSWORD']; "
                 "runpy.run_module('scripts.seed_admin', run_name='__main__')",
                 "--username", "smoke_admin"],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
            )
            (output / "seed.log").write_text(
                (seed.stdout + seed.stderr).replace(password, "[REDACTED]"), encoding="utf-8",
            )
            require(seed.returncode == 0, "Administrator setup failed")
            passed(step)

            def start():
                nonlocal process
                port_file.unlink(missing_ok=True)
                log = (output / f"server-{len(logs) + 1}.log").open("w", encoding="utf-8")
                logs.append(log)
                options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
                process = subprocess.Popen([sys.executable, "-m", "scripts.smoke", "--serve"],
                                           cwd=ROOT, env=env, stdout=log, stderr=log, **options)
                deadline = time.monotonic() + 30
                with httpx.Client(timeout=0.5, trust_env=False) as probe:
                    while time.monotonic() < deadline:
                        require(process.poll() is None, f"Server exited; inspect {Path(log.name).name}")
                        if port_file.exists():
                            text = port_file.read_text(encoding="ascii")
                            if text:
                                url = f"http://127.0.0.1:{int(text)}"
                                try:
                                    response = probe.get(url + "/api/health")
                                    if response.status_code == 200 and response.json() == {"status": "ok"}:
                                        return url
                                except httpx.HTTPError:
                                    pass
                        time.sleep(0.05)
                raise RuntimeError("Server startup timed out")

            step = "startup and frontend assets"
            url = start()
            client = httpx.Client(base_url=url, timeout=20, trust_env=False)
            clients.append(client)
            for path in ("/", "/css/style.css", "/js/app.js", "/js/pages/run.js"):
                response = client.get(path)
                require(response.status_code == 200 and bool(response.content), f"Missing asset: {path}")
            require("script-src 'self'" in client.get("/").headers.get("content-security-policy", ""),
                    "Frontend CSP missing")
            passed(step)

            step = "login and measurement"
            login = client.post("/api/auth/login", json={"username": "smoke_admin", "password": password})
            require(login.status_code == 200, "Seeded administrator cannot log in")
            client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            payload = dict(label="Packaging smoke", implementation="vulnerable", fixture_id="prefix_4",
                           sample_size=60, warmup_runs=5, seed=2026)
            response = client.post("/api/submissions", json=payload)
            require(response.status_code == 201 and response.json()["status"] == "completed",
                    "Measurement did not complete")
            submission_id = response.json()["id"]
            response = client.get(f"/api/submissions/{submission_id}/result")
            require(response.status_code == 200, "Measurement result unavailable")
            result = response.json()
            require(bool(result["reasons"]) and bool(result["evidence"]["histogram"]), "Result evidence missing")
            passed(step, submission_id=submission_id, decision=result["decision"])

            step = "sanitized report and audit"
            response = client.get(f"/api/submissions/{submission_id}/report")
            require(response.status_code == 200, "Report unavailable")
            sample = response.json()
            body = {key: value for key, value in sample.items() if key != "integrity"}
            digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            require(digest == sample["integrity"]["report_digest"], "Report digest mismatch")
            require(password not in response.text and login.json()["user"]["id"] not in response.text,
                    "Report contains account data")
            (output / "sample-report.json").write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")
            require(client.get("/api/audit/verify").json()["intact"] is True, "Audit chain failed")
            passed(step, report_digest=digest)

            step = "restart and persistence"
            stop()
            client.base_url = httpx.URL(start())
            require(client.get("/api/auth/me").status_code == 200, "Session did not survive restart")
            response = client.get(f"/api/submissions/{submission_id}/result")
            require(response.status_code == 200 and response.json() == result, "Stored result changed after restart")
            require(client.get("/api/audit/verify").json()["intact"] is True, "Audit chain failed after restart")
            passed(step)
            step = "logout"
            require(client.post("/api/auth/logout").status_code == 200, "Logout failed")
            require(client.get("/api/auth/me").status_code == 401, "Logged-out session still accepted")
            passed(step)
            step = "cleanup"
            stop()  # release SQLite before the temporary directory is removed
        report["passed"] = True
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError, httpx.HTTPError) as exc:
        report["passed"] = False
        report["checks"].append({"name": step, "passed": False, "error": str(exc)})
        print(f"FAIL: {step}: {exc}", flush=True)
    finally:
        stop()
        for client in clients:
            client.close()
        for log in logs:
            log.close()
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Overall: {'PASS' if report['passed'] else 'FAIL'}. See {output / 'summary.json'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
