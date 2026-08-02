from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CourseLearningPathCreate(BaseModel):
    required_mastery: float = Field(default=0.7, ge=0.3, le=1)


class CourseLearningPathItem(BaseModel):
    concept_id: UUID
    lesson_id: UUID
    title: str
    objective: str
    sequence: int
    session_number: int
    planned_date: date
    estimated_minutes: int
    activity_type: str
    instructions: str
    completion_criteria: list[str]
    source_chunk_ids: list[UUID]


class CourseLearningPathResponse(BaseModel):
    id: UUID
    course_id: UUID
    publication_id: UUID
    diagnostic_attempt_id: UUID
    path_version: int
    status: str
    title: str
    summary: str
    required_mastery: float
    total_estimated_minutes: int
    profile_version: int
    stale: bool
    gaps: list[dict]
    skipped: list[dict]
    items: list[CourseLearningPathItem]
    created_at: datetime
