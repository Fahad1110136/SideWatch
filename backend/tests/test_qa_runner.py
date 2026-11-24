"""Check the QA gate fails honestly and keeps evidence when a check fails."""

import json
from pathlib import Path
import sys

import pytest

from scripts import qa


def evaluation():
    return {
        "engine_version": "test", "total": 6, "passed": 6,
        "cases": [dict(id=f"T{i}", inputs={}, expected="ok", actual={},
                       evidence={}, passed=True) for i in range(1, 7)],
    }


@pytest.mark.parametrize("failure", [None, "pytest", "evaluation", "invalid-report"])
def test_gate_preserves_both_reports_and_propagates_failure(tmp_path, monkeypatch, failure):
    calls = []

    def fake_step(command, output, name, env, timeout):
        calls.append(name)
        database = Path(env["DATABASE_URL"].removeprefix("sqlite:///"))
        assert database.name == "qa.db"
        assert database.parent.name.startswith("sidewatch-qa-")
        assert database.parent.is_dir()
        assert env["APP_ENV"] == "development"
        assert len(env["SECRET_KEY"]) >= 32
        if name == "pytest":
            (output / "pytest.xml").write_text(
                '<testsuites><testsuite tests="2" failures="0" errors="0" skipped="0"/></testsuites>',
                encoding="utf-8",
            )
        else:
            report = "not json" if failure == "invalid-report" else json.dumps(evaluation())
            (output / "evaluation.stdout.log").write_text(report, encoding="utf-8")
        return dict(command=command, exit_code=1 if failure == name else 0,
                    duration_seconds=0.01, passed=failure != name, error=None)

    monkeypatch.setattr(qa, "run_step", fake_step)
    monkeypatch.setattr(qa, "environment_details", lambda: {"git_revision": "test", "working_tree_dirty": False})
    assert qa.main(["--output-dir", str(tmp_path)]) == (0 if failure is None else 1)
    assert calls == ["pytest", "evaluation"]
    output = next(tmp_path.iterdir())
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["passed"] is (failure is None)
    assert (output / "summary.md").exists()


@pytest.mark.parametrize("kind", ["missing-case", "duplicate-case", "failed-case", "missing-evidence", "wrong-total"])
def test_incomplete_or_failed_evaluation_is_rejected(tmp_path, kind):
    report = evaluation()
    if kind == "missing-case":
        report["cases"].pop()
    elif kind == "duplicate-case":
        report["cases"][-1]["id"] = "T1"
    elif kind == "failed-case":
        report["cases"][0]["passed"] = False
    elif kind == "missing-evidence":
        del report["cases"][0]["evidence"]
    else:
        report["passed"] = 5
    path = tmp_path / "evaluation.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        qa.read_evaluation_report(path)


@pytest.mark.parametrize("tests,failures,errors,skipped", [(0, 0, 0, 0), (2, 1, 0, 0), (2, 0, 1, 0), (2, 0, 0, 2)])
def test_empty_failed_or_fully_skipped_suite_cannot_pass(tmp_path, tests, failures, errors, skipped):
    path = tmp_path / "pytest.xml"
    path.write_text(
        f'<testsuite tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}"/>',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        qa.read_pytest_report(path)


def test_timeout_is_a_failure_with_saved_logs(tmp_path):
    result = qa.run_step(
        [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(20)"],
        tmp_path, "timeout", None, 0.5,
    )
    assert result["passed"] is False
    assert result["exit_code"] is None
    assert "Timed out" in result["error"]
    assert (tmp_path / "timeout.stdout.log").exists()
    assert (tmp_path / "timeout.stderr.log").exists()
