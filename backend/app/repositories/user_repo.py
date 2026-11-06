from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.enums import Role
from backend.app.core.security import hash_password
from backend.app.models import User
from backend.app.models.tables import utcnow

MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15


class UsernameTaken(Exception):
    pass


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def create_user(db: Session, username: str, password: str, role: Role) -> User:
    user = User(username=username.lower(), password_hash=hash_password(password),
                role=Role(role).value)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise UsernameTaken()
    return user


def get_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username.lower()))


def get_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at)))


def set_active(db: Session, user: User, active: bool) -> User:
    user.is_active = active
    db.commit()
    return user


def is_locked(user: User) -> bool:
    return user.locked_until is not None and _aware(user.locked_until) > utcnow()


def register_failed_login(db: Session, user: User) -> bool:
    """Returns True if this failure triggered a lockout."""
    user.failed_logins += 1
    locked = user.failed_logins >= MAX_FAILED_LOGINS
    if locked:
        user.locked_until = utcnow() + timedelta(minutes=LOCK_MINUTES)
        user.failed_logins = 0
    db.commit()
    return locked


def register_successful_login(db: Session, user: User) -> None:
    user.failed_logins = 0
    user.locked_until = None
    db.commit()