from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend import app as _app  # noqa: F401
from backend.app import models
from backend.app.core.enums import AuditOutcome
from backend.app.database import Base
from backend.app.repositories import audit_repo, submission_repo as sr
from backend.app.schemas.submission import SubmissionCreate
from backend.app.services import recovery_service as rs

DATA = SubmissionCreate(label="Run 1", implementation="vulnerable",
                        fixture_id="no_match", sample_size=100)
RESULT = dict(decision="leak_detected", severity="high", confidence=0.99, evidence={},
              reasons=["x"], rule_name="welch", rule_version="1", engine_version="1",
              thresholds={"alpha": 0.01})


def test_interrupted_runs_marked_failed_and_audited(db, user):
    stuck = sr.create(db, user.id, DATA)
    sr.set_status(db, stuck, "running")
    queued = sr.create(db, user.id, DATA)
    done = sr.create(db, user.id, DATA)
    sr.save_result(db, done.id, RESULT)

    assert rs.recover_interrupted(db) == 2
    assert stuck.status == "failed" and stuck.error_code == "INTERRUPTED_BY_RESTART"
    assert queued.status == "failed"
    assert done.status == "completed"
    assert len(audit_repo.list_events(db, action="system.recovery")) == 2


def test_recovery_is_idempotent(db, user):
    sr.create(db, user.id, DATA)
    assert rs.recover_interrupted(db) == 1
    assert rs.recover_interrupted(db) == 0


def test_startup_checks_report_broken_chain(db):
    audit_repo.append_event(db, "auth.login", AuditOutcome.SUCCESS)
    victim = audit_repo.append_event(db, "auth.login", AuditOutcome.SUCCESS)
    audit_repo.append_event(db, "auth.login", AuditOutcome.SUCCESS)
    db.execute(text("DROP TRIGGER audit_no_update"))   # simulate an attacker with file access
    db.execute(text("UPDATE audit_events SET action='forged' WHERE id=:i"), {"i": victim.id})
    db.commit()
    result = rs.run_startup_checks(db)
    assert result["audit_chain_intact"] is False
    assert len(audit_repo.list_events(db, action="system.startup", outcome="failure")) == 1


def test_data_and_audit_chain_survive_restart(tmp_path):
    url = f"sqlite:///{(tmp_path / 'restart.db').as_posix()}"
    first = create_engine(url)
    Base.metadata.create_all(first)
    with Session(first) as s:
        u = models.User(username="alice", password_hash="x", role="operator")
        s.add(u)
        s.commit()
        audit_repo.append_event(s, "auth.login", AuditOutcome.SUCCESS, actor_id=u.id)
        audit_repo.append_event(s, "auth.logout", AuditOutcome.SUCCESS, actor_id=u.id)
    first.dispose()

    second = create_engine(url)   # "restart": brand-new engine on the same file
    with Session(second) as s:
        assert s.query(models.User).count() == 1
        assert audit_repo.verify_chain(s) == (True, None, 2)
        audit_repo.append_event(s, "auth.login", AuditOutcome.SUCCESS)
        assert audit_repo.verify_chain(s) == (True, None, 3)
    second.dispose()