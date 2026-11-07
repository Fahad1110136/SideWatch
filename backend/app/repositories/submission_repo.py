from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Result, Submission
from backend.app.models.tables import utcnow
from backend.app.schemas.submission import SubmissionCreate


def create(db: Session, user_id: str, data: SubmissionCreate) -> Submission:
    s = Submission(
        user_id=user_id, label=data.label, implementation=data.implementation.value,
        fixture_id=data.fixture_id, sample_size=data.sample_size,
        warmup_runs=data.warmup_runs, seed=data.seed,
    )
    db.add(s)
    db.commit()
    return s


def get(db: Session, submission_id: str) -> Submission | None:
    return db.get(Submission, submission_id)


# def list_submissions(db: Session, *, user_id: str | None = None, status: str | None = None,
#                      limit: int = 50, offset: int = 0) -> list[Submission]:
#     q = select(Submission).order_by(Submission.created_at.desc())
#     if user_id:
#         q = q.where(Submission.user_id == user_id)
#     if status:
#         q = q.where(Submission.status == status)
#     return list(db.scalars(q.limit(min(limit, 200)).offset(max(offset, 0))))

def list_submissions(db: Session, *, user_id: str | None = None, status: str | None = None,
                     implementation: str | None = None,
                     limit: int = 50, offset: int = 0) -> list[Submission]:
    q = select(Submission).order_by(Submission.created_at.desc())
    if user_id:
        q = q.where(Submission.user_id == user_id)
    if status:
        q = q.where(Submission.status == status)
    if implementation:
        q = q.where(Submission.implementation == implementation)
    return list(db.scalars(q.limit(min(limit, 200)).offset(max(offset, 0))))


def set_status(db: Session, s: Submission, status: str, error_code: str | None = None) -> Submission:
    s.status = status
    s.error_code = error_code
    if status in ("completed", "failed"):
        s.completed_at = utcnow()
    db.commit()
    return s


def save_result(db: Session, submission_id: str, data: dict) -> Result:
    """Store the engine's result and mark the submission completed, in one commit."""
    result = Result(submission_id=submission_id, **data)
    db.add(result)
    s = db.get(Submission, submission_id)
    s.status = "completed"
    s.completed_at = utcnow()
    db.commit()
    return result