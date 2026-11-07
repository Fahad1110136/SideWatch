from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import RuleConfig
from backend.app.models.tables import utcnow

DEFAULTS = {"alpha": 0.01, "min_effect_size": 0.2, "ci_level": 0.99}
BOUNDS = {"alpha": (0.0001, 0.1), "min_effect_size": (0.0, 5.0), "ci_level": (0.8, 0.999)}


def seed_defaults(db: Session) -> None:
    for key, value in DEFAULTS.items():
        if db.get(RuleConfig, key) is None:
            db.add(RuleConfig(key=key, value=value))
    db.commit()


def get_all(db: Session) -> dict[str, float]:
    return {r.key: r.value for r in db.scalars(select(RuleConfig))}


def update_value(db: Session, key: str, value: float, user_id: str) -> RuleConfig:
    if key not in BOUNDS:
        raise ValueError("unknown rule key")
    low, high = BOUNDS[key]
    if not (low <= value <= high):
        raise ValueError("value out of permitted range")
    rule = db.get(RuleConfig, key)
    rule.value = value
    rule.version += 1
    rule.updated_by = user_id
    rule.updated_at = utcnow()
    db.commit()
    return rule

def list_rules(db: Session) -> list[RuleConfig]:
    return list(db.scalars(select(RuleConfig).order_by(RuleConfig.key)))