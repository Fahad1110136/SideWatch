from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.deps import AuthContext, require_roles
from backend.app.core.enums import AuditOutcome, Role
from backend.app.database import get_db
from backend.app.repositories import audit_repo
from backend.app.schemas.audit import AuditEventOut

router = APIRouter(prefix="/api/audit", tags=["audit"])
admin_only = require_roles(Role.ADMIN)


@router.get("", response_model=list[AuditEventOut])
def list_audit(
    action: str | None = Query(None, max_length=48),
    outcome: AuditOutcome | None = None,
    actor_id: str | None = Query(None, max_length=32),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: AuthContext = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return audit_repo.list_events(
        db, action=action, outcome=outcome.value if outcome else None,
        actor_id=actor_id, limit=limit, offset=offset,
    )


@router.get("/verify")
def verify(ctx: AuthContext = Depends(admin_only), db: Session = Depends(get_db)):
    intact, bad_id, count = audit_repo.verify_chain(db)
    return {"intact": intact, "first_bad_event_id": bad_id, "events_checked": count}