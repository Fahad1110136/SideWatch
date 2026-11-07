# from fastapi import APIRouter, Depends, Request, Response
# from sqlalchemy.orm import Session

# from backend.app.config import settings
# from backend.app.core.deps import (
#     SESSION_COOKIE, AuthContext, client_ip, get_auth, rate_limit,
# )
# from backend.app.core.enums import AuditOutcome
# from backend.app.database import get_db
# from backend.app.repositories import audit_repo
# from backend.app.schemas.auth import LoginRequest, LoginResponse, UserOut
# from backend.app.services import auth_service, session_service

# router = APIRouter(prefix="/api/auth", tags=["auth"])


# @router.post("/login", response_model=LoginResponse,
#              dependencies=[Depends(rate_limit("login", 10, 60))])
# def login(body: LoginRequest, request: Request, response: Response,
#           db: Session = Depends(get_db)):
#     user, token, csrf = auth_service.login(db, body.username, body.password, client_ip(request))
#     response.set_cookie(
#         SESSION_COOKIE, token, max_age=settings.session_ttl_minutes * 60, httponly=True,
#         samesite="strict", secure=settings.app_env == "production", path="/",
#     )
#     return LoginResponse(user=UserOut.model_validate(user), csrf_token=csrf)


# @router.post("/logout")
# def logout(request: Request, response: Response,
#            ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
#     session_service.revoke_session(db, request.cookies[SESSION_COOKIE])
#     audit_repo.append_event(db, "auth.logout", AuditOutcome.SUCCESS, actor_id=ctx.user.id,
#                             actor_role=ctx.user.role, ip_address=client_ip(request))
#     response.delete_cookie(SESSION_COOKIE, path="/")
#     return {"status": "logged_out"}


# @router.get("/me", response_model=UserOut)
# def me(ctx: AuthContext = Depends(get_auth)):
#     return ctx.user





from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.deps import (
    SESSION_COOKIE, AuthContext, client_ip, get_auth, rate_limit,
)
from backend.app.core.enums import AuditOutcome
from backend.app.database import get_db
from backend.app.repositories import audit_repo
from backend.app.schemas.auth import LoginRequest, LoginResponse, PasswordChange, UserOut
from backend.app.services import auth_service, session_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token, max_age=settings.session_ttl_minutes * 60, httponly=True,
        samesite="strict", secure=settings.app_env == "production", path="/",
    )


@router.post("/login", response_model=LoginResponse,
             dependencies=[Depends(rate_limit("login", 10, 60))])
def login(body: LoginRequest, request: Request, response: Response,
          db: Session = Depends(get_db)):
    user, token, csrf = auth_service.login(db, body.username, body.password, client_ip(request))
    _set_session_cookie(response, token)
    return LoginResponse(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post("/logout")
def logout(request: Request, response: Response,
           ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    session_service.revoke_session(db, request.cookies[SESSION_COOKIE])
    audit_repo.append_event(db, "auth.logout", AuditOutcome.SUCCESS, actor_id=ctx.user.id,
                            actor_role=ctx.user.role, ip_address=client_ip(request))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
def me(ctx: AuthContext = Depends(get_auth)):
    return ctx.user


@router.get("/csrf")
def refresh_csrf(ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    """For page reloads: the browser still has the cookie but has lost the CSRF token.
    This issues a new one and invalidates the previous one for this session."""
    return {"csrf_token": session_service.rotate_csrf(db, ctx.session)}


@router.post("/change-password", response_model=LoginResponse,
             dependencies=[Depends(rate_limit("pwchange", 5, 60))])
def change_password(body: PasswordChange, request: Request, response: Response,
                    ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    token, csrf = auth_service.change_password(
        db, ctx.user, body.current_password, body.new_password, client_ip(request))
    _set_session_cookie(response, token)
    return LoginResponse(user=UserOut.model_validate(ctx.user), csrf_token=csrf)