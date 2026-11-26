"""Run SideWatch checks and preserve local evidence: python -m scripts.qa."""

import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CASES = {f"T{i}" for i in range(1, 7)}


def run_step(command, output_dir, name, env, timeout):
    started = time.monotonic()
    try:
        result = subprocess.run(
            command, cwd=ROOT, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        stdout, stderr = result.stdout, result.stderr
        code = result.returncode
        error = None if code == 0 else f"Command exited with status {code}"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        stdout = stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else stdout
        stderr = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr
        code, error = None, f"Timed out after {timeout} seconds"
    except OSError as exc:
        stdout, stderr = "", str(exc)
        code, error = None, "Could not start check"
    (output_dir / f"{name}.stdout.log").write_text(stdout, encoding="utf-8")
    (output_dir / f"{name}.stderr.log").write_text(stderr, encoding="utf-8")
    return {
        "command": command, "exit_code": code,
        "duration_seconds": round(time.monotonic() - started, 3),
        "passed": code == 0, "error": error,
    }


def read_pytest_report(path):
    root = ET.parse(path).getroot()
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in root.iter("testsuite"):
        # pytest produces a flat list of suites; count leaf suites only.
        if suite.find("testsuite") is None:
            for key in counts:
                counts[key] += int(suite.get(key, "0"))
    counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    if counts["tests"] <= 0 or counts["passed"] <= 0:
        raise ValueError("No passing tests recorded")
    if counts["failures"] or counts["errors"]:
        raise ValueError(f"Test failures or errors recorded: {counts}")
    return counts


def read_evaluation_report(path):
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not isinstance(report.get("cases"), list):
        raise ValueError("Evaluation must be an object containing a cases list")
    cases = report["cases"]
    if any(not isinstance(case, dict) for case in cases):
        raise ValueError("Each evaluation case must be an object")
    ids = [case["id"] for case in cases]
    if len(ids) != 6 or set(ids) != REQUIRED_CASES:
        raise ValueError("Evaluation must contain T1 through T6 exactly once")
    fields = {"inputs", "expected", "actual", "evidence", "passed"}
    if any(not fields <= case.keys() or case["passed"] is not True for case in cases):
        raise ValueError("Evaluation case failed or has incomplete evidence")
    if report["total"] != 6 or report["passed"] != 6:
        raise ValueError("Evaluation totals do not match six passing cases")
    return {"total": 6, "passed": 6, "engine_version": report["engine_version"]}


def environment_details():
    packages = {}
    for name in ("pytest", "fastapi", "httpx", "numpy", "scipy", "sqlalchemy", "pydantic-settings"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = "not installed"
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
            timeout=10, check=True,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True,
            timeout=10, check=True,
        ).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        revision, dirty = None, None
    return {
        "python": platform.python_version(), "platform": platform.system(),
        "platform_release": platform.release(), "machine": platform.machine(),
        "packages": packages, "git_revision": revision, "working_tree_dirty": dirty,
    }


def positive_seconds(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("timeout must be a positive number of seconds")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "qa",
                        help="parent directory for a new evidence folder")
    parser.add_argument("--timeout", type=positive_seconds, default=300,
                        help="timeout in seconds for each check (default: 300)")
    args = parser.parse_args(argv)
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    output = Path(tempfile.mkdtemp(prefix=started.strftime("%Y%m%dT%H%M%SZ-"), dir=args.output_dir))
    print(f"Evidence: {output}", flush=True)
    summary = {"started_at_utc": started.isoformat(), "environment": environment_details(), "checks": {}}
    with tempfile.TemporaryDirectory(prefix="sidewatch-qa-") as scratch:
        env = dict(os.environ)
        env.update({
            "APP_ENV": "development", "SECRET_KEY": secrets.token_urlsafe(48),
            "DATABASE_URL": "sqlite:///" + (Path(scratch) / "qa.db").as_posix(),
            "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
            "MAX_BODY_BYTES": "65536", "SESSION_TTL_MINUTES": "30",
        })
        steps = (
            ("pytest", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        f"--junitxml={output / 'pytest.xml'}"], read_pytest_report, output / "pytest.xml"),
            ("evaluation", [sys.executable, "-m", "engine.evaluation"],
             read_evaluation_report, output / "evaluation.stdout.log"),
        )
        for name, command, validate, evidence in steps:
            print(f"Running {name}...", flush=True)
            check = run_step(command, output, name, env, args.timeout)
            try:
                check["results"] = validate(evidence)
            except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
                check["passed"] = False
                check["error"] = check["error"] or f"Invalid evidence: {exc}"
            summary["checks"][name] = check
            print(f"{name}: {'PASS' if check['passed'] else 'FAIL'}", flush=True)
    summary["passed"] = all(check["passed"] for check in summary["checks"].values())
    summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = ["# SideWatch QA results", "", f"Overall: {'PASS' if summary['passed'] else 'FAIL'}",
             f"Started (UTC): {summary['started_at_utc']}",
             f"Revision: {summary['environment']['git_revision']}",
             f"Working tree dirty: {summary['environment']['working_tree_dirty']}", ""]
    for name, check in summary["checks"].items():
        lines.append(f"- {name}: {'PASS' if check['passed'] else 'FAIL'} ({check['duration_seconds']} seconds)")
        if "results" in check:
            lines.append(f"  Results: {json.dumps(check['results'])}")
        if check["error"]:
            lines.append(f"  Error: {check['error']}")
    lines += ["", "See summary.json for environment and commands, pytest.xml for test details,",
              "and evaluation.stdout.log for T1-T6 inputs, expected/actual results and evidence.", "",
              "Evaluation passes verify the harness checks, not proof of constant-time behavior.",
              "Actual timings vary with hardware and load; seeded schedules and jitter are reproducible."]
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Overall: {'PASS' if summary['passed'] else 'FAIL'}. See {output / 'summary.md'}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
