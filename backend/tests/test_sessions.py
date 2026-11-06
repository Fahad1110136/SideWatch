from datetime import timedelta

from backend.app.models import UserSession
from backend.app.models.tables import utcnow
from backend.app.services import session_service as ss


def test_create_and_validate(db, user):
    token, _ = ss.create_session(db, user.id)
    assert ss.get_valid_session(db, token).user_id == user.id


def test_raw_token_not_stored(db, user):
    token, csrf = ss.create_session(db, user.id)
    row = db.query(UserSession).one()
    assert token not in (row.token_hash, row.csrf_hash)
    assert csrf not in (row.token_hash, row.csrf_hash)


def test_unknown_token_rejected(db):
    assert ss.get_valid_session(db, "bogus") is None


def test_expired_session_rejected(db, user):
    token, _ = ss.create_session(db, user.id)
    row = db.query(UserSession).one()
    row.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert ss.get_valid_session(db, token) is None


def test_revoked_session_rejected(db, user):
    token, _ = ss.create_session(db, user.id)
    ss.revoke_session(db, token)
    assert ss.get_valid_session(db, token) is None


def test_revoke_all(db, user):
    t1, _ = ss.create_session(db, user.id)
    t2, _ = ss.create_session(db, user.id)
    ss.revoke_all_user_sessions(db, user.id)
    assert ss.get_valid_session(db, t1) is None and ss.get_valid_session(db, t2) is None


def test_csrf(db, user):
    token, csrf = ss.create_session(db, user.id)
    s = ss.get_valid_session(db, token)
    assert ss.csrf_is_valid(s, csrf)
    assert not ss.csrf_is_valid(s, "wrong")
    assert not ss.csrf_is_valid(s, None)