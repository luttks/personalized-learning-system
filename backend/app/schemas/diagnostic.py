from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DiagnosticQuestion(BaseModel):
    id: UUID
    concept_id: UUID
    lesson_title: str
    prompt: str
    options: list[str]
    source_label: str


class DiagnosticAttemptResponse(BaseModel):
    attempt_id: UUID
    assessment_id: UUID
    course_id: UUID
    status: str
    assessment_version: int
    questions: list[DiagnosticQuestion]
    started_at: datetime


class DiagnosticSubmitRequest(BaseModel):
    answers: list[int] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=100)


class DiagnosticConceptResult(BaseModel):
    concept_id: UUID
    concept_title: str
    correct: bool
    selected_index: int
    correct_index: int


class DiagnosticResultResponse(BaseModel):
    attempt_id: UUID
    status: str
    score: float
    correct_count: int
    question_count: int
    results: list[DiagnosticConceptResult]
    submitted_at: datetime
