from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.app.core import errors
from backend.app.core.deps import AuthContext, client_ip, require_roles
from backend.app.core.enums import AuditOutcome, Role
from backend.app.database import get_db
from backend.app.repositories import audit_repo, user_repo
from backend.app.schemas.auth import ActiveUpdate, UserCreate, UserOut
from backend.app.services import session_service

router = APIRouter(prefix="/api/users", tags=["users"])
admin_only = require_roles(Role.ADMIN)


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, request: Request,
                ctx: AuthContext = Depends(admin_only), db: Session = Depends(get_db)):
    ip = client_ip(request)
    try:
        user = user_repo.create_user(db, body.username, body.password, body.role)
    except user_repo.UsernameTaken:
        audit_repo.append_event(db, "admin.user_create", AuditOutcome.FAILURE,
                                actor_id=ctx.user.id, actor_role=ctx.user.role, ip_address=ip,
                                details={"reason": "username_taken"})
        raise errors.user_exists()
    audit_repo.append_event(db, "admin.user_create", AuditOutcome.SUCCESS,
                            actor_id=ctx.user.id, actor_role=ctx.user.role, ip_address=ip,
                            resource_type="user", resource_id=user.id,
                            details={"role": body.role.value})
    return user


@router.get("", response_model=list[UserOut])
def list_users(ctx: AuthContext = Depends(admin_only), db: Session = Depends(get_db)):
    return user_repo.list_users(db)


@router.patch("/{user_id}/active", response_model=UserOut)
def set_active(user_id: str, body: ActiveUpdate, request: Request,
               ctx: AuthContext = Depends(admin_only), db: Session = Depends(get_db)):
    ip = client_ip(request)
    target = user_repo.get_by_id(db, user_id)
    if target is None:
        raise errors.not_found()
    if target.id == ctx.user.id:
        audit_repo.append_event(db, "admin.user_active_change", AuditOutcome.DENIED,
                                actor_id=ctx.user.id, actor_role=ctx.user.role, ip_address=ip,
                                resource_type="user", resource_id=target.id,
                                details={"reason": "self_change"})
        raise errors.invalid_operation()
    user_repo.set_active(db, target, body.is_active)
    if not body.is_active:
        session_service.revoke_all_user_sessions(db, target.id)
    audit_repo.append_event(db, "admin.user_active_change", AuditOutcome.SUCCESS,
                            actor_id=ctx.user.id, actor_role=ctx.user.role, ip_address=ip,
                            resource_type="user", resource_id=target.id,
                            details={"is_active": body.is_active})
    return target