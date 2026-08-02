from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "personalized-learning-api",
    }


@router.get("/database")
async def database_health_check(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    result = await session.execute(
        text("SELECT 1 AS healthy")
    )

    return {
        "status": "ok",
        "database": result.scalar_one(),
    }
