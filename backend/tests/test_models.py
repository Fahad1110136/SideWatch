import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.database import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def make_user(name="alice"):
    return models.User(username=name, password_hash="x", role="operator")


def test_user_gets_server_generated_id(db):
    u = make_user()
    db.add(u)
    db.commit()
    assert len(u.id) == 32


def test_username_must_be_unique(db):
    db.add(make_user())
    db.commit()
    db.add(make_user())
    with pytest.raises(IntegrityError):
        db.commit()


def test_submission_links_to_result(db):
    u = make_user()
    db.add(u)
    db.commit()
    s = models.Submission(user_id=u.id, label="t", implementation="vulnerable",
                          fixture_id="no_match", sample_size=100, warmup_runs=10)
    db.add(s)
    db.commit()
    r = models.Result(submission_id=s.id, decision="leak_detected", severity="high",
                      confidence=0.99, evidence={}, reasons=["x"], rule_name="welch",
                      rule_version="1", engine_version="1", thresholds={"alpha": 0.01})
    db.add(r)
    db.commit()
    assert s.result.decision == "leak_detected"