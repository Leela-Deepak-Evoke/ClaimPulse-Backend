from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import delete

from claimpulse.db import DbSession
from claimpulse.deps import AdminUser, CurrentUser
from claimpulse.enums import ClaimStatus
from claimpulse.models import Claim
from claimpulse.pagination import Pagination
from claimpulse.schemas.claim import ClaimRead, ClaimStatusUpdate, ClaimWrite
from claimpulse.schemas.common import Page
from claimpulse.services import claims as service

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("", summary="List, filter, search and sort claims")
def list_claims(
    db: DbSession,
    _user: CurrentUser,
    page: Pagination,
    status_filter: Annotated[ClaimStatus | None, Query(alias="status")] = None,
    payer_id: int | None = None,
    patient_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[
        str, Query(pattern=r"^-?(service_date|billed_amount|created_at)$")
    ] = "-created_at",
) -> Page[ClaimRead]:
    filters = service.ClaimFilters(
        status=status_filter,
        payer_id=payer_id,
        patient_id=patient_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        sort=sort,
    )
    claims, total = service.list_claims(db, filters, page)
    return Page(
        items=[ClaimRead.model_validate(c) for c in claims],
        total=total,
        page=page.page,
        size=page.size,
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a claim")
def create_claim(data: ClaimWrite, db: DbSession, user: CurrentUser) -> ClaimRead:
    return ClaimRead.model_validate(service.create_claim(db, data, user))


@router.get("/{claim_id}", summary="Claim details")
def get_claim(claim_id: int, db: DbSession, _user: CurrentUser) -> ClaimRead:
    return ClaimRead.model_validate(service.get_claim_or_404(db, claim_id))


@router.put("/{claim_id}", summary="Edit claim details (SUBMITTED or DENIED only)")
def update_claim(claim_id: int, data: ClaimWrite, db: DbSession, _user: CurrentUser) -> ClaimRead:
    claim = service.get_claim_or_404(db, claim_id)
    return ClaimRead.model_validate(service.update_claim(db, claim, data))


@router.patch("/{claim_id}/status", summary="Mark Paid / Denied / Resubmitted")
def change_claim_status(
    claim_id: int, data: ClaimStatusUpdate, db: DbSession, _user: CurrentUser
) -> ClaimRead:
    claim = service.get_claim_or_404(db, claim_id)
    return ClaimRead.model_validate(service.change_status(db, claim, data))


@router.delete(
    "/{claim_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a claim (Admin only)"
)
def delete_claim(claim_id: int, db: DbSession, _admin: AdminUser) -> Response:
    service.get_claim_or_404(db, claim_id)
    db.execute(delete(Claim).where(Claim.id == claim_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
