from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_student
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.content import (
    LearnerCourseProfileResponse,
    LearnerCourseProfileUpsert,
    PublishedCourseDetail,
    PublishedCourseSummary,
)
from app.services.learner_course_profile_service import (
    LearnerCourseProfileNotFoundError,
    LearnerCourseProfileUnavailableError,
    get_learner_course_profile,
    upsert_learner_course_profile,
)
from app.services.published_catalog_service import (
    PublishedCourseNotFoundError,
    get_published_course,
    list_published_courses,
)

router = APIRouter(prefix="/catalog/courses", tags=["Student Catalog"])

CurrentStudent = Annotated[User, Depends(get_current_student)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("", response_model=list[PublishedCourseSummary])
async def list_catalog_courses(
    _current_student: CurrentStudent,
    session: DatabaseSession,
) -> list[PublishedCourseSummary]:
    rows = await list_published_courses(session)
    return [PublishedCourseSummary.model_validate(row) for row in rows]


@router.get("/{course_id}", response_model=PublishedCourseDetail)
async def get_catalog_course(
    course_id: UUID,
    _current_student: CurrentStudent,
    session: DatabaseSession,
) -> PublishedCourseDetail:
    try:
        row = await get_published_course(session, course_id)
    except PublishedCourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return PublishedCourseDetail.model_validate(row)


@router.get(
    "/{course_id}/learner-profile",
    response_model=LearnerCourseProfileResponse,
)
async def get_course_onboarding_profile(
    course_id: UUID,
    current_student: CurrentStudent,
    session: DatabaseSession,
) -> LearnerCourseProfileResponse:
    try:
        row = await get_learner_course_profile(session, current_student, course_id)
    except LearnerCourseProfileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except LearnerCourseProfileUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT) from error
    return LearnerCourseProfileResponse.model_validate(row)


@router.put(
    "/{course_id}/learner-profile",
    response_model=LearnerCourseProfileResponse,
)
async def save_course_onboarding_profile(
    course_id: UUID,
    payload: LearnerCourseProfileUpsert,
    current_student: CurrentStudent,
    session: DatabaseSession,
) -> LearnerCourseProfileResponse:
    try:
        row = await upsert_learner_course_profile(
            session,
            current_student,
            course_id,
            payload.model_dump(),
        )
    except LearnerCourseProfileUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Khóa học không còn publication đang hoạt động.",
        ) from error
    return LearnerCourseProfileResponse.model_validate(row)
