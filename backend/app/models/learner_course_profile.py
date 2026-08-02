from datetime import date
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LearnerCourseProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "learner_course_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_learner_course_profiles_user_course"),
        CheckConstraint("deadline >= start_date", name="learner_course_profile_date_order"),
        CheckConstraint(
            "minutes_per_day >= 10 AND minutes_per_day <= 600",
            name="learner_course_profile_minutes_range",
        ),
        CheckConstraint(
            "days_per_week >= 1 AND days_per_week <= 7",
            name="learner_course_profile_days_range",
        ),
        CheckConstraint("profile_version >= 1", name="learner_course_profile_version_positive"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    course_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    publication_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_publications.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    learning_goal: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    deadline: Mapped[date] = mapped_column(Date, nullable=False)
    minutes_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    available_periods: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    content_formats: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
