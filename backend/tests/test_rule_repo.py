import pytest

from backend.app.repositories import rule_repo as rr


def test_seed_defaults_is_idempotent(db):
    rr.seed_defaults(db)
    rr.seed_defaults(db)
    assert rr.get_all(db) == rr.DEFAULTS


def test_update_bumps_version_and_records_actor(db, user):
    rr.seed_defaults(db)
    rule = rr.update_value(db, "alpha", 0.05, user.id)
    assert rule.value == 0.05 and rule.version == 2 and rule.updated_by == user.id


def test_unknown_key_rejected(db, user):
    rr.seed_defaults(db)
    with pytest.raises(ValueError):
        rr.update_value(db, "drop_table", 1, user.id)


def test_out_of_range_rejected(db, user):
    rr.seed_defaults(db)
    with pytest.raises(ValueError):
        rr.update_value(db, "alpha", 0.9, user.id)