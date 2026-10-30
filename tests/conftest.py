import os
from collections.abc import Iterator
from datetime import date

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret-key-for-unit-tests-only-0123456789"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from claimpulse.db import Base, get_db
from claimpulse.main import app
from claimpulse.models import Claim, Patient, Payer, User
from claimpulse.security import hash_password

PASSWORD = "Password1"


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        db.add_all(
            [
                User(
                    full_name="Ada Admin",
                    email="admin@test.io",
                    role="ADMIN",
                    password_hash=hash_password(PASSWORD),
                    is_active=True,
                ),
                User(
                    full_name="Bill Biller",
                    email="biller@test.io",
                    role="BILLER",
                    password_hash=hash_password(PASSWORD),
                    is_active=True,
                ),
                User(
                    full_name="Ina Inactive",
                    email="inactive@test.io",
                    role="BILLER",
                    password_hash=hash_password(PASSWORD),
                    is_active=False,
                ),
                Payer(payer_name="Medicare", payer_code="MCR"),
                Payer(payer_name="Aetna", payer_code="AET"),
                Patient(
                    full_name="Emily Johnson",
                    date_of_birth=date(1986, 7, 22),
                    gender="FEMALE",
                    insurance_member_id="AET553201",
                ),
                Patient(full_name="Michael Brown", date_of_birth=date(1975, 1, 3)),
            ]
        )
        db.commit()
    yield factory
    engine.dispose()


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def admin(client: TestClient) -> dict[str, str]:
    return _headers(client, "admin@test.io")


@pytest.fixture
def biller(client: TestClient) -> dict[str, str]:
    return _headers(client, "biller@test.io")


@pytest.fixture
def seed_claims(session_factory: sessionmaker[Session]) -> None:
    """SUBMITTED, PAID, DENIED claims for patient 1 / payer 1 and one for patient 2 / payer 2."""
    rows = [
        ("SUBMITTED", "100.00", None, None),
        ("PAID", "200.00", "150.00", None),
        ("DENIED", "300.00", None, "Coding error"),
    ]
    with session_factory() as db:
        for status, billed, paid, reason in rows:
            db.add(
                Claim(
                    patient_id=1,
                    payer_id=1,
                    created_by=2,
                    service_date=date(2026, 8, 1),
                    cpt_code="99213",
                    icd_code="J06.9",
                    billed_amount=billed,
                    paid_amount=paid,
                    status=status,
                    denial_reason=reason,
                )
            )
        db.add(
            Claim(
                patient_id=2,
                payer_id=2,
                created_by=2,
                service_date=date(2026, 8, 9),
                cpt_code="71046",
                icd_code="R05.9",
                billed_amount="400.00",
                status="RESUBMITTED",
            )
        )
        db.commit()
