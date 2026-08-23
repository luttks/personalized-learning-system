from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.models.content import Course, CourseVersion, Document
from app.models.exam_analysis_model import ExamAnalysis
from app.models.learner import LearnerProfile
from app.models.personalized_roadmap import PersonalizedRoadmap
from app.models.user import User, UserRole

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class DashboardStatsResponse(BaseModel):
    course_document_count: int
    exam_upload_count: int
    roadmap_count: int
    study_minutes_per_day: int | None
    study_days_per_week: int | None


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardStatsResponse:
    # Course ownership is the source of truth for user-uploaded course documents.
    document_query = select(func.count(Document.id)).join(
        CourseVersion, CourseVersion.id == Document.course_version_id,
    ).join(Course, Course.id == CourseVersion.course_id)
    if current_user.role != UserRole.ADMIN:
        document_query = document_query.where(Course.owner_id == current_user.id)
    course_document_count = int(await session.scalar(document_query) or 0)

    exam_query = select(func.count(ExamAnalysis.id))
    roadmap_query = select(func.count(PersonalizedRoadmap.id))
    if current_user.role != UserRole.ADMIN:
        learner_id = await session.scalar(select(LearnerProfile.id).where(LearnerProfile.user_id == current_user.id))
        exam_query = exam_query.where(ExamAnalysis.learner_id == learner_id)
        roadmap_query = roadmap_query.where(PersonalizedRoadmap.learner_id == learner_id)
    exam_upload_count = int(await session.scalar(exam_query) or 0)
    roadmap_count = int(await session.scalar(roadmap_query) or 0)

    profile = await session.scalar(select(LearnerProfile).where(LearnerProfile.user_id == current_user.id))
    return DashboardStatsResponse(
        course_document_count=course_document_count,
        exam_upload_count=exam_upload_count,
        roadmap_count=roadmap_count,
        study_minutes_per_day=profile.minutes_per_day if profile else None,
        study_days_per_week=profile.days_per_week if profile else None,
    )
