from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer, StringConstraints

Money = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str, when_used="json")]
MoneyIn = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int
