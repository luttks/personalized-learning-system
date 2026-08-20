from datetime import date, datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.models.student_profile import EducationLevel


class StudentProfileBase(BaseModel):
    education_level: EducationLevel = EducationLevel.UNDER_UNIVERSITY

    grade_level: int = Field(
        ge=1,
        le=12,
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


class StudentProfileCreate(StudentProfileBase):
    @model_validator(mode="after")
    def validate_grade_level(self) -> "StudentProfileCreate":
        if self.education_level == EducationLevel.UNDER_UNIVERSITY:
            if self.grade_level < 1 or self.grade_level > 12:
                raise ValueError("grade_level must be between 1 and 12 for under_university")
        elif self.education_level == EducationLevel.UNIVERSITY:
            if self.grade_level < 1 or self.grade_level > 7:
                raise ValueError("grade_level must be between 1 and 7 for university")
        return self


class StudentProfileUpdate(BaseModel):
    education_level: EducationLevel | None = None

    grade_level: int | None = Field(
        default=None,
        ge=1,
        le=12,
    )

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


class StudentProfileResponse(StudentProfileBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )