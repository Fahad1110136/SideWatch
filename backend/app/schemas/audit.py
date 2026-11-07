from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.app.core.enums import AuditOutcome


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    actor_id: str | None
    actor_role: str | None
    action: str
    outcome: AuditOutcome
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    details: dict