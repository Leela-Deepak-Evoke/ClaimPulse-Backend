import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import ColumnElement, desc, func, or_, select
from sqlalchemy.orm import Session

from claimpulse.enums import ClaimStatus
from claimpulse.errors import AppError
from claimpulse.models import Claim, Patient, Payer, User
from claimpulse.pagination import PageParams
from claimpulse.schemas.claim import ClaimStatusUpdate, ClaimWrite

_EDITABLE = {ClaimStatus.SUBMITTED, ClaimStatus.DENIED}
_TRANSITIONS: dict[ClaimStatus, set[ClaimStatus]] = {
    ClaimStatus.SUBMITTED: {ClaimStatus.PAID, ClaimStatus.DENIED},
    ClaimStatus.RESUBMITTED: {ClaimStatus.PAID, ClaimStatus.DENIED},
    ClaimStatus.DENIED: {ClaimStatus.RESUBMITTED},
    ClaimStatus.PAID: set(),
}
_CLAIM_CODE = re.compile(r"^CLM-(\d+)$", re.IGNORECASE)
_SORT_COLUMNS = {
    "service_date": Claim.service_date,
    "billed_amount": Claim.billed_amount,
    "created_at": Claim.created_at,
}


@dataclass
class ClaimFilters:
    status: ClaimStatus | None = None
    payer_id: int | None = None
    patient_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    search: str | None = None
    sort: str = "-created_at"


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_claim_or_404(db: Session, claim_id: int) -> Claim:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise AppError(404, "CLAIM_NOT_FOUND", "Claim not found.")
    return claim


def _ensure_patient_and_payer(db: Session, patient_id: int, payer_id: int) -> None:
    if db.get(Patient, patient_id) is None:
        raise AppError(404, "PATIENT_NOT_FOUND", "Patient not found.")
    if db.get(Payer, payer_id) is None:
        raise AppError(404, "PAYER_NOT_FOUND", "Payer not found.")


def _conditions(filters: ClaimFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.status:
        conditions.append(Claim.status == filters.status.value)
    if filters.payer_id:
        conditions.append(Claim.payer_id == filters.payer_id)
    if filters.patient_id:
        conditions.append(Claim.patient_id == filters.patient_id)
    if filters.date_from:
        conditions.append(Claim.service_date >= filters.date_from)
    if filters.date_to:
        conditions.append(Claim.service_date <= filters.date_to)
    if filters.search:
        term = filters.search.strip()
        matches = [
            Claim.patient.has(Patient.full_name.ilike(f"%{escape_like(term)}%", escape="\\"))
        ]
        code = _CLAIM_CODE.match(term)
        if code:
            matches.append(Claim.id == int(code.group(1)))
        conditions.append(or_(*matches))
    return conditions


def list_claims(db: Session, filters: ClaimFilters, page: PageParams) -> tuple[list[Claim], int]:
    conditions = _conditions(filters)
    total = db.scalar(select(func.count(Claim.id)).where(*conditions)) or 0
    column = _SORT_COLUMNS[filters.sort.lstrip("-")]
    order = desc(column) if filters.sort.startswith("-") else column
    stmt = (
        select(Claim)
        .where(*conditions)
        .order_by(order, desc(Claim.id))
        .limit(page.size)
        .offset(page.offset)
    )
    return list(db.scalars(stmt).unique()), total


def create_claim(db: Session, data: ClaimWrite, user: User) -> Claim:
    _ensure_patient_and_payer(db, data.patient_id, data.payer_id)
    claim = Claim(
        **data.model_dump(),
        status=ClaimStatus.SUBMITTED.value,
        created_by=user.id,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def update_claim(db: Session, claim: Claim, data: ClaimWrite) -> Claim:
    if ClaimStatus(claim.status) not in _EDITABLE:
        raise AppError(409, "CLAIM_NOT_EDITABLE", f"A {claim.status} claim cannot be edited.")
    _ensure_patient_and_payer(db, data.patient_id, data.payer_id)
    for field, value in data.model_dump().items():
        setattr(claim, field, value)
    db.commit()
    db.refresh(claim)
    return claim


def change_status(db: Session, claim: Claim, data: ClaimStatusUpdate) -> Claim:
    current = ClaimStatus(claim.status)
    if data.status not in _TRANSITIONS[current]:
        raise AppError(
            409,
            "INVALID_STATUS_TRANSITION",
            f"A {current} claim cannot move to {data.status}.",
        )

    if data.status == ClaimStatus.PAID:
        if data.paid_amount is None:
            raise AppError(422, "PAID_AMOUNT_REQUIRED", "paid_amount is required for PAID.")
        if data.paid_amount > claim.billed_amount:
            raise AppError(
                422, "PAID_AMOUNT_EXCEEDS_BILLED", "paid_amount cannot exceed billed_amount."
            )
        claim.paid_amount = data.paid_amount
        claim.denial_reason = None
    elif data.status == ClaimStatus.DENIED:
        if data.denial_reason is None:
            raise AppError(422, "DENIAL_REASON_REQUIRED", "denial_reason is required for DENIED.")
        claim.denial_reason = data.denial_reason.value
        claim.paid_amount = None
    else:
        claim.paid_amount = None

    claim.status = data.status.value
    if data.notes is not None:
        claim.notes = data.notes
    db.commit()
    db.refresh(claim)
    return claim
