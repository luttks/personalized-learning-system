from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RoadmapFinalExam(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Bài thi chốt hạ cuối lộ trình — 1 dòng duy nhất mỗi PersonalizedRoadmap (không theo giai
    đoạn). Sinh ngầm LAZY khi người học lần đầu mở màn hình này SAU khi đã đi qua mọi giai đoạn
    (current_phase_number > số giai đoạn) — KHÁC PhaseAssessment (sinh sẵn hàng loạt lúc tạo lộ
    trình), vì roadmap_data có thể bị remediation sửa đổi bất cứ lúc nào trước khi hoàn thành, sinh
    sẵn dễ lệch nội dung thực tế đã học. Đây là BÁO CÁO tổng kết, không phải cửa chặn — không có
    pass_threshold/gate, không có manually_unlocked_at (không có giai đoạn nào phía sau để bảo vệ)."""

    __tablename__ = "roadmap_final_exams"
    __table_args__ = (
        CheckConstraint("attempts_count >= 0", name="ck_roadmap_final_exams_attempts_non_negative"),
        CheckConstraint(
            "score_ratio IS NULL OR (score_ratio >= 0 AND score_ratio <= 1)",
            name="ck_roadmap_final_exams_score_range",
        ),
        UniqueConstraint("roadmap_id", name="uq_roadmap_final_exams_roadmap"),
    )

    roadmap_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("personalized_roadmaps.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # pending (vừa tạo, chưa sinh) | generating (task đang chạy) | ready (đã có câu hỏi, chờ làm)
    # | failed (sinh câu hỏi lỗi kỹ thuật, cần sinh lại) | completed (đã làm — chỉ 1 lần, giống quy
    # ước PhaseAssessment, tránh học thuộc bằng cách làm đi làm lại)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # [{"id", "question", "options", "correct", "explanation", "difficulty", "topic_ref",
    #   "phase_number"}, ...] — correct/explanation KHÔNG trả ra ngoài qua API trước khi nộp bài.
    questions_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    score_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
