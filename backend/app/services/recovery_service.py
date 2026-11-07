# import logging

# from sqlalchemy import select
# from sqlalchemy.orm import Session

# from backend.app.core.enums import AuditOutcome
# from backend.app.models import Submission
# from backend.app.repositories import audit_repo, submission_repo

# logger = logging.getLogger("sidewatch")
# RECOVERY_ERROR_CODE = "INTERRUPTED_BY_RESTART"


# def recover_interrupted(db: Session) -> int:
#     stuck = list(db.scalars(select(Submission).where(Submission.status.in_(("queued", "running")))))
#     for sub in stuck:
#         previous = sub.status
#         submission_repo.set_status(db, sub, "failed", error_code=RECOVERY_ERROR_CODE)
#         audit_repo.append_event(db, "system.recovery", AuditOutcome.SUCCESS,
#                                 resource_type="submission", resource_id=sub.id,
#                                 details={"previous_status": previous,
#                                          "error_code": RECOVERY_ERROR_CODE})
#     return len(stuck)


# def run_startup_checks(db: Session) -> dict:
#     intact, bad_id, checked = audit_repo.verify_chain(db)   # verify before we append anything
#     if not intact:
#         logger.warning("Audit chain verification FAILED at event %s", bad_id)
#     recovered = recover_interrupted(db)
#     audit_repo.append_event(
#         db, "system.startup", AuditOutcome.SUCCESS if intact else AuditOutcome.FAILURE,
#         details={"recovered_submissions": recovered, "audit_chain_intact": intact,
#                  "events_checked": checked, "first_bad_event_id": bad_id},
#     )
#     return {"recovered": recovered, "audit_chain_intact": intact, "events_checked": checked}





import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.enums import AuditOutcome
from backend.app.models import Submission
from backend.app.repositories import audit_repo, submission_repo
from backend.app.services import session_service

logger = logging.getLogger("sidewatch")
RECOVERY_ERROR_CODE = "INTERRUPTED_BY_RESTART"


def recover_interrupted(db: Session) -> int:
    stuck = list(db.scalars(select(Submission).where(Submission.status.in_(("queued", "running")))))
    for sub in stuck:
        previous = sub.status
        submission_repo.set_status(db, sub, "failed", error_code=RECOVERY_ERROR_CODE)
        audit_repo.append_event(db, "system.recovery", AuditOutcome.SUCCESS,
                                resource_type="submission", resource_id=sub.id,
                                details={"previous_status": previous,
                                         "error_code": RECOVERY_ERROR_CODE})
    return len(stuck)


def run_startup_checks(db: Session) -> dict:
    intact, bad_id, checked = audit_repo.verify_chain(db)   # verify before we append anything
    if not intact:
        logger.warning("Audit chain verification FAILED at event %s", bad_id)
    recovered = recover_interrupted(db)
    purged = session_service.purge_expired(db)
    audit_repo.append_event(
        db, "system.startup", AuditOutcome.SUCCESS if intact else AuditOutcome.FAILURE,
        details={"recovered_submissions": recovered, "purged_sessions": purged,
                 "audit_chain_intact": intact, "events_checked": checked,
                 "first_bad_event_id": bad_id},
    )
    return {"recovered": recovered, "purged_sessions": purged,
            "audit_chain_intact": intact, "events_checked": checked}