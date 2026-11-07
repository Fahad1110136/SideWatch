import logging
import threading

from sqlalchemy.orm import Session

from backend.app.core import errors
from backend.app.core.enums import AuditOutcome, Role
from backend.app.models import Submission, User
from backend.app.repositories import audit_repo, rule_repo, submission_repo
from backend.app.schemas.result import EngineResult
from backend.app.schemas.submission import SubmissionCreate
from engine import interface as engine

logger = logging.getLogger("sidewatch")
_measurement_lock = threading.Lock()


def can_view(user: User, sub: Submission) -> bool:
    if user.role == Role.ADMIN.value:
        return True
    if user.role == Role.OPERATOR.value:
        return sub.user_id == user.id
    if user.role == Role.VIEWER.value:
        return sub.status == "completed"
    return False


def create_and_run(db: Session, user: User, data: SubmissionCreate, ip: str | None) -> Submission:
    actor = dict(actor_id=user.id, actor_role=user.role, ip_address=ip)

    if data.fixture_id not in engine.list_fixtures():
        audit_repo.append_event(db, "submission.create", AuditOutcome.FAILURE, **actor,
                                details={"reason": "unknown_fixture", "fixture_id": data.fixture_id})
        raise errors.invalid_fixture()

    sub = submission_repo.create(db, user.id, data)
    audit_repo.append_event(db, "submission.create", AuditOutcome.SUCCESS, **actor,
                            resource_type="submission", resource_id=sub.id,
                            details={"implementation": data.implementation.value,
                                     "fixture_id": data.fixture_id,
                                     "sample_size": data.sample_size})

    thresholds = {**rule_repo.DEFAULTS, **rule_repo.get_all(db)}
    submission_repo.set_status(db, sub, "running")
    try:
        with _measurement_lock:
            raw = engine.run_analysis(engine.EngineRequest(
                implementation=data.implementation.value, fixture_id=data.fixture_id,
                sample_size=data.sample_size, warmup_runs=data.warmup_runs,
                seed=data.seed, thresholds=thresholds,
            ))
        result = EngineResult.model_validate(raw).model_dump(mode="json")
        result["thresholds"] = {**result["thresholds"], **thresholds}  # config snapshot wins
    except Exception:
        logger.exception("Engine failure submission=%s", sub.id)
        submission_repo.set_status(db, sub, "failed", error_code="ENGINE_FAILED")
        audit_repo.append_event(db, "submission.run", AuditOutcome.FAILURE, **actor,
                                resource_type="submission", resource_id=sub.id,
                                details={"error_code": "ENGINE_FAILED"})
        return sub

    submission_repo.save_result(db, sub.id, result)
    audit_repo.append_event(db, "submission.run", AuditOutcome.SUCCESS, **actor,
                            resource_type="submission", resource_id=sub.id,
                            details={"decision": result["decision"],
                                     "rule_name": result["rule_name"],
                                     "rule_version": result["rule_version"]})
    return sub