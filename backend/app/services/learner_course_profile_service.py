from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Course, CourseStatus
from app.models.course_publication import CoursePublication
from app.models.learner_course_profile import LearnerCourseProfile
from app.models.user import User


class LearnerCourseProfileNotFoundError(Exception):
    pass


class LearnerCourseProfileUnavailableError(Exception):
    pass


async def _active_publication(
    session: AsyncSession,
    course_id: UUID,
) -> tuple[Course, CoursePublication]:
    row = (
        await session.execute(
            select(Course, CoursePublication)
            .join(CoursePublication, CoursePublication.id == Course.active_publication_id)
            .where(
                Course.id == course_id,
                Course.status == CourseStatus.PUBLISHED.value,
                CoursePublication.status == "published",
            )
        )
    ).one_or_none()
    if row is None:
        raise LearnerCourseProfileUnavailableError
    return row


def learner_course_profile_data(
    profile: LearnerCourseProfile,
    active_publication_id: UUID,
) -> dict:
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "course_id": profile.course_id,
        "publication_id": profile.publication_id,
        "version_ids": [UUID(value) for value in profile.version_ids_json],
        "learning_goal": profile.learning_goal,
        "start_date": profile.start_date,
        "deadline": profile.deadline,
        "minutes_per_day": profile.minutes_per_day,
        "days_per_week": profile.days_per_week,
        "available_periods": profile.available_periods,
        "content_formats": profile.content_formats,
        "profile_version": profile.profile_version,
        "stale": profile.publication_id != active_publication_id,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


async def get_learner_course_profile(
    session: AsyncSession,
    user: User,
    course_id: UUID,
) -> dict:
    _course, publication = await _active_publication(session, course_id)
    profile = await session.scalar(
        select(LearnerCourseProfile).where(
            LearnerCourseProfile.user_id == user.id,
            LearnerCourseProfile.course_id == course_id,
        )
    )
    if profile is None:
        raise LearnerCourseProfileNotFoundError
    return learner_course_profile_data(profile, publication.id)


async def upsert_learner_course_profile(
    session: AsyncSession,
    user: User,
    course_id: UUID,
    payload: dict,
) -> dict:
    _course, publication = await _active_publication(session, course_id)
    profile = await session.scalar(
        select(LearnerCourseProfile)
        .where(
            LearnerCourseProfile.user_id == user.id,
            LearnerCourseProfile.course_id == course_id,
        )
        .with_for_update()
    )
    values = {
        **payload,
        "publication_id": publication.id,
        "version_ids_json": publication.version_ids_json,
    }
    if profile is None:
        profile = LearnerCourseProfile(
            user_id=user.id,
            course_id=course_id,
            profile_version=1,
            **values,
        )
        session.add(profile)
    else:
        changed = any(
            getattr(profile, key) != value
            for key, value in values.items()
        )
        for key, value in values.items():
            setattr(profile, key, value)
        if changed:
            profile.profile_version += 1
    await session.commit()
    await session.refresh(profile)
    return learner_course_profile_data(profile, publication.id)
