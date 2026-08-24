from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

EMBEDDING_DIMENSIONS = 768


class ExamAnalysisChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Đoạn trích raw_markdown của ExamAnalysis đã đánh chỉ mục embedding — phục vụ RAG chấm ngữ
    cảnh tài liệu gốc vào prompt sinh câu hỏi kiểm tra (generate_phase_assessment_quiz/
    generate_final_exam_quiz trong exam_service.py), KHÔNG phải chatbot hỏi-đáp tài liệu. Sinh
    ngầm qua index_exam_analysis_chunks_task (app/worker/tasks.py) ngay sau khi ExamAnalysis được
    commit. KHÁC document_page_chunks (RAG cũ cho tính năng nhảy trang, đã xóa vì 1 Gemini API key
    bị giới hạn hạn mức quá thấp — xem alembic e6b7583a9dcb) — bảng này dùng cơ chế xoay vòng 3 key
    đã có sẵn trong LLMClient nên rủi ro hạn mức thấp hơn hẳn. Không có cột trạng thái kiểu
    'page_index_status' — việc "chưa đánh chỉ mục xong" được xử lý tự nhiên bằng cách truy hồi trả
    về rỗng khi chưa có dòng nào, sinh đề vẫn chạy bình thường không có ngữ cảnh gốc."""

    __tablename__ = "exam_analysis_chunks"
    __table_args__ = (
        UniqueConstraint(
            "exam_analysis_id", "chunk_index", name="uq_exam_analysis_chunks_analysis_chunk_index"
        ),
    )

    exam_analysis_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("exam_analyses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
