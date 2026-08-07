from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LearningGoal(BaseModel):
    type: str | None = None
    description: str | None = None
    target: str | float | int | None = None


class LearningPreferences(BaseModel):
    preferred_sequence: list[str] = Field(default_factory=list)
    content_formats: list[str] = Field(default_factory=list)
    preferred_difficulty: str | None = None


class LearnerProfilePatch(BaseModel):
    education_level: str | None = None
    subject: str | None = None
    learning_goal: LearningGoal | None = None
    deadline: date | None = None
    current_level: str | None = None
    known_concepts: list[str] | None = None
    weak_concepts: list[str] | None = None
    misconceptions: list[str] | None = None
    minutes_per_day: int | None = Field(default=None, ge=10, le=600)
    days_per_week: int | None = Field(default=None, ge=1, le=7)
    available_periods: list[str] | None = None
    learning_preferences: LearningPreferences | None = None
    confidence_scores: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_confidence(self) -> "LearnerProfilePatch":
        invalid = [
            key for key, value in self.confidence_scores.items()
            if not 0 <= value <= 1
        ]
        if invalid:
            raise ValueError(f"confidence must be between 0 and 1: {invalid}")
        return self


class LearnerProfileUpdate(LearnerProfilePatch):
    pass


class LearnerProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    education_level: str | None
    subject: str | None
    learning_goal: dict[str, Any]
    deadline: date | None
    current_level: str | None
    known_concepts: list[str]
    weak_concepts: list[str]
    misconceptions: list[str]
    minutes_per_day: int | None
    days_per_week: int | None
    available_periods: list[str]
    learning_preferences: dict[str, Any]
    diagnostic_results: list[dict[str, Any]]
    confidence_scores: dict[str, float]
    missing_fields: list[str]
    profile_version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnderstandInputRequest(BaseModel):
    message: str = Field(min_length=3, max_length=10_000)
    session_id: str | None = Field(default=None, max_length=255)
    conversation_context: str | None = Field(default=None, max_length=20_000)


class EvidenceInput(BaseModel):
    field_name: str | None = None
    topic_id: str | None = None
    value: Any
    evidence_type: Literal["self_report", "conversation", "inference"]
    confidence: float = Field(ge=0, le=1)


class Contradiction(BaseModel):
    field_name: str
    existing_value: Any
    new_value: Any
    explanation: str


class UnderstandingResult(BaseModel):
    profile_patch: LearnerProfilePatch
    evidence: list[EvidenceInput] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    clarification_question: str | None = None
    diagnostic_required: bool = True


class UnderstandInputResponse(UnderstandingResult):
    profile: LearnerProfileResponse


class LearningEventRequest(BaseModel):
    topic_id: str = Field(min_length=1, max_length=255)
    correct: bool
    difficulty: float = Field(ge=0, le=1)
    hint_used: bool = False
    attempt_count: int = Field(default=1, ge=1, le=100)
    source: str = Field(default="quiz", max_length=100)


class MasteryResponse(BaseModel):
    topic_id: str
    mastery_score: float
    confidence: float
    repeated_errors: int
    level: str
    last_assessed_at: datetime | None


class ConceptInput(BaseModel):
    id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    difficulty: float = Field(default=0.5, ge=0, le=1)
    estimated_minutes: int = Field(default=60, ge=5, le=10_000)
    prerequisites: list[str] = Field(default_factory=list)


class RoadmapCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    target_concept_ids: list[str] = Field(min_length=1)
    concepts: list[ConceptInput] = Field(min_length=1)
    required_mastery: float = Field(default=0.7, ge=0.1, le=1)
    start_date: date = Field(default_factory=date.today)


class LearningGap(BaseModel):
    concept_id: str
    current_mastery: float
    required_mastery: float
    priority: Literal["critical", "high", "normal"]
    reason: str


class SkippedConcept(BaseModel):
    concept_id: str
    reason: str


class RoadmapItemPlan(BaseModel):
    concept_id: str
    title: str
    sequence: int
    session_number: int
    planned_date: date
    estimated_minutes: int
    activity_type: str


class RoadmapPlan(BaseModel):
    title: str
    subject: str
    deadline: date | None
    total_estimated_minutes: int
    profile_version: int
    learning_gaps: list[LearningGap]
    skipped_concepts: list[SkippedConcept]
    items: list[RoadmapItemPlan]


class RoadmapCreateResponse(RoadmapPlan):
    id: UUID
    status: str
    topic_resources: dict[str, dict] = Field(
        default_factory=dict,
        description="Tài nguyên crawl theo từng topic: {concept_id: {youtube, quiz, academic, github}}"
    )
