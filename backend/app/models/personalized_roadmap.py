from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class PersonalizedRoadmap(Base, UUIDPrimaryKeyMixin):
    """Lưu trữ lộ trình học tập được tạo ra từ AI cho người dùng."""
    __tablename__ = "personalized_roadmaps"

    learner_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("learner_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    exam_analysis_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("exam_analyses.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    overview: Mapped[str] = mapped_column(Text, nullable=False)
    total_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # JSON schema containing the phases and phase resources.
    # ⚠️ SQLAlchemy KHÔNG tự phát hiện mutate nested dict/list bên trong cột JSON này tại chỗ — nếu
    # lấy `roadmap.roadmap_data.get("phases")`, sửa trực tiếp vào đó, rồi mới gán lại
    # `roadmap.roadmap_data = ...`, baseline so sánh dirty-tracking và giá trị mới trỏ CHUNG một
    # object nên SQLAlchemy thấy "bằng nhau", ÂM THẦM BỎ QUA việc UPDATE (xác nhận qua test trực
    # tiếp: gán xong, commit() không lỗi, nhưng DB không đổi). LUÔN copy.deepcopy() cấu trúc lồng
    # nhau trước khi mutate, rồi gán lại TOÀN BỘ giá trị mới cho roadmap_data.
    roadmap_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Thời điểm người dùng bấm "Áp dụng lộ trình" — có giá trị nghĩa là lộ trình đang active:
    # được gửi email nhắc học hằng ngày và tính tiến độ giai đoạn.
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    # Giai đoạn hiện tại người học được phép làm — chỉ tăng khi vượt qua bài kiểm tra cuối giai
    # đoạn trước đó (PhaseAssessment tương ứng status='passed').
    current_phase_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Ngày gần nhất đã gửi email nhắc học cho lộ trình này — dùng để task Celery hằng ngày không
    # gửi trùng nếu lịch beat lỡ chạy nhiều lần trong cùng một ngày.
    last_reminder_sent_at: Mapped[date | None] = mapped_column(Date, nullable=True)
