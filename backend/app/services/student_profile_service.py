from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student_profile import StudentProfile
from app.schemas.student_profile import (
    StudentProfileCreate,
    StudentProfileUpdate,
)


class StudentProfileAlreadyExistsError(Exception):
    pass


class StudentProfileNotFoundError(Exception):
    pass


async def get_student_profile(
    session: AsyncSession,
    user_id: UUID,
) -> StudentProfile | None:
    statement = select(StudentProfile).where(
        StudentProfile.user_id == user_id
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def create_student_profile(
    session: AsyncSession,
    user_id: UUID,
    payload: StudentProfileCreate,
) -> StudentProfile:
    existing_profile = await get_student_profile(
        session=session,
        user_id=user_id,
    )

    if existing_profile is not None:
        raise StudentProfileAlreadyExistsError

    profile = StudentProfile(
        user_id=user_id,
        **payload.model_dump(),
    )

    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    return profile


async def update_student_profile(
    session: AsyncSession,
    user_id: UUID,
    payload: StudentProfileUpdate,
) -> StudentProfile:
    profile = await get_student_profile(
        session=session,
        user_id=user_id,
    )

    if profile is None:
        raise StudentProfileNotFoundError

    update_data = payload.model_dump(
        exclude_unset=True,
    )

    for field_name, value in update_data.items():
        setattr(
            profile,
            field_name,
            value,
        )

    await session.commit()
    await session.refresh(profile)

    return profile