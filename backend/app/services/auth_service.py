from sqlalchemy.orm import Session

from backend.app.core import errors
from backend.app.core.enums import AuditOutcome
from backend.app.core.security import hash_password, password_needs_rehash, verify_password
from backend.app.models import User
from backend.app.repositories import audit_repo, user_repo
from backend.app.services import session_service

# Verified against when the username doesn't exist, so response time doesn't reveal valid usernames.
_DUMMY_HASH = hash_password("dummy-password-for-timing-only")


def login(db: Session, username: str, password: str, ip: str | None) -> tuple[User, str, str]:
    user = user_repo.get_by_username(db, username)

    if user is None:
        verify_password(_DUMMY_HASH, password)
        audit_repo.append_event(db, "auth.login", AuditOutcome.FAILURE, ip_address=ip,
                                details={"reason": "invalid_credentials",
                                         "attempted_username": username})
        raise errors.invalid_credentials()

    if user_repo.is_locked(user):
        audit_repo.append_event(db, "auth.login", AuditOutcome.DENIED, actor_id=user.id,
                                actor_role=user.role, ip_address=ip,
                                details={"reason": "account_locked"})
        raise errors.account_locked()

    if not verify_password(user.password_hash, password) or not user.is_active:
        locked_now = user_repo.register_failed_login(db, user) if user.is_active else False
        audit_repo.append_event(db, "auth.login", AuditOutcome.FAILURE, actor_id=user.id,
                                actor_role=user.role, ip_address=ip,
                                details={"reason": "invalid_credentials", "locked": locked_now})
        raise errors.invalid_credentials()

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user_repo.register_successful_login(db, user)
    token, csrf = session_service.create_session(db, user.id)
    audit_repo.append_event(db, "auth.login", AuditOutcome.SUCCESS, actor_id=user.id,
                            actor_role=user.role, ip_address=ip)
    return user, token, csrf