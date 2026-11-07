from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.security import constant_time_equal, generate_token, hash_token
from backend.app.models import UserSession
from backend.app.models.tables import utcnow


def _aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def create_session(db: Session, user_id: str) -> tuple[str, str]:
    """Returns (session_token, csrf_token). Raw values go to the client once; only hashes are stored."""
    token, csrf = generate_token(), generate_token()
    db.add(UserSession(
        user_id=user_id,
        token_hash=hash_token(token),
        csrf_hash=hash_token(csrf),
        expires_at=utcnow() + timedelta(minutes=settings.session_ttl_minutes),
    ))
    db.commit()
    return token, csrf


def get_valid_session(db: Session, token: str) -> UserSession | None:
    s = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if s is None or s.revoked or _aware(s.expires_at) <= utcnow():
        return None
    return s


def revoke_session(db: Session, token: str) -> None:
    db.execute(update(UserSession)
               .where(UserSession.token_hash == hash_token(token))
               .values(revoked=True))
    db.commit()


def revoke_all_user_sessions(db: Session, user_id: str) -> None:
    db.execute(update(UserSession).where(UserSession.user_id == user_id).values(revoked=True))
    db.commit()


def csrf_is_valid(session: UserSession, csrf_token: str | None) -> bool:
    if not csrf_token:
        return False
    return constant_time_equal(session.csrf_hash, hash_token(csrf_token))


def purge_expired(db: Session) -> int:
    """Delete expired sessions. Returns how many were removed."""
    result = db.execute(delete(UserSession).where(UserSession.expires_at <= utcnow()))
    db.commit()
    return result.rowcount or 0


def rotate_csrf(db: Session, session: UserSession) -> str:
    """Issue a fresh CSRF token for a valid session. Only the hash is stored."""
    csrf = generate_token()
    session.csrf_hash = hash_token(csrf)
    db.commit()
    return csrf