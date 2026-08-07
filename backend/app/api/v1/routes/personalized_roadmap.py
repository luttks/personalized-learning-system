from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_student
from app.db.session import get_db_session
from app.models.personalized_roadmap import PersonalizedRoadmap
from app.models.user import User
from app.services.learner_service import get_learner_profile

router = APIRouter()


class PersonalizedRoadmapResponse(BaseModel):
    id: UUID
    title: str
    overview: str
    total_weeks: int
    roadmap_data: dict[str, Any]
    created_at: str

    @classmethod
    def from_orm(cls, roadmap: PersonalizedRoadmap) -> "PersonalizedRoadmapResponse":
        return cls(
            id=roadmap.id,
            title=roadmap.title,
            overview=roadmap.overview,
            total_weeks=roadmap.total_weeks,
            roadmap_data=roadmap.roadmap_data,
            created_at=roadmap.created_at.isoformat(),
        )


@router.get("", response_model=list[PersonalizedRoadmapResponse])
async def get_my_roadmaps(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_student),
) -> Any:
    """Lấy danh sách các lộ trình AI đã lưu của học sinh."""
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        return []

    stmt = select(PersonalizedRoadmap).where(
        PersonalizedRoadmap.learner_id == learner.id
    ).order_by(PersonalizedRoadmap.created_at.desc())
    
    result = await session.execute(stmt)
    roadmaps = result.scalars().all()
    
    return [PersonalizedRoadmapResponse.from_orm(r) for r in roadmaps]


@router.get("/{roadmap_id}", response_model=PersonalizedRoadmapResponse)
async def get_roadmap(
    roadmap_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_student),
) -> Any:
    """Xem chi tiết một lộ trình AI."""
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner profile not found")

    stmt = select(PersonalizedRoadmap).where(
        PersonalizedRoadmap.id == roadmap_id,
        PersonalizedRoadmap.learner_id == learner.id
    )
    result = await session.execute(stmt)
    roadmap = result.scalar_one_or_none()
    
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
        
    return PersonalizedRoadmapResponse.from_orm(roadmap)


@router.delete("/{roadmap_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_roadmap(
    roadmap_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_student),
) -> None:
    """Xóa một lộ trình AI."""
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner profile not found")

    stmt = select(PersonalizedRoadmap).where(
        PersonalizedRoadmap.id == roadmap_id,
        PersonalizedRoadmap.learner_id == learner.id
    )
    result = await session.execute(stmt)
    roadmap = result.scalar_one_or_none()
    
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
        
    await session.delete(roadmap)
    await session.commit()
