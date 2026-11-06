from backend.app.models import User
from backend.app.repositories import submission_repo as sr
from backend.app.schemas.submission import SubmissionCreate

DATA = SubmissionCreate(label="Run 1", implementation="vulnerable",
                        fixture_id="no_match", sample_size=100)
RESULT = dict(decision="leak_detected", severity="high", confidence=0.99, evidence={},
              reasons=["x"], rule_name="welch", rule_version="1", engine_version="1",
              thresholds={"alpha": 0.01})


def test_create_defaults_to_queued(db, user):
    s = sr.create(db, user.id, DATA)
    assert s.status == "queued" and len(s.id) == 32


def test_list_scoped_to_user(db, user):
    other = User(username="dave", password_hash="x", role="operator")
    db.add(other)
    db.commit()
    sr.create(db, user.id, DATA)
    sr.create(db, other.id, DATA)
    assert len(sr.list_submissions(db, user_id=user.id)) == 1
    assert len(sr.list_submissions(db)) == 2


def test_status_filter(db, user):
    s = sr.create(db, user.id, DATA)
    sr.create(db, user.id, DATA)
    sr.set_status(db, s, "running")
    assert len(sr.list_submissions(db, status="running")) == 1


def test_save_result_completes_submission(db, user):
    s = sr.create(db, user.id, DATA)
    sr.save_result(db, s.id, RESULT)
    assert s.status == "completed" and s.completed_at is not None and s.result.decision == "leak_detected"


def test_failed_status_records_safe_error_code(db, user):
    s = sr.create(db, user.id, DATA)
    sr.set_status(db, s, "failed", error_code="ENGINE_TIMEOUT")
    assert s.error_code == "ENGINE_TIMEOUT" and s.completed_at is not None