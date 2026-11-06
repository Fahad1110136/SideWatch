import hashlib
import hmac
import json
import threading
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.enums import AuditOutcome
from backend.app.core.redact import redact
from backend.app.models import AuditEvent
from backend.app.models.tables import utcnow

GENESIS_HASH = "0" * 64
_lock = threading.Lock()


def _ts(dt) -> str:
    if dt.tzinfo is None:  # SQLite returns naive datetimes; they are UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _fields(ev: AuditEvent) -> dict:
    return {
        "timestamp": _ts(ev.timestamp), "actor_id": ev.actor_id, "actor_role": ev.actor_role,
        "action": ev.action, "outcome": ev.outcome, "resource_type": ev.resource_type,
        "resource_id": ev.resource_id, "ip_address": ev.ip_address, "details": ev.details,
    }


def _compute_hash(prev_hash: str, fields: dict) -> str:
    body = prev_hash + json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)
    return hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()


def append_event(
    db: Session,
    action: str,
    outcome: AuditOutcome,
    *,
    actor_id: str | None = None,
    actor_role: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    details: dict | None = None,
) -> AuditEvent:
    """Append one event and commit. Details are redacted first.

    Note: this commits the session, so call it after your own changes are staged
    or already committed. Denied and failed attempts must be logged too.
    """
    with _lock:
        last = db.scalar(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1))
        ev = AuditEvent(
            timestamp=utcnow(), actor_id=actor_id, actor_role=actor_role, action=action,
            outcome=AuditOutcome(outcome).value, resource_type=resource_type,
            resource_id=resource_id, ip_address=ip_address,
            details=redact(details or {}),
            prev_hash=last.event_hash if last else GENESIS_HASH, event_hash="",
        )
        ev.event_hash = _compute_hash(ev.prev_hash, _fields(ev))
        db.add(ev)
        db.commit()
        return ev


def verify_chain(db: Session) -> tuple[bool, int | None, int]:
    """Returns (is_intact, first_bad_event_id_or_None, events_checked)."""
    expected_prev, count = GENESIS_HASH, 0
    for ev in db.scalars(select(AuditEvent).order_by(AuditEvent.id)):
        count += 1
        good = ev.prev_hash == expected_prev and hmac.compare_digest(
            ev.event_hash, _compute_hash(ev.prev_hash, _fields(ev))
        )
        if not good:
            return False, ev.id, count
        expected_prev = ev.event_hash
    return True, None, count


def list_events(db: Session, *, action: str | None = None, outcome: str | None = None,
                actor_id: str | None = None, limit: int = 100, offset: int = 0) -> list[AuditEvent]:
    q = select(AuditEvent).order_by(AuditEvent.id.desc())
    if action:
        q = q.where(AuditEvent.action == action)
    if outcome:
        q = q.where(AuditEvent.outcome == outcome)
    if actor_id:
        q = q.where(AuditEvent.actor_id == actor_id)
    return list(db.scalars(q.limit(min(limit, 500)).offset(max(offset, 0))))