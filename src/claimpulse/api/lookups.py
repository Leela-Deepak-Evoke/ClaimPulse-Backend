from fastapi import APIRouter

from claimpulse.deps import CurrentUser
from claimpulse.enums import ClaimStatus, DenialReason, Gender, Role
from claimpulse.schemas.dashboard import Lookups

router = APIRouter(tags=["lookups"])


@router.get("/lookups", summary="Fixed lists for dropdowns and badges")
def lookups(_user: CurrentUser) -> Lookups:
    return Lookups(
        claim_statuses=list(ClaimStatus),
        denial_reasons=list(DenialReason),
        genders=list(Gender),
        roles=list(Role),
    )
