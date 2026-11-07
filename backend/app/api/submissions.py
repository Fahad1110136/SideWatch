# from fastapi import APIRouter, Depends, Path, Query, Request
# from sqlalchemy.orm import Session

# from backend.app.core import errors
# from backend.app.core.deps import (
#     AuthContext, client_ip, get_auth, rate_limit, require_roles,
# )
# from backend.app.core.enums import AuditOutcome, Implementation, Role, SubmissionStatus
# from backend.app.database import get_db
# from backend.app.models import Submission
# from backend.app.repositories import audit_repo, submission_repo
# from backend.app.schemas.result import ResultOut
# from backend.app.schemas.submission import SubmissionCreate, SubmissionOut
# from backend.app.services import submission_service
# from engine import interface as engine

# router = APIRouter(prefix="/api/submissions", tags=["submissions"])
# fixtures_router = APIRouter(prefix="/api/fixtures", tags=["submissions"])
# can_submit = require_roles(Role.ADMIN, Role.OPERATOR)


# def _load_visible(db: Session, ctx: AuthContext, submission_id: str, request: Request) -> Submission:
#     """Missing and not-yours both return the same 404, so existence is never revealed."""
#     sub = submission_repo.get(db, submission_id)
#     if sub is None:
#         raise errors.not_found()
#     if not submission_service.can_view(ctx.user, sub):
#         audit_repo.append_event(
#             db, "security.access_denied", AuditOutcome.DENIED, actor_id=ctx.user.id,
#             actor_role=ctx.user.role, ip_address=client_ip(request),
#             resource_type="submission", resource_id=sub.id,
#             details={"path": request.url.path, "method": request.method},
#         )
#         raise errors.not_found()
#     return sub


# @fixtures_router.get("", response_model=list[str])
# def list_fixtures(ctx: AuthContext = Depends(get_auth)):
#     return engine.list_fixtures()


# @router.post("", response_model=SubmissionOut, status_code=201,
#              dependencies=[Depends(rate_limit("submit", 20, 60))])
# def create_submission(body: SubmissionCreate, request: Request,
#                       ctx: AuthContext = Depends(can_submit), db: Session = Depends(get_db)):
#     return submission_service.create_and_run(db, ctx.user, body, client_ip(request))


# @router.get("", response_model=list[SubmissionOut])
# def list_submissions(
#     status: SubmissionStatus | None = None,
#     implementation: Implementation | None = None,
#     limit: int = Query(50, ge=1, le=200),
#     offset: int = Query(0, ge=0),
#     ctx: AuthContext = Depends(get_auth),
#     db: Session = Depends(get_db),
# ):
#     user_id = ctx.user.id if ctx.user.role == Role.OPERATOR.value else None  # operators: own only
#     status_value = status.value if status else None
#     if ctx.user.role == Role.VIEWER.value:
#         status_value = "completed"                                           # viewers: completed only
#     return submission_repo.list_submissions(
#         db, user_id=user_id, status=status_value,
#         implementation=implementation.value if implementation else None,
#         limit=limit, offset=offset,
#     )


# @router.get("/{submission_id}", response_model=SubmissionOut)
# def get_submission(request: Request, submission_id: str = Path(max_length=32),
#                    ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
#     return _load_visible(db, ctx, submission_id, request)


# @router.get("/{submission_id}/result", response_model=ResultOut)
# def get_result(request: Request, submission_id: str = Path(max_length=32),
#                ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
#     sub = _load_visible(db, ctx, submission_id, request)
#     if sub.result is None:
#         raise errors.not_found()
#     return sub.result



from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.core import errors
from backend.app.core.deps import (
    AuthContext, client_ip, get_auth, rate_limit, require_roles,
)
from backend.app.core.enums import AuditOutcome, Implementation, Role, SubmissionStatus
from backend.app.database import get_db
from backend.app.models import Submission
from backend.app.repositories import audit_repo, submission_repo
from backend.app.schemas.result import ResultOut
from backend.app.schemas.submission import SubmissionCreate, SubmissionOut
from backend.app.services import report_service, submission_service
from engine import interface as engine

router = APIRouter(prefix="/api/submissions", tags=["submissions"])
fixtures_router = APIRouter(prefix="/api/fixtures", tags=["submissions"])
can_submit = require_roles(Role.ADMIN, Role.OPERATOR)


def _load_visible(db: Session, ctx: AuthContext, submission_id: str, request: Request) -> Submission:
    """Missing and not-yours both return the same 404, so existence is never revealed."""
    sub = submission_repo.get(db, submission_id)
    if sub is None:
        raise errors.not_found()
    if not submission_service.can_view(ctx.user, sub):
        audit_repo.append_event(
            db, "security.access_denied", AuditOutcome.DENIED, actor_id=ctx.user.id,
            actor_role=ctx.user.role, ip_address=client_ip(request),
            resource_type="submission", resource_id=sub.id,
            details={"path": request.url.path, "method": request.method},
        )
        raise errors.not_found()
    return sub


@fixtures_router.get("", response_model=list[str])
def list_fixtures(ctx: AuthContext = Depends(get_auth)):
    return engine.list_fixtures()


@router.post("", response_model=SubmissionOut, status_code=201,
             dependencies=[Depends(rate_limit("submit", 20, 60))])
def create_submission(body: SubmissionCreate, request: Request,
                      ctx: AuthContext = Depends(can_submit), db: Session = Depends(get_db)):
    return submission_service.create_and_run(db, ctx.user, body, client_ip(request))


@router.get("", response_model=list[SubmissionOut])
def list_submissions(
    status: SubmissionStatus | None = None,
    implementation: Implementation | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
):
    user_id = ctx.user.id if ctx.user.role == Role.OPERATOR.value else None  # operators: own only
    status_value = status.value if status else None
    if ctx.user.role == Role.VIEWER.value:
        status_value = "completed"                                           # viewers: completed only
    return submission_repo.list_submissions(
        db, user_id=user_id, status=status_value,
        implementation=implementation.value if implementation else None,
        limit=limit, offset=offset,
    )


@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission(request: Request, submission_id: str = Path(max_length=32),
                   ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    return _load_visible(db, ctx, submission_id, request)


@router.get("/{submission_id}/result", response_model=ResultOut)
def get_result(request: Request, submission_id: str = Path(max_length=32),
               ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    sub = _load_visible(db, ctx, submission_id, request)
    if sub.result is None:
        raise errors.not_found()
    return sub.result


@router.get("/{submission_id}/report",
            dependencies=[Depends(rate_limit("export", 10, 60))])
def export_report(request: Request, submission_id: str = Path(max_length=32),
                  ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    sub = _load_visible(db, ctx, submission_id, request)
    if sub.result is None:
        raise errors.not_found()
    report = report_service.build_report(db, sub)
    audit_repo.append_event(
        db, "report.export", AuditOutcome.SUCCESS, actor_id=ctx.user.id,
        actor_role=ctx.user.role, ip_address=client_ip(request),
        resource_type="submission", resource_id=sub.id,
        details={"format": "json", "report_digest": report["integrity"]["report_digest"]},
    )
    return JSONResponse(
        report,
        headers={"Content-Disposition": f'attachment; filename="sidewatch-report-{sub.id}.json"'},
    )