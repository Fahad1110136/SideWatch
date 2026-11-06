from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.enums import Implementation, SubmissionStatus
from backend.app.schemas.common import StrictModel


class SubmissionCreate(StrictModel):
    label: str = Field(min_length=1, max_length=80, pattern=r"^[\w .\-()]+$")
    implementation: Implementation
    fixture_id: str = Field(pattern=r"^[a-z0-9_]{1,40}$")   # checked against whitelist in service layer
    sample_size: int = Field(ge=30, le=5000)
    warmup_runs: int = Field(default=50, ge=0, le=500)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label: str
    implementation: Implementation
    fixture_id: str
    sample_size: int
    warmup_runs: int
    seed: int | None
    status: SubmissionStatus
    created_at: datetime
    completed_at: datetime | None