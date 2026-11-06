from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.enums import Role
from backend.app.schemas.common import StrictModel

USERNAME_PATTERN = r"^[a-zA-Z0-9_.-]{3,32}$"


class LoginRequest(StrictModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    password: str = Field(min_length=1, max_length=128)


class UserCreate(StrictModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    password: str = Field(min_length=12, max_length=128)
    role: Role

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not (any(c.isalpha() for c in v) and any(c.isdigit() for c in v)):
            raise ValueError("password must contain letters and digits")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    role: Role
    is_active: bool