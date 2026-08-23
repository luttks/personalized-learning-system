from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document_chat import DocumentChatMessage, DocumentChatSession
from app.models.user import User
from app.services.content_service import CourseNotFoundError, get_analysis_for_manager
from app.services.exam_service import _call_llm_with_fallback
from app.services.rag_service import search_content_chunks


async def chat_about_document(
    session: AsyncSession,
    user: User,
    course_version_id: UUID,
    question: str,
    session_id: UUID | None,
) -> tuple[DocumentChatSession, list[DocumentChatMessage]]:
    analysis = await get_analysis_for_manager(session, user, course_version_id)
    if analysis is None or analysis.status != "completed":
        raise CourseNotFoundError
    if session_id:
        chat = await session.scalar(
            select(DocumentChatSession).where(
                DocumentChatSession.id == session_id,
                DocumentChatSession.user_id == user.id,
                DocumentChatSession.course_version_id == course_version_id,
            )
        )
        if chat is None:
            raise CourseNotFoundError
    else:
        chat = DocumentChatSession(
            course_version_id=course_version_id,
            user_id=user.id,
            title=question[:255],
        )
        session.add(chat)
        await session.flush()

    previous = list(
        (
            await session.scalars(
                select(DocumentChatMessage)
                .where(DocumentChatMessage.session_id == chat.id)
                .order_by(DocumentChatMessage.sequence.desc())
                .limit(10)
            )
        ).all()
    )[::-1]
    hits = await search_content_chunks(session, user, course_version_id, question, limit=6)
    context = "\n\n".join(
        f"[{chunk.source_label}]\n{chunk.text}" for chunk, _cosine, _score in hits
    )
    history = "\n".join(f"{item.role}: {item.content}" for item in previous)
    prompt = f"""Bạn là trợ lý học tập. Chỉ trả lời dựa trên NGỮ CẢNH TÀI LIỆU bên dưới. Nếu không đủ thông tin, nói rõ chưa tìm thấy trong tài liệu. Trả lời bằng tiếng Việt, giải thích dễ hiểu theo trình độ người học. Không bịa nguồn.

NGỮ CẢNH TÀI LIỆU:
{context}

LỊCH SỬ HỘI THOẠI:
{history}

CÂU HỎI MỚI:
{question}
"""
    answer = await _call_llm_with_fallback(
        prompt,
        settings.gemini_api_keys,
        settings.llm_api_keys,
        settings.llm_base_url,
        settings.llm_model or "",
        timeout=60,
        expect_json=False,
    )
    next_sequence = max((item.sequence for item in previous), default=0) + 1
    user_message = DocumentChatMessage(
        session_id=chat.id,
        role="user",
        content=question,
        citations=[],
        sequence=next_sequence,
    )
    assistant_message = DocumentChatMessage(
        session_id=chat.id,
        role="assistant",
        content=answer.strip(),
        citations=[
            {"chunk_id": str(chunk.id), "source_label": chunk.source_label, "page_number": chunk.page_number}
            for chunk, _cosine, _score in hits
        ],
        sequence=next_sequence + 1,
    )
    chat.last_message_at = datetime.now(UTC)
    session.add_all([user_message, assistant_message])
    await session.commit()
    await session.refresh(chat)
    return chat, [user_message, assistant_message]


async def get_document_chat(
    session: AsyncSession, user: User, course_version_id: UUID, chat_id: UUID
) -> tuple[DocumentChatSession, list[DocumentChatMessage]]:
    await get_analysis_for_manager(session, user, course_version_id)
    chat = await session.scalar(
        select(DocumentChatSession).where(
            DocumentChatSession.id == chat_id,
            DocumentChatSession.user_id == user.id,
            DocumentChatSession.course_version_id == course_version_id,
        )
    )
    if chat is None:
        raise CourseNotFoundError
    messages = list(
        (
            await session.scalars(
                select(DocumentChatMessage).where(DocumentChatMessage.session_id == chat.id).order_by(DocumentChatMessage.sequence)
            )
        ).all()
    )
    return chat, messages
