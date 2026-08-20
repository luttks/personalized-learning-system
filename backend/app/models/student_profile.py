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


class EducationLevel(StrEnum):
    UNDER_UNIVERSITY = "under_university"
    UNIVERSITY = "university"



class StudentProfile(
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "student_profiles"

    __table_args__ = (
        CheckConstraint(
            "(education_level = 'under_university' AND grade_level >= 1 AND grade_level <= 12) OR "
            "(education_level = 'university' AND grade_level >= 1 AND grade_level <= 7)",
            name="grade_level_education_check",
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

    education_level: Mapped[EducationLevel] = mapped_column(
        Enum(
            EducationLevel,
            name="education_level",
            values_callable=lambda enum: [
                item.value for item in enum
            ],
        ),
        default=EducationLevel.UNDER_UNIVERSITY,
        nullable=False,
    )

    grade_level: Mapped[int] = mapped_column(
        Integer,
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