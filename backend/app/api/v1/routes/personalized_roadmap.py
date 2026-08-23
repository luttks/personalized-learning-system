from typing import Any
from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_student
from app.db.session import get_db_session
from app.models.personalized_roadmap import PersonalizedRoadmap
from app.models.user import User
from app.models.content import Course, CourseVersion, CourseVersionStatus
from app.models.document_analysis import DocumentAnalysis
from app.services.document_chat_service import chat_about_document
from app.schemas.content import DocumentChatRequest, DocumentChatSessionResponse, DocumentChatMessageResponse
from app.services.learner_service import get_learner_profile
from app.core.config import settings
from app.services.exam_service import _call_llm_with_fallback

router = APIRouter()


class PersonalizedRoadmapResponse(BaseModel):
    id: UUID
    title: str
    overview: str
    total_weeks: int
    roadmap_data: dict[str, Any]
    created_at: str
    source_version_id: UUID | None = None

    @classmethod
    def from_orm(cls, roadmap: PersonalizedRoadmap, source_version_id: UUID | None = None) -> "PersonalizedRoadmapResponse":
        return cls(
            id=roadmap.id,
            title=roadmap.title,
            overview=roadmap.overview,
            total_weeks=roadmap.total_weeks,
            roadmap_data=roadmap.roadmap_data,
            created_at=roadmap.created_at.isoformat(),
            source_version_id=source_version_id,
        )


class SubjectDocumentChatRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=2, max_length=3000)
    session_id: UUID | None = None


async def _source_version_id(session: AsyncSession, roadmap: PersonalizedRoadmap, user: User) -> UUID | None:
    subject = roadmap.title.strip().lower()
    result = await session.scalar(
        select(CourseVersion.id)
        .join(Course, Course.id == CourseVersion.course_id)
        .join(DocumentAnalysis, DocumentAnalysis.course_version_id == CourseVersion.id)
        .where(
            CourseVersion.status.in_([CourseVersionStatus.READY_FOR_REVIEW.value, CourseVersionStatus.PUBLISHED.value]),
            func.lower(Course.subject) == subject,
            DocumentAnalysis.status == "completed",
        )
        .order_by(CourseVersion.created_at.desc())
    )
    return result


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
    
    return [PersonalizedRoadmapResponse.from_orm(r, await _source_version_id(session, r, current_user)) for r in roadmaps]


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
        
    return PersonalizedRoadmapResponse.from_orm(roadmap, await _source_version_id(session, roadmap, current_user))


@router.post("/{roadmap_id}/chat", response_model=DocumentChatSessionResponse)
async def chat_with_roadmap_document(
    roadmap_id: UUID,
    payload: DocumentChatRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_student),
) -> DocumentChatSessionResponse:
    learner = await get_learner_profile(session, current_user.id)
    roadmap = await session.scalar(select(PersonalizedRoadmap).where(PersonalizedRoadmap.id == roadmap_id, PersonalizedRoadmap.learner_id == learner.id if learner else False))
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    source_version_id = await _source_version_id(session, roadmap, current_user)
    if not source_version_id:
        from app.models.exam_analysis_model import ExamAnalysis
        analysis = await session.scalar(
            select(ExamAnalysis).where(
                ExamAnalysis.id == roadmap.exam_analysis_id,
                ExamAnalysis.raw_markdown.is_not(None),
            )
        )
        if analysis is None or not analysis.raw_markdown:
            raise HTTPException(status_code=409, detail="Chưa tìm thấy tài liệu nguồn đã lập chỉ mục cho lộ trình này.")
        prompt = f"""Bạn là trợ lý học tập. Trả lời bằng tiếng Việt, chỉ dựa trên tài liệu gốc bên dưới. Nếu không có thông tin, nói rõ chưa tìm thấy trong tài liệu.\n\nTÀI LIỆU GỐC:\n{analysis.raw_markdown[:120000]}\n\nCÂU HỎI:\n{payload.question.strip()}"""
        try:
            answer = await _call_llm_with_fallback(prompt, settings.gemini_api_keys, settings.llm_api_keys, settings.llm_base_url, settings.llm_model or "", timeout=60, expect_json=False)
        except Exception as error:
            raise HTTPException(status_code=503, detail="Dịch vụ AI hiện không khả dụng.") from error
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        chat_id = payload.session_id or uuid4()
        return DocumentChatSessionResponse(
            id=chat_id,
            course_version_id=uuid4(),
            title=f"Hỏi đáp {roadmap.title}",
            messages=[
                DocumentChatMessageResponse(id=uuid4(), role="user", content=payload.question.strip(), citations=[], sequence=1, created_at=now),
                DocumentChatMessageResponse(id=uuid4(), role="assistant", content=answer.strip(), citations=[{"source_label": analysis.filename}], sequence=2, created_at=now),
            ],
        )
    try:
        chat, messages = await chat_about_document(session, current_user, source_version_id, payload.question.strip(), payload.session_id)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Không thể trả lời từ tài liệu nguồn.") from error
    return DocumentChatSessionResponse(
        id=chat.id,
        course_version_id=chat.course_version_id,
        title=chat.title,
        messages=[DocumentChatMessageResponse(id=item.id, role=item.role, content=item.content, citations=item.citations or [], sequence=item.sequence, created_at=item.created_at) for item in messages],
    )


