from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
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


class PhaseAssessment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Bài kiểm tra năng lực cuối một giai đoạn của PersonalizedRoadmap — sinh ngầm bằng Celery
    ngay khi lộ trình được tạo (không chờ người học mở ra mới sinh). Chỉ làm ĐÚNG 1 LẦN — không có
    cơ chế làm lại; đậu hay rớt đều mở khóa giai đoạn tiếp theo, khác biệt duy nhất là rớt thì kích
    hoạt điều chỉnh (remediation) nội dung các giai đoạn còn lại thay vì chặn người học lại. Nội
    dung câu hỏi bám vào đúng phase.days[*].topics[*] đã lưu, không phải kiến thức chung của môn
    học.

    NGOẠI LỆ DUY NHẤT cho "luôn tiến tới": nếu giai đoạn TRƯỚC đó chưa đạt (not_passed) và người học
    bấm "mở khóa sớm" để bỏ qua thời gian học lại rồi CŨNG rớt luôn giai đoạn này — status chuyển
    'locked_for_retry' (chung cuộc kiểu khác: không mở khóa giai đoạn sau, bắt học lại chính giai
    đoạn này) thay vì 'not_passed'. Xem apply_phase_remediation(reinforce_same_phase=True) trong
    exam_service.py và submit_phase_assessment trong routes/personalized_roadmap.py."""

    __tablename__ = "phase_assessments"
    __table_args__ = (
        CheckConstraint("phase_number >= 1", name="ck_phase_assessments_phase_number_positive"),
        CheckConstraint("attempts_count >= 0", name="ck_phase_assessments_attempts_non_negative"),
        CheckConstraint(
            "pass_threshold >= 0 AND pass_threshold <= 1",
            name="ck_phase_assessments_threshold_range",
        ),
        CheckConstraint(
            "score_ratio IS NULL OR (score_ratio >= 0 AND score_ratio <= 1)",
            name="ck_phase_assessments_score_range",
        ),
        UniqueConstraint("roadmap_id", "phase_number", name="uq_phase_assessments_roadmap_phase"),
    )

    roadmap_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("personalized_roadmaps.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    phase_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # pending (vừa tạo, chưa sinh) | generating (task đang chạy) | ready (đã có câu hỏi, chờ làm)
    # | failed (SINH câu hỏi lỗi kỹ thuật, cần sinh lại — KHÔNG liên quan điểm số) | passed (đã làm
    # bài và đậu — chung cuộc) | not_passed (đã làm bài, chưa đạt ngưỡng — CŨNG chung cuộc: chỉ làm
    # 1 lần/giai đoạn, không có lượt làm lại; giai đoạn tiếp theo vẫn mở khóa, remediation điều
    # chỉnh nội dung phía sau thay vì chặn lại) | locked_for_retry (rớt sau khi bỏ qua giai đoạn
    # trước đang hổng kiến thức — KHÓA giai đoạn sau, bắt học lại chính giai đoạn này, xem
    # retry_unlock_at bên dưới; đây là NGOẠI LỆ duy nhất không mở khóa giai đoạn tiếp theo)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # Snapshot ngưỡng đậu từ Settings tại thời điểm tạo — nếu sau này đổi default toàn hệ thống,
    # lộ trình đang chạy vẫn giữ đúng ngưỡng đã "hứa" với người học.
    pass_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    # [{"id", "question", "options": {"A":..,"B":..,"C":..,"D":..}, "correct", "explanation",
    #   "difficulty", "topic_ref"}, ...] — correct/explanation KHÔNG được trả ra ngoài qua API
    # trước khi người học nộp bài.
    questions_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    score_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Người học tự bấm "học xong sớm" để mở khóa trước khi tới ngày cuối lịch học của giai đoạn.
    manually_unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Đã chèn nội dung củng cố + xếp lại lịch các giai đoạn sau do rớt (lần làm duy nhất) ở giai
    # đoạn này hay chưa — NULL nghĩa là chưa (hoặc không áp dụng, VD đây là giai đoạn cuối).
    # Idempotency guard cho apply_phase_remediation_task: attempts_count==1 chỉ chặn được request
    # nộp bài thứ 2 (race condition), không chặn được việc chính task Celery tự retry/redeliver rồi
    # áp dụng lại lần nữa.
    remediation_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Ngày bài kiểm tra được phép mở lại (chỉ có ý nghĩa khi status='locked_for_retry') — bằng ngày
    # cuối cùng của giai đoạn này SAU khi apply_phase_remediation(reinforce_same_phase=True) xếp lại
    # lịch dài hơn. Tự phục hồi (self-heal) qua _reopen_if_due trong routes/personalized_roadmap.py,
    # cùng cơ chế với _enqueue_pending — không cần task nền riêng để "mở khóa đúng giờ".
    retry_unlock_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Dedup RIÊNG cho email nhắc nhở 2 lần/ngày khi đang locked_for_retry (xem
    # send_stuck_learner_reminders_task) — KHÔNG dùng chung last_reminder_sent_at của
    # PersonalizedRoadmap vì field đó cố tình ở cấp roadmap, dùng chung với digest 7h sáng bình
    # thường cho MỌI giai đoạn, không riêng cho ca bị khóa.
    last_boost_reminder_sent_at: Mapped[date | None] = mapped_column(Date, nullable=True)
