from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class ExamAnalysis(Base, UUIDPrimaryKeyMixin):
    """Lưu kết quả phân tích đề thi của học sinh."""
    __tablename__ = "exam_analyses"

    learner_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("learner_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Tên môn học / bài thi (AI detect)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)  # Đường dẫn file đã lưu
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # SHA-256 của file để detect trùng lặp
    ocr_engine: Mapped[str] = mapped_column(String(50), default="gemini-3.1-flash-lite", nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    formula_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Câu hỏi đã parse
    questions_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    raw_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Kết quả AI phân tích mức độ khó + lời khuyên
    ai_recommendation_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Tài liệu crawl được (YouTube, Quiz, Academic, GitHub)
    resources_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Danh sách topic_id đã cập nhật mastery
    mastery_updates_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