@router.post("/chat-by-subject", response_model=DocumentChatSessionResponse)
async def chat_by_subject(
    payload: SubjectDocumentChatRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_student),
) -> DocumentChatSessionResponse:
    version_id = await session.scalar(
        select(CourseVersion.id)
        .join(Course, Course.id == CourseVersion.course_id)
        .join(DocumentAnalysis, DocumentAnalysis.course_version_id == CourseVersion.id)
        .where(
            func.lower(Course.subject) == payload.subject.strip().lower(),
            DocumentAnalysis.status == "completed",
        )
        .order_by(CourseVersion.created_at.desc())
    )
    if not version_id:
        # Onboarding uploads are stored as ExamAnalysis (not CourseVersion). Use that
        # extracted source directly so students do not need to upload the document again.
        from app.models.exam_analysis_model import ExamAnalysis
        analysis = await session.scalar(
            select(ExamAnalysis)
            .where(
                ExamAnalysis.learner_id == (await get_learner_profile(session, current_user.id)).id,
                func.lower(ExamAnalysis.subject) == payload.subject.strip().lower(),
                ExamAnalysis.raw_markdown.is_not(None),
            )
            .order_by(ExamAnalysis.created_at.desc())
        )
        if analysis is None or not analysis.raw_markdown:
            raise HTTPException(status_code=409, detail="Chưa có tài liệu nguồn cho môn học này.")
        prompt = f"""Bạn là trợ lý học tập. Hãy trả lời bằng tiếng Việt, chỉ dựa trên tài liệu gốc dưới đây. Nếu không có thông tin, nói rõ không tìm thấy trong tài liệu.\n\nTÀI LIỆU:\n{analysis.raw_markdown[:120000]}\n\nCÂU HỎI:\n{payload.question.strip()}"""
        try:
            answer = await _call_llm_with_fallback(prompt, settings.gemini_api_keys, settings.llm_api_keys, settings.llm_base_url, settings.llm_model or "", timeout=60, expect_json=False)
        except Exception as error:
            raise HTTPException(status_code=503, detail="Dịch vụ AI hiện không khả dụng.") from error
        chat_id = payload.session_id or uuid4()
        from datetime import datetime, UTC
        now = datetime.now(UTC)
        return DocumentChatSessionResponse(
            id=chat_id,
            course_version_id=uuid4(),
            title=f"Hỏi đáp {payload.subject}",
            messages=[
                DocumentChatMessageResponse(id=uuid4(), role="user", content=payload.question.strip(), citations=[], sequence=1, created_at=now),
                DocumentChatMessageResponse(id=uuid4(), role="assistant", content=answer.strip(), citations=[{"source_label": analysis.filename}], sequence=2, created_at=now),
            ],
        )
    try:
        chat, messages = await chat_about_document(session, current_user, version_id, payload.question.strip(), payload.session_id)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Không thể trả lời từ tài liệu nguồn.") from error
    return DocumentChatSessionResponse(
        id=chat.id,
        course_version_id=chat.course_version_id,
        title=chat.title,
        messages=[DocumentChatMessageResponse(id=item.id, role=item.role, content=item.content, citations=item.citations or [], sequence=item.sequence, created_at=item.created_at) for item in messages],
    )


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
