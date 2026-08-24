from pydantic import BaseModel, Field


class LearningEventRequest(BaseModel):
    topic_id: str = Field(min_length=1, max_length=255)
    correct: bool
    difficulty: float = Field(ge=0, le=1)
    hint_used: bool = False
    attempt_count: int = Field(default=1, ge=1, le=100)
    source: str = Field(default="quiz", max_length=100)
