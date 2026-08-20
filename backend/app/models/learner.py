from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LearnerProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "learner_profiles"
    __table_args__ = (
        CheckConstraint(
            "minutes_per_day >= 10 AND minutes_per_day <= 600",
            name="learner_minutes_per_day_range",
        ),
        CheckConstraint(
            "days_per_week >= 1 AND days_per_week <= 7",
            name="learner_days_per_week_range",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    education_level: Mapped[str | None] = mapped_column(String(100))
    subject: Mapped[str | None] = mapped_column(String(150), index=True)
    learning_goal: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date)
    current_level: Mapped[str | None] = mapped_column(String(100))
    known_concepts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    weak_concepts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    misconceptions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    minutes_per_day: Mapped[int | None] = mapped_column(Integer)
    days_per_week: Mapped[int | None] = mapped_column(Integer)
    available_periods: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    learning_preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    diagnostic_results: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    confidence_scores: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    missing_fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class LearnerEvidence(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "learner_evidence"

    learner_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("learner_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    topic_id: Mapped[str | None] = mapped_column(String(255), index=True)
    field_name: Mapped[str | None] = mapped_column(String(100))
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class LearnerTopicMastery(Base):
    __tablename__ = "learner_topic_mastery"
    __table_args__ = (
        CheckConstraint(
            "mastery_score >= 0 AND mastery_score <= 1",
            name="mastery_score_range",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="mastery_confidence_range",
        ),
    )

    learner_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("learner_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    repeated_errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class MasteryHistory(Base, UUIDPrimaryKeyMixin):
    """Nhật ký thay đổi mastery — append-only, phục vụ đánh giá hiệu quả khuyến nghị + báo cáo tiến bộ theo thời gian."""
    __tablename__ = "mastery_history"

    learner_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("learner_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    topic_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    old_score: Mapped[float] = mapped_column(Float, nullable=False)
    new_score: Mapped[float] = mapped_column(Float, nullable=False)
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Roadmap(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roadmaps"

    learner_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("learner_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date)
    total_estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RoadmapItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roadmap_items"
    __table_args__ = (
        UniqueConstraint(
            "roadmap_id", "sequence", name="uq_roadmap_items_sequence"
        ),
    )

    roadmap_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("roadmaps.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    concept_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
