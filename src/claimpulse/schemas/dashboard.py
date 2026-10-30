from pydantic import BaseModel

from claimpulse.enums import ClaimStatus, DenialReason, Gender, Role
from claimpulse.schemas.common import Money


class DashboardSummary(BaseModel):
    total_claims: int
    by_status: dict[ClaimStatus, int]
    pending_claims: int
    total_billed: Money
    total_collected: Money
    pending_amount: Money
    denial_rate: float
    collection_rate: float


class PayerStats(BaseModel):
    payer_id: int
    payer_name: str
    claims: int
    denied: int
    billed: Money
    collected: Money
    denial_rate: float


class DenialReasonCount(BaseModel):
    denial_reason: str
    count: int


class Lookups(BaseModel):
    claim_statuses: list[ClaimStatus]
    denial_reasons: list[DenialReason]
    genders: list[Gender]
    roles: list[Role]
