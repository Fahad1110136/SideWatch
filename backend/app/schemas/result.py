from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.app.core.enums import Decision, Severity


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    submission_id: str
    decision: Decision
    severity: Severity
    confidence: float
    p_value: float | None
    effect_size: float | None
    ci_low: float | None
    ci_high: float | None
    evidence: dict
    reasons: list[str]
    rule_name: str
    rule_version: str
    engine_version: str
    thresholds: dict
    created_at: datetime