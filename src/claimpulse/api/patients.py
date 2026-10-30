from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from claimpulse.db import DbSession
from claimpulse.deps import AdminUser, CurrentUser
from claimpulse.enums import ClaimStatus
from claimpulse.errors import AppError
from claimpulse.models import Claim, Patient
from claimpulse.pagination import Pagination
from claimpulse.schemas.common import Page
from claimpulse.schemas.patient import ClaimsSummary, PatientDetail, PatientRead, PatientWrite
from claimpulse.services.claims import escape_like

router = APIRouter(prefix="/patients", tags=["patients"])

_PENDING = {ClaimStatus.SUBMITTED.value, ClaimStatus.RESUBMITTED.value}


def _get_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise AppError(404, "PATIENT_NOT_FOUND", "Patient not found.")
    return patient


def _claim_counts(db: Session, patient_id: int) -> dict[str, int]:
    rows = db.execute(
        select(Claim.status, func.count(Claim.id))
        .where(Claim.patient_id == patient_id)
        .group_by(Claim.status)
    )
    return {status_: count for status_, count in rows}


def _to_read(patient: Patient, claim_count: int = 0) -> PatientRead:
    return PatientRead.model_validate(patient).model_copy(update={"claim_count": claim_count})


@router.get("", summary="List and search patients")
def list_patients(
    db: DbSession,
    _user: CurrentUser,
    page: Pagination,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[PatientRead]:
    conditions = []
    if search:
        pattern = f"%{escape_like(search.strip())}%"
        conditions.append(
            or_(
                Patient.full_name.ilike(pattern, escape="\\"),
                Patient.insurance_member_id.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count(Patient.id)).where(*conditions)) or 0
    rows = db.execute(
        select(Patient, func.count(Claim.id))
        .outerjoin(Claim, Claim.patient_id == Patient.id)
        .where(*conditions)
        .group_by(Patient.id)
        .order_by(Patient.full_name, Patient.id)
        .limit(page.size)
        .offset(page.offset)
    ).all()
    return Page(
        items=[_to_read(patient, count) for patient, count in rows],
        total=total,
        page=page.page,
        size=page.size,
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Add a patient")
def create_patient(data: PatientWrite, db: DbSession, _user: CurrentUser) -> PatientRead:
    patient = Patient(
        full_name=data.full_name,
        date_of_birth=data.date_of_birth,
        gender=data.gender.value if data.gender else None,
        phone=data.phone,
        insurance_member_id=data.insurance_member_id,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return _to_read(patient)


@router.get("/{patient_id}", summary="One patient with a claims summary")
def get_patient(patient_id: int, db: DbSession, _user: CurrentUser) -> PatientDetail:
    patient = _get_or_404(db, patient_id)
    counts = _claim_counts(db, patient_id)
    total = sum(counts.values())
    summary = ClaimsSummary(
        total=total,
        paid=counts.get(ClaimStatus.PAID.value, 0),
        denied=counts.get(ClaimStatus.DENIED.value, 0),
        pending=sum(counts.get(s, 0) for s in _PENDING),
    )
    return PatientDetail(**_to_read(patient, total).model_dump(), claims_summary=summary)


@router.put("/{patient_id}", summary="Update a patient")
def update_patient(
    patient_id: int, data: PatientWrite, db: DbSession, _user: CurrentUser
) -> PatientRead:
    patient = _get_or_404(db, patient_id)
    patient.full_name = data.full_name
    patient.date_of_birth = data.date_of_birth
    patient.gender = data.gender.value if data.gender else None
    patient.phone = data.phone
    patient.insurance_member_id = data.insurance_member_id
    db.commit()
    db.refresh(patient)
    return _to_read(patient, sum(_claim_counts(db, patient_id).values()))


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a patient and their claims (Admin only)",
)
def delete_patient(patient_id: int, db: DbSession, _admin: AdminUser) -> Response:
    _get_or_404(db, patient_id)
    db.execute(delete(Patient).where(Patient.id == patient_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
