from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from claimpulse.schemas.common import Name


class PayerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payer_name: str
    payer_code: str
    contact_phone: str | None
    created_at: datetime


class PayerRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payer_name: str


class PayerWrite(BaseModel):
    payer_name: Name
    payer_code: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            to_upper=True,
            min_length=2,
            max_length=20,
            pattern=r"^[A-Za-z0-9]+$",
        ),
    ]
    contact_phone: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None
    ) = None
