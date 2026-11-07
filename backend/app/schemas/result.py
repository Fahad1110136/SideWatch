# from datetime import datetime

# from pydantic import BaseModel, ConfigDict

# from backend.app.core.enums import Decision, Severity


# class ResultOut(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#     id: str
#     submission_id: str
#     decision: Decision
#     severity: Severity
#     confidence: float
#     p_value: float | None
#     effect_size: float | None
#     ci_low: float | None
#     ci_high: float | None
#     evidence: dict
#     reasons: list[str]
#     rule_name: str
#     rule_version: str
#     engine_version: str
#     thresholds: dict
#     created_at: datetime





from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.enums import Decision, Severity
from backend.app.schemas.common import StrictModel


class EngineResult(StrictModel):
    """What the engine must return. Anything else is rejected and the run fails safely."""
    decision: Decision
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    p_value: float | None = Field(default=None, ge=0, le=1)
    effect_size: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    evidence: dict
    reasons: list[str] = Field(min_length=1)   # every result must be explainable
    rule_name: str = Field(min_length=1, max_length=64)
    rule_version: str = Field(min_length=1, max_length=16)
    engine_version: str = Field(min_length=1, max_length=16)
    thresholds: dict


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