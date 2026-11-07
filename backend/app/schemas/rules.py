from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import StrictModel


class RuleUpdate(StrictModel):
    value: float = Field(allow_inf_nan=False)
    confirm: bool          # high-impact action: must be explicitly true


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    value: float
    version: int
    updated_at: datetime