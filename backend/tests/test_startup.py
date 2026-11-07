from datetime import timedelta

import pytest

from backend.app.config import Settings
from backend.app.core.startup import enforce_secure_settings
from backend.app.models import UserSession
from backend.app.models.tables import utcnow
from backend.app.services import recovery_service as rs
from backend.app.services import session_service as ss

STRONG = "k" * 48


def test_production_refuses_placeholder_key():
    with pytest.raises(RuntimeError):
        enforce_secure_settings(Settings(app_env="production", secret_key="change-me"))
    with pytest.raises(RuntimeError):
        enforce_secure_settings(
            Settings(app_env="production", secret_key="change-me-to-a-long-random-string"))


def test_production_refuses_short_key_without_leaking_it():
    with pytest.raises(RuntimeError) as exc:
        enforce_secure_settings(Settings(app_env="production", secret_key="tooshort"))
    assert "tooshort" not in str(exc.value)


def test_production_accepts_strong_key():
    assert enforce_secure_settings(Settings(app_env="production", secret_key=STRONG)) == []


def test_development_only_warns():
    problems = enforce_secure_settings(Settings(app_env="development", secret_key="change-me"))
    assert len(problems) == 1


def test_purge_removes_only_expired_sessions(db, user):
    expired_token, _ = ss.create_session(db, user.id)
    live_token, _ = ss.create_session(db, user.id)
    row = db.query(UserSession).filter_by(token_hash=ss.hash_token(expired_token)).one()
    row.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert ss.purge_expired(db) == 1
    assert ss.get_valid_session(db, live_token) is not None


def test_startup_checks_report_purged_sessions(db, user):
    token, _ = ss.create_session(db, user.id)
    db.query(UserSession).one().expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    result = rs.run_startup_checks(db)
    assert result["purged_sessions"] == 1 and result["audit_chain_intact"] is True