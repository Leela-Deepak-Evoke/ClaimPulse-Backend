from datetime import date, datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
)

from claimpulse.enums import ClaimStatus, DenialReason
from claimpulse.schemas.common import Money, MoneyIn
from claimpulse.schemas.patient import PatientRef
from claimpulse.schemas.payer import PayerRef
from claimpulse.schemas.user import UserRef

_Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient: PatientRef
    payer: PayerRef
    created_by: UserRef | None = Field(validation_alias="creator")
    service_date: date
    cpt_code: str
    icd_code: str
    billed_amount: Money
    paid_amount: Money | None
    status: ClaimStatus
    denial_reason: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def claim_code(self) -> str:
        return f"CLM-{self.id:04d}"


class ClaimWrite(BaseModel):
    patient_id: int
    payer_id: int
    service_date: date
    cpt_code: Annotated[
        str,
        StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9]{5}$"),
    ]
    icd_code: Annotated[
        str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=3, max_length=10)
    ]
    billed_amount: MoneyIn
    notes: _Notes | None = None

    @field_validator("service_date")
    @classmethod
    def not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Service date cannot be in the future.")
        return value


class ClaimStatusUpdate(BaseModel):
    status: ClaimStatus
    paid_amount: MoneyIn | None = None
    denial_reason: DenialReason | None = None
    notes: _Notes | None = None
