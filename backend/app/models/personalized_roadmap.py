from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
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
    
    # JSON schema containing the phases and phase resources
    roadmap_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
