import asyncio
from collections.abc import Mapping
from typing import Any

import pytest

from app.agents.learner.understanding_agent import (
    LearnerUnderstandingAgent,
    LearnerUnderstandingError,
)


class FakeProvider:
    def __init__(self, result: Mapping[str, Any]) -> None:
        self.result = result
        self.user_prompt = ""

    async def complete_json(
        self, *, system_prompt: str, user_prompt: str
    ) -> Mapping[str, Any]:
        assert "Never invent" in system_prompt
        self.user_prompt = user_prompt
        return self.result


def test_agent_extracts_facts_and_recomputes_missing_fields() -> None:
    provider = FakeProvider(
        {
            "profile_patch": {
                "education_level": "grade_10",
                "subject": "mathematics",
                "learning_goal": {
                    "type": "exam_score",
                    "target": 8,
                },
                "deadline": "2026-09-28",
                "current_level": None,
                "weak_concepts": ["trigonometry"],
                "minutes_per_day": 60,
                "days_per_week": 6,
                "confidence_scores": {
                    "weak_concepts": 0.9,
                    "minutes_per_day": 0.95,
                },
            },
            "evidence": [
                {
                    "field_name": "weak_concepts",
                    "topic_id": "trigonometry",
                    "value": ["trigonometry"],
                    "evidence_type": "self_report",
                    "confidence": 0.9,
                }
            ],
            "missing_fields": [],
            "contradictions": [],
            "clarification_question": "Bạn đã làm bài chẩn đoán chưa?",
            "diagnostic_required": False,
        }
    )
    result = asyncio.run(
        LearnerUnderstandingAgent(provider).analyze(
            "Em học lớp 10, yếu lượng giác và muốn đạt 8 điểm.",
        )
    )

    assert result.profile_patch.subject == "mathematics"
    assert result.profile_patch.current_level is None
    assert result.missing_fields == ["diagnostic_score"]
    assert result.diagnostic_required is True
    assert "learner_message" in provider.user_prompt


def test_agent_rejects_out_of_range_confidence() -> None:
    provider = FakeProvider(
        {
            "profile_patch": {"confidence_scores": {"subject": 1.5}},
            "evidence": [],
            "missing_fields": [],
            "contradictions": [],
            "diagnostic_required": True,
        }
    )
    with pytest.raises(LearnerUnderstandingError):
        asyncio.run(
            LearnerUnderstandingAgent(provider).analyze("Tôi muốn học toán")
        )
