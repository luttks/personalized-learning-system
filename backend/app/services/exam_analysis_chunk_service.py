"""Truy hồi RAG cho việc sinh câu hỏi kiểm tra — lớp chạm DB/LLM song song vai trò với
`phase_assessment_service.py`, còn `exam_service.py` (nơi build prompt) giữ nguyên bất biến thuần
không đụng DB. Việc ĐÁNH CHỈ MỤC (chunk + embed + lưu ExamAnalysisChunk) nằm ở
`app.worker.tasks.index_exam_analysis_chunks_task`, chạy ngầm ngay sau khi ExamAnalysis được
commit — module này chỉ TRUY HỒI những gì đã đánh chỉ mục sẵn."""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm_client import get_llm_client
from app.models.exam_analysis_chunk import ExamAnalysisChunk

logger = logging.getLogger(__name__)


async def retrieve_relevant_chunks_for_topics(
    session: AsyncSession,
    exam_analysis_id: UUID | None,
    topic_queries: dict[str, str],
    top_k: int = 3,
) -> dict[str, list[str]]:
    """Truy hồi top_k đoạn trích gần nhất (cosine distance) cho MỖI chủ đề trong `topic_queries`
    ({title: query_text}) — embed TẤT CẢ câu truy vấn trong 1 lệnh gọi Gemini (embed_texts tự batch
    nội bộ) thay vì N lệnh riêng lẻ cho N chủ đề, quan trọng vì đề thi chốt hạ có thể có hàng chục
    chủ đề. AN TOÀN TUYỆT ĐỐI — KHÔNG BAO GIỜ raise: trả {} nếu exam_analysis_id là None, câu
    truy vấn rỗng, tài liệu chưa đánh chỉ mục xong, hay bất kỳ lỗi nào (API embedding lỗi, DB lỗi).
    Sinh câu hỏi PHẢI luôn chạy được bình thường (không có ngữ cảnh gốc) khi hàm này trả về rỗng —
    đây là hành vi trước khi RAG tồn tại, không phải lỗi."""
    if not exam_analysis_id or not topic_queries:
        return {}
    try:
        titles = list(topic_queries.keys())
        vectors = await get_llm_client().embed_texts(
            [topic_queries[t] for t in titles], task_type="RETRIEVAL_QUERY"
        )
        result: dict[str, list[str]] = {}
        for title, vec in zip(titles, vectors):
            rows = (
                await session.execute(
                    select(ExamAnalysisChunk.text)
                    .where(ExamAnalysisChunk.exam_analysis_id == exam_analysis_id)
                    .order_by(ExamAnalysisChunk.embedding.cosine_distance(vec))
                    .limit(top_k)
                )
            ).all()
            if rows:
                result[title] = [r[0] for r in rows]
        return result
    except Exception as e:
        logger.warning(f"retrieve_relevant_chunks_for_topics lỗi (degrade về không có ngữ cảnh gốc): {e}")
        return {}
