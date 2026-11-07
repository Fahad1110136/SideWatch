from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.app.core import errors
from backend.app.core.enums import AuditOutcome, Role
from backend.app.core.rate_limit import limiter
from backend.app.database import get_db
from backend.app.models import User, UserSession
from backend.app.repositories import audit_repo
from backend.app.services import session_service

SESSION_COOKIE = "sw_session"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass
class AuthContext:
    user: User
    session: UserSession


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise errors.not_authenticated()
    session = session_service.get_valid_session(db, token)
    if session is None:
        raise errors.session_expired()
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise errors.not_authenticated()

    if request.method in UNSAFE_METHODS and not session_service.csrf_is_valid(
        session, request.headers.get(CSRF_HEADER)
    ):
        audit_repo.append_event(
            db, "security.csrf_failed", AuditOutcome.DENIED, actor_id=user.id,
            actor_role=user.role, ip_address=client_ip(request),
            details={"path": request.url.path, "method": request.method},
        )
        raise errors.csrf_failed()
    return AuthContext(user=user, session=session)


def require_roles(*roles: Role):
    allowed = {r.value for r in roles}

    def dependency(
        request: Request,
        ctx: AuthContext = Depends(get_auth),
        db: Session = Depends(get_db),
    ) -> AuthContext:
        if ctx.user.role not in allowed:
            audit_repo.append_event(
                db, "security.access_denied", AuditOutcome.DENIED, actor_id=ctx.user.id,
                actor_role=ctx.user.role, ip_address=client_ip(request),
                details={"path": request.url.path, "method": request.method},
            )
            raise errors.forbidden()
        return ctx

    return dependency


def rate_limit(name: str, limit: int, window_seconds: int):
    def dependency(request: Request, db: Session = Depends(get_db)) -> None:
        ip = client_ip(request)
        if not limiter.allow(f"{name}:{ip}", limit, window_seconds):
            audit_repo.append_event(
                db, "security.rate_limited", AuditOutcome.DENIED, ip_address=ip,
                details={"limiter": name},
            )
            raise errors.rate_limited()

    return dependency