import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError

from app.schemas.learner import UnderstandingResult


class LearnerUnderstandingError(Exception):
    """The provider failed or returned an invalid structured result."""


class ChatCompletionProvider(Protocol):
    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> Mapping[str, Any]: ...


SYSTEM_PROMPT = """You extract a learner profile from the learner's own words.
Return one JSON object matching this exact shape:
{
  "profile_patch": {
    "education_level": string|null,
    "subject": string|null,
    "learning_goal": {"type": string|null, "description": string|null, "target": string|number|null}|null,
    "deadline": "YYYY-MM-DD"|null,
    "current_level": string|null,
    "known_concepts": [string]|null,
    "weak_concepts": [string]|null,
    "misconceptions": [string]|null,
    "minutes_per_day": integer|null,
    "days_per_week": integer|null,
    "available_periods": [string]|null,
    "learning_preferences": {"preferred_sequence": [string], "content_formats": [string], "preferred_difficulty": string|null}|null,
    "confidence_scores": {"field_name": number}
  },
  "evidence": [{"field_name": string|null, "topic_id": string|null, "value": any, "evidence_type": "self_report"|"conversation"|"inference", "confidence": number}],
  "missing_fields": [string],
  "contradictions": [{"field_name": string, "existing_value": any, "new_value": any, "explanation": string}],
  "clarification_question": string|null,
  "diagnostic_required": boolean
}
Rules:
- Never invent a level, deadline, schedule, target, preference, or concept.
- Use inference only when clearly implied and give it lower confidence.
- A learner's self-assessed level does not remove the need for a diagnostic.
- Compare new facts with the existing profile and report contradictions.
- Ask exactly one concise clarification question for the highest-priority missing field.
- Keep concept labels in the language used by the learner.
- Output JSON only.
"""


REQUIRED_FOR_ROADMAP = (
    "subject",
    "learning_goal",
    "deadline",
    "minutes_per_day",
    "days_per_week",
)


class LearnerUnderstandingAgent:
    def __init__(self, provider: ChatCompletionProvider) -> None:
        self.provider = provider

    async def analyze(
        self,
        message: str,
        existing_profile: dict[str, Any] | None = None,
        conversation_context: str | None = None,
    ) -> UnderstandingResult:
        existing = existing_profile or {}
        user_prompt = json.dumps(
            {
                "today": datetime.now(UTC).date().isoformat(),
                "learner_message": message,
                "existing_profile": existing,
                "conversation_context": conversation_context,
            },
            ensure_ascii=False,
            default=str,
        )
        raw_result = await self.provider.complete_json(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        try:
            result = UnderstandingResult.model_validate(raw_result)
        except ValidationError as error:
            raise LearnerUnderstandingError(
                "LLM result does not match the learner profile schema"
            ) from error

        merged = dict(existing)
        merged.update(
            result.profile_patch.model_dump(
                exclude_none=True,
                exclude={"confidence_scores"},
            )
        )
        missing = [field for field in REQUIRED_FOR_ROADMAP if not merged.get(field)]
        if not merged.get("current_level") and not merged.get("diagnostic_results"):
            missing.append("diagnostic_score")
        result.missing_fields = list(dict.fromkeys(missing + result.missing_fields))
        result.diagnostic_required = not bool(merged.get("diagnostic_results"))
        return result
