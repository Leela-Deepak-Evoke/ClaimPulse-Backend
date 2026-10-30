from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from claimpulse.enums import Gender
from claimpulse.schemas.common import Name

_Phone = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]
_MemberId = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    date_of_birth: date
    gender: Gender | None
    phone: str | None
    insurance_member_id: str | None
    claim_count: int = 0
    created_at: datetime


class PatientRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str


class ClaimsSummary(BaseModel):
    total: int
    paid: int
    denied: int
    pending: int


class PatientDetail(PatientRead):
    claims_summary: ClaimsSummary


class PatientWrite(BaseModel):
    full_name: Name
    date_of_birth: date
    gender: Gender | None = None
    phone: _Phone | None = None
    insurance_member_id: _MemberId | None = None

    @field_validator("date_of_birth")
    @classmethod
    def not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        return value
