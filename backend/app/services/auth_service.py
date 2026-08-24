from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import (
    TokenDecodeError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.security import verify_password
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserCreate
from app.services import otp_service
from app.services.email_service import send_otp_email
from app.services.otp_service import (
    OtpExpiredOrMissingError,
    OtpIncorrectError,
    OtpTooManyAttemptsError,
)
from app.services.user_service import (
    create_user,
    get_user_by_email,
)


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class EmailNotVerifiedError(Exception):
    pass


class UserNotFoundForOtpError(Exception):
    pass


class EmailAlreadyVerifiedError(Exception):
    pass


class InvalidOtpError(Exception):
    """Bọc chung 3 kiểu lỗi OTP (hết hạn/sai/hết lượt) thành 1 lỗi nghiệp vụ cho route xử lý."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


async def _issue_and_send_otp(user: User) -> None:
    code = otp_service.generate_otp_code()
    await otp_service.store_otp(user.email, code)
    await send_otp_email(user.email, user.full_name, code)


async def register_student(
    session: AsyncSession,
    payload: RegisterRequest,
) -> User:
    user_payload = UserCreate(
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
        role="student",
    )

    user = await create_user(
        session=session,
        payload=user_payload,
    )
    await _issue_and_send_otp(user)
    return user


async def resend_verification_otp(
    session: AsyncSession,
    email: str,
) -> None:
    user = await get_user_by_email(session=session, email=email)
    if user is None:
        raise UserNotFoundForOtpError
    if user.email_verified:
        raise EmailAlreadyVerifiedError
    await _issue_and_send_otp(user)


async def verify_email_otp(
    session: AsyncSession,
    email: str,
    code: str,
) -> User:
    user = await get_user_by_email(session=session, email=email)
    if user is None:
        raise UserNotFoundForOtpError
    if user.email_verified:
        raise EmailAlreadyVerifiedError

    try:
        await otp_service.verify_otp(email, code)
    except OtpExpiredOrMissingError:
        raise InvalidOtpError("expired") from None
    except OtpTooManyAttemptsError:
        raise InvalidOtpError("too_many_attempts") from None
    except OtpIncorrectError:
        raise InvalidOtpError("incorrect") from None

    user.email_verified = True
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> User:
    user = await get_user_by_email(
        session=session,
        email=email,
    )

    if user is None:
        raise InvalidCredentialsError

    if not verify_password(
        password,
        user.password_hash,
    ):
        raise InvalidCredentialsError

    if not user.is_active:
        raise InactiveUserError

    if not user.email_verified:
        raise EmailNotVerifiedError

    return user


async def issue_token_pair(
    session: AsyncSession,
    user: User,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[str, str]:
    access_token = create_access_token(
        user_id=user.id,
        role=user.role.value,
    )

    (
        refresh_token,
        refresh_token_id,
        refresh_expires_at,
    ) = create_refresh_token(
        user_id=user.id,
    )

    token_record = RefreshToken(
        user_id=user.id,
        token_id=refresh_token_id,
        expires_at=refresh_expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    session.add(token_record)
    await session.commit()

    return access_token, refresh_token


async def rotate_refresh_token(
    session: AsyncSession,
    raw_refresh_token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[str, str]:
    try:
        payload = decode_token(
            raw_refresh_token,
            TokenType.REFRESH,
        )
    except Exception as error:
        raise InvalidRefreshTokenError from error

    try:
        user_id = UUID(payload["sub"])
        token_id = UUID(payload["jti"])
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidRefreshTokenError from error

    statement = (
        select(RefreshToken)
        .where(
            RefreshToken.token_id == token_id,
            RefreshToken.user_id == user_id,
        )
        .with_for_update()
    )

    result = await session.execute(statement)
    stored_token = result.scalar_one_or_none()

    now = datetime.now(UTC)

    if stored_token is None:
        raise InvalidRefreshTokenError

    if stored_token.is_revoked:
        raise InvalidRefreshTokenError

    if stored_token.expires_at <= now:
        raise InvalidRefreshTokenError

    user = await session.get(User, user_id)

    if user is None or not user.is_active:
        raise InvalidRefreshTokenError

    stored_token.is_revoked = True
    stored_token.revoked_at = now

    access_token = create_access_token(
        user_id=user.id,
        role=user.role.value,
    )

    (
        new_refresh_token,
        new_token_id,
        new_expires_at,
    ) = create_refresh_token(
        user_id=user.id,
    )

    new_record = RefreshToken(
        user_id=user.id,
        token_id=new_token_id,
        expires_at=new_expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    session.add(new_record)
    await session.commit()

    return access_token, new_refresh_token


async def revoke_refresh_token(
    session: AsyncSession,
    raw_refresh_token: str,
) -> None:
    try:
        payload = decode_token(
            raw_refresh_token,
            TokenType.REFRESH,
        )

        token_id = UUID(payload["jti"])
    except (
        TokenDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise InvalidRefreshTokenError from error

    statement = (
        update(RefreshToken)
        .where(
            RefreshToken.token_id == token_id,
            RefreshToken.is_revoked.is_(False),
        )
        .values(
            is_revoked=True,
            revoked_at=datetime.now(UTC),
        )
    )

    await session.execute(statement)
    await session.commit()


async def revoke_all_user_tokens(
    session: AsyncSession,
    user_id: UUID,
) -> None:
    statement = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked.is_(False),
        )
        .values(
            is_revoked=True,
            revoked_at=datetime.now(UTC),
        )
    )

    await session.execute(statement)
    await session.commit()
