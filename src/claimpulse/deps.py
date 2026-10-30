from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from claimpulse.db import DbSession
from claimpulse.enums import Role
from claimpulse.errors import AppError
from claimpulse.models import User
from claimpulse.security import decode_access_token

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
_BEARER = {"WWW-Authenticate": "Bearer"}


def get_current_user(token: Annotated[str | None, Depends(_oauth2_scheme)], db: DbSession) -> User:
    if token is None:
        raise AppError(401, "NOT_AUTHENTICATED", "Not authenticated.", _BEARER)
    user = db.get(User, decode_access_token(token))
    if user is None:
        raise AppError(401, "TOKEN_INVALID", "Token is invalid.", _BEARER)
    if not user.is_active:
        raise AppError(403, "ACCOUNT_INACTIVE", "Account is deactivated.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise AppError(
                403, "PERMISSION_DENIED", "You do not have permission to perform this action."
            )
        return user

    return checker


AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
