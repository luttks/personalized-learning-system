from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate


class EmailAlreadyExistsError(Exception):
    pass


async def get_user_by_email(
    session: AsyncSession,
    email: str,
) -> User | None:
    statement = select(User).where(
        User.email == email.lower().strip()
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    payload: UserCreate,
) -> User:
    normalised_email = payload.email.lower().strip()

    existing_user = await get_user_by_email(
        session=session,
        email=normalised_email,
    )

    if existing_user:
        raise EmailAlreadyExistsError

    user = User(
        full_name=payload.full_name.strip(),
        email=normalised_email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def list_users(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
) -> list[User]:
    statement = (
        select(User)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(statement)
    return list(result.scalars().all())