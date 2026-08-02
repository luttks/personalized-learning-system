from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_current_student,
)
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.student_profile import (
    StudentProfileCreate,
    StudentProfileResponse,
    StudentProfileUpdate,
)
from app.services.student_profile_service import (
    StudentProfileAlreadyExistsError,
    StudentProfileNotFoundError,
    create_student_profile,
    get_student_profile,
    update_student_profile,
)

router = APIRouter(
    prefix="/student-profile",
    tags=["Student Profile"],
)


@router.post(
    "",
    response_model=StudentProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_profile(
    payload: StudentProfileCreate,
    current_user: User = Depends(
        get_current_student
    ),
    session: AsyncSession = Depends(
        get_db_session
    ),
) -> StudentProfileResponse:
    try:
        profile = await create_student_profile(
            session=session,
            user_id=current_user.id,
            payload=payload,
        )
    except StudentProfileAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Hồ sơ học sinh đã tồn tại. "
                "Hãy sử dụng PATCH để cập nhật."
            ),
        ) from error

    return StudentProfileResponse.model_validate(
        profile
    )


@router.get(
    "/me",
    response_model=StudentProfileResponse,
)
async def get_my_profile(
    current_user: User = Depends(
        get_current_student
    ),
    session: AsyncSession = Depends(
        get_db_session
    ),
) -> StudentProfileResponse:
    profile = await get_student_profile(
        session=session,
        user_id=current_user.id,
    )

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chưa có hồ sơ học sinh.",
        )

    return StudentProfileResponse.model_validate(
        profile
    )


@router.patch(
    "/me",
    response_model=StudentProfileResponse,
)
async def update_my_profile(
    payload: StudentProfileUpdate,
    current_user: User = Depends(
        get_current_student
    ),
    session: AsyncSession = Depends(
        get_db_session
    ),
) -> StudentProfileResponse:
    try:
        profile = await update_student_profile(
            session=session,
            user_id=current_user.id,
            payload=payload,
        )
    except StudentProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chưa có hồ sơ học sinh.",
        ) from error

    return StudentProfileResponse.model_validate(
        profile
    )