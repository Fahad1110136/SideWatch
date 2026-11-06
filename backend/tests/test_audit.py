import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from backend.app.core.enums import AuditOutcome
from backend.app.repositories import audit_repo as ar


def add(db, action="auth.login", **kw):
    return ar.append_event(db, action, AuditOutcome.SUCCESS, **kw)


def test_first_event_links_to_genesis(db):
    assert add(db).prev_hash == ar.GENESIS_HASH


def test_events_are_chained(db):
    a, b = add(db), add(db)
    assert b.prev_hash == a.event_hash


def test_intact_chain_verifies(db):
    assert ar.verify_chain(db) == (True, None, 0)
    for _ in range(3):
        add(db, details={"n": 1})
    ok, bad, count = ar.verify_chain(db)
    assert ok and bad is None and count == 3


def test_update_blocked_by_database(db):
    add(db)
    with pytest.raises(DatabaseError):
        db.execute(text("UPDATE audit_events SET action='x'"))
    db.rollback()


def test_delete_blocked_by_database(db):
    add(db)
    with pytest.raises(DatabaseError):
        db.execute(text("DELETE FROM audit_events"))
    db.rollback()


def test_tampering_is_detected(db):
    add(db)
    victim = add(db)
    add(db)
    db.execute(text("DROP TRIGGER audit_no_update"))  # simulate an attacker with file access
    db.execute(text("UPDATE audit_events SET action='forged' WHERE id=:i"), {"i": victim.id})
    db.commit()
    ok, bad, _ = ar.verify_chain(db)
    assert not ok and bad == victim.id


def test_secrets_redacted_in_stored_details(db):
    ev = add(db, details={"password": "hunter2", "reason": "bad"})
    assert ev.details["password"] == "[REDACTED]" and ev.details["reason"] == "bad"


def test_list_filters(db):
    add(db, "auth.login")
    add(db, "submission.create")
    rows = ar.list_events(db, action="auth.login")
    assert len(rows) == 1 and rows[0].action == "auth.login"