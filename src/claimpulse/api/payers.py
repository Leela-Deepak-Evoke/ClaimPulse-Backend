from fastapi import APIRouter, Response, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from claimpulse.db import DbSession
from claimpulse.deps import AdminUser, CurrentUser
from claimpulse.errors import AppError
from claimpulse.models import Claim, Payer
from claimpulse.schemas.payer import PayerRead, PayerWrite

router = APIRouter(prefix="/payers", tags=["payers"])

_PAYER_EXISTS = AppError(409, "PAYER_ALREADY_EXISTS", "Payer name or code is already used.")


def _get_or_404(db: Session, payer_id: int) -> Payer:
    payer = db.get(Payer, payer_id)
    if payer is None:
        raise AppError(404, "PAYER_NOT_FOUND", "Payer not found.")
    return payer


def _ensure_unique(db: Session, data: PayerWrite, exclude_id: int | None = None) -> None:
    stmt = select(Payer.id).where(
        or_(Payer.payer_name == data.payer_name, Payer.payer_code == data.payer_code)
    )
    if exclude_id is not None:
        stmt = stmt.where(Payer.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise _PAYER_EXISTS


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _PAYER_EXISTS from exc


@router.get("", summary="List payers")
def list_payers(db: DbSession, _user: CurrentUser) -> list[PayerRead]:
    return [PayerRead.model_validate(p) for p in db.scalars(select(Payer).order_by(Payer.id))]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Add a payer (Admin only)")
def create_payer(data: PayerWrite, db: DbSession, _admin: AdminUser) -> PayerRead:
    _ensure_unique(db, data)
    payer = Payer(**data.model_dump())
    db.add(payer)
    _commit(db)
    db.refresh(payer)
    return PayerRead.model_validate(payer)


@router.put("/{payer_id}", summary="Update a payer (Admin only)")
def update_payer(payer_id: int, data: PayerWrite, db: DbSession, _admin: AdminUser) -> PayerRead:
    payer = _get_or_404(db, payer_id)
    _ensure_unique(db, data, exclude_id=payer_id)
    for field, value in data.model_dump().items():
        setattr(payer, field, value)
    _commit(db)
    db.refresh(payer)
    return PayerRead.model_validate(payer)


@router.delete(
    "/{payer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a payer with no claims (Admin only)",
)
def delete_payer(payer_id: int, db: DbSession, _admin: AdminUser) -> Response:
    _get_or_404(db, payer_id)
    if db.scalar(select(func.count(Claim.id)).where(Claim.payer_id == payer_id)):
        raise AppError(409, "PAYER_HAS_CLAIMS", "Payer has claims and cannot be deleted.")
    db.execute(delete(Payer).where(Payer.id == payer_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
