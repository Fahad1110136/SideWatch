from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.orm import Session

from backend.app.core import errors
from backend.app.core.deps import AuthContext, client_ip, require_roles
from backend.app.core.enums import AuditOutcome, Role
from backend.app.database import get_db
from backend.app.repositories import audit_repo, rule_repo
from backend.app.schemas.rules import RuleOut, RuleUpdate

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("", response_model=list[RuleOut])
def list_rules(ctx: AuthContext = Depends(require_roles(Role.ADMIN, Role.OPERATOR)),
               db: Session = Depends(get_db)):
    return rule_repo.list_rules(db)


@router.put("/{key}", response_model=RuleOut)
def update_rule(body: RuleUpdate, request: Request, key: str = Path(max_length=64),
                ctx: AuthContext = Depends(require_roles(Role.ADMIN)),
                db: Session = Depends(get_db)):
    actor = dict(actor_id=ctx.user.id, actor_role=ctx.user.role, ip_address=client_ip(request))
    if key not in rule_repo.BOUNDS:
        raise errors.not_found()
    if not body.confirm:
        raise errors.confirmation_required()

    old_value = rule_repo.get_all(db).get(key)
    try:
        rule = rule_repo.update_value(db, key, body.value, ctx.user.id)
    except ValueError:
        audit_repo.append_event(db, "admin.rule_change", AuditOutcome.FAILURE, **actor,
                                resource_type="rule", resource_id=key,
                                details={"reason": "out_of_range", "attempted": body.value})
        raise errors.invalid_rule_value()

    audit_repo.append_event(db, "admin.rule_change", AuditOutcome.SUCCESS, **actor,
                            resource_type="rule", resource_id=key,
                            details={"old": old_value, "new": rule.value, "version": rule.version})
    return rule