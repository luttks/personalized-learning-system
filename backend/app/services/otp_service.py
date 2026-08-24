"""Sinh và xác thực mã OTP 6 chữ số dùng Redis (đã có sẵn cho Celery) làm nơi lưu tạm — phù hợp
vì OTP vốn có thời hạn ngắn, không cần một bảng DB riêng cho dữ liệu tồn tại vài phút."""
from __future__ import annotations

import secrets

from app.core.config import settings
from app.core.redis_client import get_redis_client


def _code_key(email: str) -> str:
    return f"otp:code:{email.strip().lower()}"


def _attempts_key(email: str) -> str:
    return f"otp:attempts:{email.strip().lower()}"


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def store_otp(email: str, code: str) -> None:
    redis_client = get_redis_client()
    ttl = settings.otp_expire_minutes * 60
    await redis_client.set(_code_key(email), code, ex=ttl)
    await redis_client.delete(_attempts_key(email))


class OtpExpiredOrMissingError(Exception):
    pass


class OtpTooManyAttemptsError(Exception):
    pass


class OtpIncorrectError(Exception):
    pass


async def verify_otp(email: str, code: str) -> None:
    """Raise nếu mã sai/hết hạn/hết lượt thử; không raise nghĩa là hợp lệ (đã xóa mã khỏi Redis)."""
    redis_client = get_redis_client()
    code_key = _code_key(email)
    attempts_key = _attempts_key(email)

    stored_code = await redis_client.get(code_key)
    if stored_code is None:
        raise OtpExpiredOrMissingError

    attempts = await redis_client.incr(attempts_key)
    if attempts == 1:
        ttl = await redis_client.ttl(code_key)
        await redis_client.expire(attempts_key, max(ttl, 1))

    if attempts > settings.otp_max_attempts:
        await redis_client.delete(code_key, attempts_key)
        raise OtpTooManyAttemptsError

    if not secrets.compare_digest(stored_code, code.strip()):
        raise OtpIncorrectError

    await redis_client.delete(code_key, attempts_key)
