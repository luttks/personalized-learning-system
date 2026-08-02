from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import (
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import (
    InvalidTokenTypeError,
    TokenDecodeError,
    TokenType,
    decode_token,
)
from app.db.session import get_db_session
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    description=(
        "Nhập access_token nhận được từ "
        "POST /api/v1/auth/login."
    ),
    auto_error=False,
)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không thể xác thực người dùng.",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )

    if credentials is None:
        raise credentials_exception

    try:
        payload = decode_token(
            credentials.credentials,
            TokenType.ACCESS,
        )

        user_id = UUID(payload["sub"])
    except (
        TokenDecodeError,
        InvalidTokenTypeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise credentials_exception from error

    user = await session.get(
        User,
        user_id,
    )

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị khóa.",
        )

    return user


def require_roles(
    *allowed_roles: UserRole,
) -> Callable[..., User]:
    async def role_checker(
        current_user: Annotated[
            User,
            Depends(get_current_user),
        ],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Bạn không có quyền thực hiện "
                    "hành động này."
                ),
            )

        return current_user

    return role_checker


get_current_student = require_roles(
    UserRole.STUDENT,
)

get_current_teacher = require_roles(
    UserRole.TEACHER,
)

get_current_admin = require_roles(
    UserRole.ADMIN,
)

get_current_teacher_or_admin = require_roles(
    UserRole.TEACHER,
    UserRole.ADMIN,
)
