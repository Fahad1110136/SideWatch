from contextlib import contextmanager
import json

from scripts.init_env import initialize


def test_env_setup_preserves_existing_config_and_secret(tmp_path):
    original = b"SECRET_KEY=existing-secret\r\nDATABASE_URL=sqlite:///custom.db\r\n"
    path = tmp_path / ".env"
    path.write_bytes(original)
    assert initialize(tmp_path) is False
    assert path.read_bytes() == original


def test_new_env_has_unique_strong_secrets(tmp_path):
    secrets = []
    for name in ("first", "second"):
        directory = tmp_path / name
        directory.mkdir()
        assert initialize(directory) is True
        settings = dict(line.split("=", 1) for line in (directory / ".env").read_text().splitlines())
        assert settings["DATABASE_URL"] == "sqlite:///./data/sidewatch.db"
        assert settings["APP_ENV"] == "development"
        assert len(settings["SECRET_KEY"]) >= 32
        secrets.append(settings["SECRET_KEY"])
    assert secrets[0] != secrets[1]


def test_smoke_cleanup_failure_cannot_report_success(tmp_path, monkeypatch):
    from scripts import smoke

    real_workspace = smoke.workspace

    @contextmanager
    def failed_cleanup():
        with real_workspace() as directory:
            yield directory
        # Reproduce the Windows cleanup failure after all HTTP checks succeed.
        raise PermissionError("simulated cleanup failure")

    monkeypatch.setattr(smoke, "workspace", failed_cleanup)
    assert smoke.main(["--output-dir", str(tmp_path)]) == 1
    output = next(tmp_path.glob("smoke-*"))
    report = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert report["passed"] is False
    assert report["checks"][-1] == {
        "name": "cleanup", "passed": False, "error": "simulated cleanup failure",
    }
