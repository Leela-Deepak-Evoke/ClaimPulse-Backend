from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from claimpulse.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), server_default="BILLER")
    is_active: Mapped[bool] = mapped_column(server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Payer(Base):
    __tablename__ = "payers"

    id: Mapped[int] = mapped_column(primary_key=True)
    payer_name: Mapped[str] = mapped_column(String(100), unique=True)
    payer_code: Mapped[str] = mapped_column(String(20), unique=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(10))
    phone: Mapped[str | None] = mapped_column(String(30))
    insurance_member_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    payer_id: Mapped[int] = mapped_column(ForeignKey("payers.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    service_date: Mapped[date] = mapped_column(Date)
    cpt_code: Mapped[str] = mapped_column(String(10))
    icd_code: Mapped[str] = mapped_column(String(10))
    billed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), server_default="SUBMITTED")
    denial_reason: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    patient: Mapped[Patient] = relationship(lazy="joined", innerjoin=True)
    payer: Mapped[Payer] = relationship(lazy="joined", innerjoin=True)
    creator: Mapped[User | None] = relationship(lazy="joined")
