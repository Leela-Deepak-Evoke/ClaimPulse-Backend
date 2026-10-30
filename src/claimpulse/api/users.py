from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from claimpulse.db import DbSession
from claimpulse.deps import AdminUser
from claimpulse.enums import Role
from claimpulse.errors import AppError
from claimpulse.models import User
from claimpulse.pagination import Pagination
from claimpulse.schemas.common import Page
from claimpulse.schemas.user import UserRead, UserUpdate
from claimpulse.services.claims import escape_like

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", summary="List users (Admin only)")
def list_users(
    db: DbSession,
    _admin: AdminUser,
    page: Pagination,
    role: Role | None = None,
    is_active: bool | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[UserRead]:
    conditions = []
    if role:
        conditions.append(User.role == role.value)
    if is_active is not None:
        conditions.append(User.is_active == is_active)
    if search:
        pattern = f"%{escape_like(search.strip())}%"
        conditions.append(
            or_(
                User.full_name.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count(User.id)).where(*conditions)) or 0
    users = db.scalars(
        select(User).where(*conditions).order_by(User.id).limit(page.size).offset(page.offset)
    )
    return Page(
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        page=page.page,
        size=page.size,
    )


@router.patch("/{user_id}", summary="Change role or activate/deactivate (Admin only)")
def update_user(user_id: int, data: UserUpdate, db: DbSession, admin: AdminUser) -> UserRead:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "User not found.")
    if user.id == admin.id and (data.is_active is False or data.role == Role.BILLER):
        raise AppError(
            409, "CANNOT_MODIFY_SELF", "You cannot deactivate or demote your own account."
        )
    if data.role is not None:
        user.role = data.role.value
    if data.is_active is not None:
        user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)
