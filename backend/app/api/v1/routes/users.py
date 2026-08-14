from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_admin
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import (
    EmailAlreadyExistsError,
    UserNotFoundError,
    create_user,
    list_users,
    update_user,
    delete_user,
)
from uuid import UUID

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_by_admin(
    payload: UserCreate,
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(
        get_db_session
    ),
) -> UserResponse:
    try:
        user = await create_user(
            session=session,
            payload=payload,
        )
    except EmailAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được sử dụng.",
        ) from error

    return UserResponse.model_validate(user)


@router.get(
    "",
    response_model=list[UserResponse],
)
async def get_users(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(
        get_db_session
    ),
) -> list[UserResponse]:
    users = await list_users(
        session=session,
        limit=limit,
        offset=offset,
    )

    return [
        UserResponse.model_validate(user)
        for user in users
    ]


@router.put(
    "/{user_id}",
    response_model=UserResponse,
)
async def update_user_by_admin(
    user_id: UUID,
    payload: UserUpdate,
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    try:
        user = await update_user(
            session=session,
            user_id=user_id,
            payload=payload,
        )
        return UserResponse.model_validate(user)
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Người dùng không tồn tại.",
        ) from error


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user_by_admin(
    user_id: UUID,
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        await delete_user(
            session=session,
            user_id=user_id,
        )
    except UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Người dùng không tồn tại.",
        ) from error