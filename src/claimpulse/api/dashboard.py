from fastapi import APIRouter

from claimpulse.db import DbSession
from claimpulse.deps import CurrentUser
from claimpulse.schemas.dashboard import DashboardSummary, DenialReasonCount, PayerStats
from claimpulse.services import dashboard as service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", summary="Stat cards and billed vs collected")
def summary(db: DbSession, _user: CurrentUser) -> DashboardSummary:
    return service.summary(db)


@router.get("/payers", summary="Claims by payer")
def payers(db: DbSession, _user: CurrentUser) -> list[PayerStats]:
    return service.payer_stats(db)


@router.get("/denial-reasons", summary="Denials by reason, most common first")
def denial_reasons(db: DbSession, _user: CurrentUser) -> list[DenialReasonCount]:
    return service.denial_reasons(db)
