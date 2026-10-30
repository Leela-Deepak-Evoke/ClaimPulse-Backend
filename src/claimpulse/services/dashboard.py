from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from claimpulse.enums import ClaimStatus
from claimpulse.models import Claim, Payer
from claimpulse.schemas.dashboard import DashboardSummary, DenialReasonCount, PayerStats

_PENDING = {ClaimStatus.SUBMITTED, ClaimStatus.RESUBMITTED}
_ZERO = Decimal("0.00")


def _rate(part: Decimal | int, whole: Decimal | int) -> float:
    return round(float(part) / float(whole) * 100, 1) if whole else 0.0


def summary(db: Session) -> DashboardSummary:
    rows = db.execute(
        select(
            Claim.status,
            func.count(Claim.id),
            func.coalesce(func.sum(Claim.billed_amount), 0),
            func.coalesce(func.sum(Claim.paid_amount), 0),
        ).group_by(Claim.status)
    ).all()

    by_status = {status: 0 for status in ClaimStatus}
    total_billed = total_collected = pending_amount = _ZERO
    for status, count, billed, collected in rows:
        by_status[ClaimStatus(status)] = count
        total_billed += Decimal(billed or 0)
        total_collected += Decimal(collected or 0)
        if ClaimStatus(status) in _PENDING:
            pending_amount += Decimal(billed or 0)

    total_claims = sum(by_status.values())
    return DashboardSummary(
        total_claims=total_claims,
        by_status=by_status,
        pending_claims=sum(by_status[s] for s in _PENDING),
        total_billed=total_billed,
        total_collected=total_collected,
        pending_amount=pending_amount,
        denial_rate=_rate(by_status[ClaimStatus.DENIED], total_claims),
        collection_rate=_rate(total_collected, total_billed),
    )


def payer_stats(db: Session) -> list[PayerStats]:
    denied = func.count(Claim.id).filter(Claim.status == ClaimStatus.DENIED.value)
    rows = db.execute(
        select(
            Payer.id,
            Payer.payer_name,
            func.count(Claim.id),
            denied,
            func.coalesce(func.sum(Claim.billed_amount), 0),
            func.coalesce(func.sum(Claim.paid_amount), 0),
        )
        .select_from(Payer)
        .outerjoin(Claim, Claim.payer_id == Payer.id)
        .group_by(Payer.id, Payer.payer_name)
        .order_by(Payer.id)
    ).all()
    return [
        PayerStats(
            payer_id=payer_id,
            payer_name=name,
            claims=claims,
            denied=denied_count,
            billed=Decimal(billed or 0),
            collected=Decimal(collected or 0),
            denial_rate=_rate(denied_count, claims),
        )
        for payer_id, name, claims, denied_count, billed, collected in rows
    ]


def denial_reasons(db: Session) -> list[DenialReasonCount]:
    count = func.count(Claim.id)
    rows = db.execute(
        select(Claim.denial_reason, count)
        .where(Claim.status == ClaimStatus.DENIED.value)
        .group_by(Claim.denial_reason)
        .order_by(desc(count), Claim.denial_reason)
    ).all()
    return [DenialReasonCount(denial_reason=reason or "Unspecified", count=n) for reason, n in rows]
