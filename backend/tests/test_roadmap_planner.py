from datetime import date

import pytest

from app.schemas.learner import ConceptInput, RoadmapCreateRequest
from app.services.roadmap_planner import (
    InvalidKnowledgeGraphError,
    RoadmapCapacityError,
    build_roadmap,
)


def request_for_trigonometry(**overrides: object) -> RoadmapCreateRequest:
    values = {
        "target_concept_ids": ["math.trigonometry.sin"],
        "concepts": [
            ConceptInput(
                id="math.algebra.equation",
                name="Phương trình đại số",
                difficulty=0.4,
                estimated_minutes=60,
            ),
            ConceptInput(
                id="math.trigonometry.sin",
                name="Tỉ số sin",
                difficulty=0.5,
                estimated_minutes=90,
                prerequisites=["math.algebra.equation"],
            ),
        ],
        "start_date": date(2026, 7, 29),
    }
    values.update(overrides)
    return RoadmapCreateRequest(**values)


def build(request: RoadmapCreateRequest, mastery: dict[str, float]):
    return build_roadmap(
        request,
        subject="mathematics",
        deadline=date(2026, 9, 28),
        minutes_per_day=60,
        days_per_week=6,
        profile_version=2,
        mastery=mastery,
    )


def test_roadmap_adds_weak_prerequisite_before_target() -> None:
    plan = build(
        request_for_trigonometry(),
        {"math.algebra.equation": 0.35, "math.trigonometry.sin": 0.2},
    )

    concepts = [item.concept_id for item in plan.items]
    assert concepts.index("math.algebra.equation") < concepts.index(
        "math.trigonometry.sin"
    )
    assert plan.learning_gaps[0].priority == "critical"
    assert all(item.estimated_minutes <= 60 for item in plan.items)


def test_roadmap_skips_mastered_prerequisite_and_personalizes_duration() -> None:
    novice = build(request_for_trigonometry(), {"math.algebra.equation": 0.9})
    experienced = build(
        request_for_trigonometry(),
        {"math.algebra.equation": 0.9, "math.trigonometry.sin": 0.65},
    )

    assert novice.total_estimated_minutes > experienced.total_estimated_minutes
    assert {
        item.concept_id for item in novice.skipped_concepts
    } == {"math.algebra.equation"}
    assert all(
        item.concept_id != "math.algebra.equation" for item in novice.items
    )


def test_mastered_target_does_not_schedule_its_weak_prerequisite() -> None:
    plan = build(
        request_for_trigonometry(),
        {"math.algebra.equation": 0.1, "math.trigonometry.sin": 0.9},
    )

    assert plan.items == []
    assert [item.concept_id for item in plan.skipped_concepts] == [
        "math.trigonometry.sin"
    ]


def test_roadmap_rejects_impossible_deadline() -> None:
    with pytest.raises(RoadmapCapacityError):
        build_roadmap(
            request_for_trigonometry(start_date=date(2026, 7, 29)),
            subject="mathematics",
            deadline=date(2026, 7, 29),
            minutes_per_day=10,
            days_per_week=7,
            profile_version=1,
            mastery={},
        )


def test_roadmap_rejects_prerequisite_cycle() -> None:
    request = RoadmapCreateRequest(
        target_concept_ids=["a"],
        concepts=[
            ConceptInput(id="a", name="A", prerequisites=["b"]),
            ConceptInput(id="b", name="B", prerequisites=["a"]),
        ],
    )
    with pytest.raises(InvalidKnowledgeGraphError):
        build(request, {})
