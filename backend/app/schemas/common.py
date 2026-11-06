from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ErrorResponse(BaseModel):
    code: str          # stable, e.g. "AUTH_INVALID_CREDENTIALS"
    message: str       # safe, generic text, never a stack trace
    request_id: str | None = None