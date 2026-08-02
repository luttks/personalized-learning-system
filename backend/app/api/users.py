from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.user import UserCreate, UserResponse
from app.services.user_service import (
    EmailAlreadyExistsError,
    create_user,
    list_users,
)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
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
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
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
