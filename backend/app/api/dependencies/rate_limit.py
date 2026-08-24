"""Giới hạn tần suất gọi API bằng bộ đếm cửa sổ cố định (fixed window) trên Redis — tái sử
dụng Redis đã có sẵn cho Celery, không cần thêm hạ tầng mới. Nếu Redis tạm thời không sẵn sàng,
request vẫn được cho qua (không để lỗi hạ tầng phụ làm sập API chính)."""
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.api.dependencies.auth import get_current_student
from app.core.redis_client import get_redis_client
from app.models.user import User


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _check_and_increment(key: str, max_requests: int, window_seconds: int) -> None:
    redis_client = get_redis_client()
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, window_seconds)
    except Exception:
        return
    if count > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau {window_seconds} giây.",
        )


def rate_limit_by_ip(key_prefix: str, max_requests: int, window_seconds: int):
    """Giới hạn theo địa chỉ IP — dùng cho các endpoint chưa đăng nhập (login, register)."""

    async def _dependency(request: Request) -> None:
        await _check_and_increment(
            f"ratelimit:{key_prefix}:{_client_ip(request)}", max_requests, window_seconds
        )

    return _dependency


def rate_limit_by_user(key_prefix: str, max_requests: int, window_seconds: int):
    """Giới hạn theo tài khoản học sinh — dùng cho các endpoint tốn kém (OCR/LLM)."""

    async def _dependency(
        current_user: Annotated[User, Depends(get_current_student)],
    ) -> None:
        await _check_and_increment(
            f"ratelimit:{key_prefix}:{current_user.id}", max_requests, window_seconds
        )

    return _dependency
