from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from claimpulse.config import get_settings
from claimpulse.db import DbSession
from claimpulse.deps import AdminUser, CurrentUser
from claimpulse.errors import AppError
from claimpulse.models import User
from claimpulse.schemas.user import LoginResponse, UserCreate, UserRead
from claimpulse.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_TAKEN = AppError(409, "EMAIL_ALREADY_EXISTS", "A user with this email already exists.")


@router.post("/login", summary="Log in and get a token")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == form.username.strip().lower()))
    if user is None or not verify_password(form.password, user.password_hash):
        raise AppError(
            401,
            "INVALID_CREDENTIALS",
            "Incorrect email or password.",
            {"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise AppError(403, "ACCOUNT_INACTIVE", "Account is deactivated.")
    return LoginResponse(
        access_token=create_access_token(user.id),
        expires_in=get_settings().access_token_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.get("/me", summary="Current user")
def me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    summary="Create a team member (Admin only)",
)
def create_user(data: UserCreate, db: DbSession, _admin: AdminUser) -> UserRead:
    email = data.email.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise _EMAIL_TAKEN
    user = User(
        full_name=data.full_name,
        email=email,
        password_hash=hash_password(data.password),
        role=data.role.value,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _EMAIL_TAKEN from exc
    db.refresh(user)
    return UserRead.model_validate(user)
