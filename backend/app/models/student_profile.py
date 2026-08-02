from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class LearningMode(StrEnum):
    THEORY_FIRST = "theory_first"
    PRACTICE_FIRST = "practice_first"
    STEP_BY_STEP = "step_by_step"
    BALANCED = "balanced"


class ExplanationDepth(StrEnum):
    SHORT = "short"
    MEDIUM = "medium"
    DETAILED = "detailed"


class StudentProfile(
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "student_profiles"

    __table_args__ = (
        CheckConstraint(
            "grade_level >= 1 AND grade_level <= 12",
            name="grade_level_range",
        ),
        CheckConstraint(
            (
                "preferred_session_minutes >= 10 "
                "AND preferred_session_minutes <= 180"
            ),
            name="session_minutes_range",
        ),
        CheckConstraint(
            (
                "study_days_per_week >= 1 "
                "AND study_days_per_week <= 7"
            ),
            name="study_days_range",
        ),
        CheckConstraint(
            (
                "study_minutes_per_day >= 10 "
                "AND study_minutes_per_day <= 600"
            ),
            name="study_minutes_range",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
        index=True,
    )

    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    grade_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    school_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    preferred_learning_mode: Mapped[LearningMode] = mapped_column(
        Enum(
            LearningMode,
            name="learning_mode",
            values_callable=lambda enum: [
                item.value for item in enum
            ],
        ),
        default=LearningMode.BALANCED,
        nullable=False,
    )

    explanation_depth: Mapped[ExplanationDepth] = mapped_column(
        Enum(
            ExplanationDepth,
            name="explanation_depth",
            values_callable=lambda enum: [
                item.value for item in enum
            ],
        ),
        default=ExplanationDepth.MEDIUM,
        nullable=False,
    )

    preferred_session_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )

    study_days_per_week: Mapped[int] = mapped_column(
        Integer,
        default=4,
        nullable=False,
    )

    study_minutes_per_day: Mapped[int] = mapped_column(
        Integer,
        default=45,
        nullable=False,
    )

    favourite_subjects: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    difficult_subjects: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    learning_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )