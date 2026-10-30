from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from claimpulse.enums import Role
from claimpulse.schemas.common import Name

_BCRYPT_MAX_BYTES = 72


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: Role
    is_active: bool
    created_at: datetime


class UserRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str


class UserCreate(BaseModel):
    full_name: Name
    email: EmailStr
    password: Annotated[str, Field(min_length=8)]
    role: Role = Role.BILLER

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if len(value.encode()) > _BCRYPT_MAX_BYTES:
            raise ValueError("Password must be at most 72 bytes long.")
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one letter and one digit.")
        return value


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UserUpdate":
        if self.role is None and self.is_active is None:
            raise ValueError("Provide at least one of: role, is_active.")
        return self


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int
    user: UserRead
