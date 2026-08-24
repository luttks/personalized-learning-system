from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.rate_limit import rate_limit_by_ip
from app.core.config import settings
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    ResendOtpRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.user import UserResponse
from app.services.auth_service import (
    EmailAlreadyVerifiedError,
    EmailNotVerifiedError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidOtpError,
    InvalidRefreshTokenError,
    UserNotFoundForOtpError,
    authenticate_user,
    issue_token_pair,
    register_student,
    resend_verification_otp,
    revoke_all_user_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_email_otp,
)
from app.services.user_service import (
    EmailAlreadyExistsError,
)

async def _enrich_user_response(session: AsyncSession, user: User) -> UserResponse:
    resp = UserResponse.model_validate(user)
    if user.role.value == "student":
        from sqlalchemy import select
        from app.models.student_profile import StudentProfile
        result = await session.execute(
            select(StudentProfile.id).where(StudentProfile.user_id == user.id)
        )
        resp.has_completed_profile = result.scalar_one_or_none() is not None
    else:
        resp.has_completed_profile = True
    return resp

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def get_request_ip(
    request: Request,
) -> str | None:
    forwarded_for = request.headers.get(
        "x-forwarded-for"
    )

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client:
        return request.client.host

    return None


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_by_ip("register", max_requests=8, window_seconds=60))],
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    try:
        user = await register_student(
            session=session,
            payload=payload,
        )
    except EmailAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được sử dụng.",
        ) from error

    return await _enrich_user_response(session, user)


@router.post(
    "/verify-email",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit_by_ip("verify_email", max_requests=10, window_seconds=60))],
)
async def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Xác thực mã OTP 6 chữ số đã gửi qua email lúc đăng ký — thành công thì đăng nhập luôn."""
    try:
        user = await verify_email_otp(
            session=session,
            email=payload.email,
            code=payload.code,
        )
    except UserNotFoundForOtpError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản với email này.",
        ) from error
    except EmailAlreadyVerifiedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được xác thực trước đó. Vui lòng đăng nhập.",
        ) from error
    except InvalidOtpError as error:
        messages = {
            "expired": "Mã OTP đã hết hạn hoặc không tồn tại. Vui lòng bấm gửi lại mã.",
            "too_many_attempts": "Bạn đã nhập sai quá nhiều lần. Vui lòng bấm gửi lại mã mới.",
            "incorrect": "Mã OTP không chính xác. Vui lòng kiểm tra lại.",
        }
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=messages.get(error.reason, "Mã OTP không hợp lệ."),
        ) from error

    access_token, refresh_token = await issue_token_pair(
        session=session,
        user=user,
        user_agent=request.headers.get("user-agent"),
        ip_address=get_request_ip(request),
    )
    enriched_user = await _enrich_user_response(session, user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=(settings.access_token_expire_minutes * 60),
        user=enriched_user,
    )


@router.post(
    "/resend-otp",
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit_by_ip("resend_otp", max_requests=3, window_seconds=120))],
)
async def resend_otp(
    payload: ResendOtpRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    try:
        await resend_verification_otp(session=session, email=payload.email)
    except UserNotFoundForOtpError:
        # Không tiết lộ việc email có tồn tại hay không — trả về thông báo chung.
        pass
    except EmailAlreadyVerifiedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được xác thực trước đó. Vui lòng đăng nhập.",
        ) from error

    return MessageResponse(message="Nếu email tồn tại, mã OTP mới đã được gửi.")


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit_by_ip("login", max_requests=10, window_seconds=60))],
)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    try:
        user = await authenticate_user(
            session=session,
            email=payload.email,
            password=payload.password,
        )
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác.",
        ) from error
    except InactiveUserError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị khóa.",
        ) from error
    except EmailNotVerifiedError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "EMAIL_NOT_VERIFIED",
                "message": "Email chưa được xác thực. Vui lòng nhập mã OTP đã gửi tới email của bạn.",
            },
        ) from error

    access_token, refresh_token = await issue_token_pair(
        session=session,
        user=user,
        user_agent=request.headers.get("user-agent"),
        ip_address=get_request_ip(request),
    )

    enriched_user = await _enrich_user_response(session, user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=(
            settings.access_token_expire_minutes * 60
        ),
        user=enriched_user,
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> RefreshResponse:
    try:
        (
            access_token,
            refresh_token,
        ) = await rotate_refresh_token(
            session=session,
            raw_refresh_token=payload.refresh_token,
            user_agent=request.headers.get(
                "user-agent"
            ),
            ip_address=get_request_ip(request),
        )
    except InvalidRefreshTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Refresh token không hợp lệ, "
                "đã hết hạn hoặc đã bị thu hồi."
            ),
        ) from error

    return RefreshResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=(
            settings.access_token_expire_minutes * 60
        ),
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
)
async def logout(
    payload: LogoutRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    try:
        await revoke_refresh_token(
            session=session,
            raw_refresh_token=payload.refresh_token,
        )
    except InvalidRefreshTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ.",
        ) from error

    return MessageResponse(
        message="Đăng xuất thành công.",
    )


@router.post(
    "/logout-all",
    response_model=MessageResponse,
)
async def logout_all(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    await revoke_all_user_tokens(
        session=session,
        user_id=current_user.id,
    )

    return MessageResponse(
        message="Đã đăng xuất khỏi tất cả thiết bị.",
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
async def me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    return await _enrich_user_response(session, current_user)