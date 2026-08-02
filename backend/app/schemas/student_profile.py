from datetime import date, datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.models.student_profile import (
    ExplanationDepth,
    LearningMode,
)


class StudentProfileBase(BaseModel):
    date_of_birth: date | None = None

    grade_level: int = Field(
        ge=1,
        le=12,
    )

    school_name: str | None = Field(
        default=None,
        max_length=255,
    )

    city: str | None = Field(
        default=None,
        max_length=100,
    )

    preferred_learning_mode: LearningMode = (
        LearningMode.BALANCED
    )

    explanation_depth: ExplanationDepth = (
        ExplanationDepth.MEDIUM
    )

    preferred_session_minutes: int = Field(
        default=30,
        ge=10,
        le=180,
    )

    study_days_per_week: int = Field(
        default=4,
        ge=1,
        le=7,
    )

    study_minutes_per_day: int = Field(
        default=45,
        ge=10,
        le=600,
    )

    favourite_subjects: str | None = None
    difficult_subjects: str | None = None
    learning_notes: str | None = None


class StudentProfileCreate(StudentProfileBase):
    pass


class StudentProfileUpdate(BaseModel):
    date_of_birth: date | None = None

    grade_level: int | None = Field(
        default=None,
        ge=1,
        le=12,
    )

    school_name: str | None = Field(
        default=None,
        max_length=255,
    )

    city: str | None = Field(
        default=None,
        max_length=100,
    )

    preferred_learning_mode: LearningMode | None = None
    explanation_depth: ExplanationDepth | None = None

    preferred_session_minutes: int | None = Field(
        default=None,
        ge=10,
        le=180,
    )

    study_days_per_week: int | None = Field(
        default=None,
        ge=1,
        le=7,
    )

    study_minutes_per_day: int | None = Field(
        default=None,
        ge=10,
        le=600,
    )

    favourite_subjects: str | None = None
    difficult_subjects: str | None = None
    learning_notes: str | None = None


class StudentProfileResponse(StudentProfileBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )