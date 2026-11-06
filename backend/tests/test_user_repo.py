import pytest

from backend.app.core.enums import Role
from backend.app.repositories import user_repo as ur


def test_password_is_hashed(db):
    u = ur.create_user(db, "bob_1", "CorrectHorse123", Role.OPERATOR)
    assert u.password_hash.startswith("$argon2id$") and "CorrectHorse123" not in u.password_hash


def test_duplicate_username_case_insensitive(db):
    ur.create_user(db, "Bob_1", "CorrectHorse123", Role.OPERATOR)
    with pytest.raises(ur.UsernameTaken):
        ur.create_user(db, "bob_1", "CorrectHorse123", Role.VIEWER)


def test_lookup_case_insensitive(db):
    u = ur.create_user(db, "Carol", "CorrectHorse123", Role.VIEWER)
    assert ur.get_by_username(db, "CAROL").id == u.id


def test_lockout_after_repeated_failures(db, user):
    for _ in range(ur.MAX_FAILED_LOGINS - 1):
        assert ur.register_failed_login(db, user) is False
    assert ur.register_failed_login(db, user) is True
    assert ur.is_locked(user)


def test_successful_login_clears_lock(db, user):
    for _ in range(ur.MAX_FAILED_LOGINS):
        ur.register_failed_login(db, user)
    ur.register_successful_login(db, user)
    assert not ur.is_locked(user) and user.failed_logins == 0


def test_deactivate_user(db, user):
    assert ur.set_active(db, user, False).is_active is False