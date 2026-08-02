from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_student
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.course_learning_path import (
    CourseLearningPathCreate,
    CourseLearningPathResponse,
)
from app.services.course_learning_path_service import (
    CourseLearningPathNotFoundError,
    CourseLearningPathUnavailableError,
    create_course_learning_path,
    get_latest_course_learning_path,
)

router = APIRouter(prefix="/catalog/courses", tags=["Course Learning Paths"])
CurrentStudent = Annotated[User, Depends(get_current_student)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/{course_id}/learning-paths",
    response_model=CourseLearningPathResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_learning_path(
    course_id: UUID,
    payload: CourseLearningPathCreate,
    current_student: CurrentStudent,
    session: DatabaseSession,
) -> CourseLearningPathResponse:
    try:
        data = await create_course_learning_path(
            session, current_student, course_id, payload.required_mastery
        )
    except CourseLearningPathUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return CourseLearningPathResponse.model_validate(data)


@router.get(
    "/{course_id}/learning-paths/latest", response_model=CourseLearningPathResponse
)
async def get_latest_learning_path(
    course_id: UUID,
    current_student: CurrentStudent,
    session: DatabaseSession,
) -> CourseLearningPathResponse:
    try:
        data = await get_latest_course_learning_path(
            session, current_student, course_id
        )
    except CourseLearningPathNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return CourseLearningPathResponse.model_validate(data)
