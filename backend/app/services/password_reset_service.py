from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.password_reset import PasswordResetCode
from app.models.user import User
from app.services.auth_service import revoke_all_user_tokens

CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def issue_reset_code(session: AsyncSession, email: str) -> tuple[User | None, str | None]:
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if not user or not user.is_active:
        return None, None
    await session.execute(delete(PasswordResetCode).where(PasswordResetCode.user_id == user.id))
    code = f"{secrets.randbelow(1_000_000):06d}"
    session.add(PasswordResetCode(user_id=user.id, code_hash=_hash(code), expires_at=datetime.now(UTC) + CODE_TTL))
    await session.commit()
    return user, code


async def reset_password(session: AsyncSession, email: str, code: str, new_password: str) -> bool:
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if not user:
        return False
    record = await session.scalar(select(PasswordResetCode).where(PasswordResetCode.user_id == user.id).with_for_update())
    now = datetime.now(UTC)
    if not record or record.used_at or record.expires_at <= now or record.attempts >= MAX_ATTEMPTS:
        return False
    if not secrets.compare_digest(record.code_hash, _hash(code)):
        record.attempts += 1
        await session.commit()
        return False
    user.password_hash = hash_password(new_password)
    record.used_at = now
    await revoke_all_user_tokens(session=session, user_id=user.id)
    await session.commit()
    return True
