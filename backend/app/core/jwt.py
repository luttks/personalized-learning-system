from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError

from app.core.config import settings


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenDecodeError(Exception):
    pass


class InvalidTokenTypeError(Exception):
    pass


def create_access_token(
    user_id: UUID,
    role: str,
) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": TokenType.ACCESS.value,
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    user_id: UUID,
    token_id: UUID | None = None,
) -> tuple[str, UUID, datetime]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(
        days=settings.refresh_token_expire_days
    )

    refresh_token_id = token_id or uuid4()

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": str(refresh_token_id),
        "type": TokenType.REFRESH.value,
        "iat": now,
        "exp": expires_at,
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return token, refresh_token_id, expires_at


def decode_token(
    token: str,
    expected_type: TokenType,
) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as error:
        raise TokenDecodeError(
            "Token không hợp lệ hoặc đã hết hạn."
        ) from error

    token_type = payload.get("type")

    if token_type != expected_type.value:
        raise InvalidTokenTypeError(
            "Token không đúng loại."
        )

    if not payload.get("sub"):
        raise TokenDecodeError(
            "Token thiếu subject."
        )

    return payload