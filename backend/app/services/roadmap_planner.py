from collections.abc import Mapping
from datetime import date, timedelta
from math import ceil
from typing import Any

from app.schemas.learner import (
    ConceptInput,
    LearningGap,
    RoadmapCreateRequest,
    RoadmapItemPlan,
    RoadmapPlan,
    SkippedConcept,
)


class InvalidKnowledgeGraphError(ValueError):
    pass


class RoadmapCapacityError(ValueError):
    pass


def _topological_order(
    selected: set[str],
    concepts: Mapping[str, ConceptInput],
    roots: list[str],
) -> list[str]:
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(concept_id: str) -> None:
        if concept_id in visited:
            return
        if concept_id in visiting:
            raise InvalidKnowledgeGraphError(
                f"Prerequisite cycle detected at '{concept_id}'"
            )
        visiting.add(concept_id)
        for prerequisite in concepts[concept_id].prerequisites:
            if prerequisite in selected:
                visit(prerequisite)
        visiting.remove(concept_id)
        visited.add(concept_id)
        ordered.append(concept_id)

    for concept_id in roots:
        if concept_id in selected:
            visit(concept_id)
    return ordered


def _next_study_date(current: date, days_per_week: int) -> date:
    candidate = current
    allowed_weekdays = set(range(days_per_week))
    while candidate.weekday() not in allowed_weekdays:
        candidate += timedelta(days=1)
    return candidate


def build_roadmap(
    request: RoadmapCreateRequest,
    *,
    subject: str,
    deadline: date | None,
    minutes_per_day: int,
    days_per_week: int,
    profile_version: int,
    mastery: Mapping[str, float],
    learning_preferences: Mapping[str, Any] | None = None,
) -> RoadmapPlan:
    if deadline and request.start_date > deadline:
        raise RoadmapCapacityError("The roadmap start date is after the deadline")

    concept_map = {concept.id: concept for concept in request.concepts}
    if len(concept_map) != len(request.concepts):
        raise InvalidKnowledgeGraphError("Concept IDs must be unique")

    unknown_targets = set(request.target_concept_ids) - set(concept_map)
    if unknown_targets:
        raise InvalidKnowledgeGraphError(
            f"Unknown target concepts: {sorted(unknown_targets)}"
        )
    unknown_prerequisites = {
        prerequisite
        for concept in request.concepts
        for prerequisite in concept.prerequisites
        if prerequisite not in concept_map
    }
    if unknown_prerequisites:
        raise InvalidKnowledgeGraphError(
            f"Unknown prerequisites: {sorted(unknown_prerequisites)}"
        )

    required: set[str] = set()
    prerequisite_ids: set[str] = set()
    skipped_by_id: dict[str, SkippedConcept] = {}

    def collect(concept_id: str, is_prerequisite: bool = False) -> None:
        current = max(0.0, min(1.0, mastery.get(concept_id, 0.0)))
        if current >= request.required_mastery:
            skipped_by_id[concept_id] = SkippedConcept(
                concept_id=concept_id,
                reason=(
                    f"Current mastery {current:.2f} meets the "
                    f"required {request.required_mastery:.2f}"
                ),
            )
            return
        if is_prerequisite:
            prerequisite_ids.add(concept_id)
        if concept_id in required:
            return
        required.add(concept_id)
        for prerequisite in concept_map[concept_id].prerequisites:
            collect(prerequisite, True)

    for target in request.target_concept_ids:
        collect(target)

    selected: set[str] = set()
    gaps: list[LearningGap] = []
    for concept_id in required:
        current = max(0.0, min(1.0, mastery.get(concept_id, 0.0)))
        selected.add(concept_id)
        is_prerequisite = concept_id in prerequisite_ids
        gaps.append(
            LearningGap(
                concept_id=concept_id,
                current_mastery=current,
                required_mastery=request.required_mastery,
                priority="critical" if is_prerequisite else "high",
                reason=(
                    "Prerequisite below required mastery"
                    if is_prerequisite
                    else "Target concept below required mastery"
                ),
            )
        )

    ordered = _topological_order(
        selected, concept_map, request.target_concept_ids
    )
    gap_by_id = {gap.concept_id: gap for gap in gaps}
    preferences = learning_preferences or {}
    activities = preferences.get("preferred_sequence") or [
        "worked_example",
        "guided_practice",
        "independent_practice",
    ]

    items: list[RoadmapItemPlan] = []
    sequence = 1
    session = 1
    planned_date = _next_study_date(request.start_date, days_per_week)
    for concept_id in ordered:
        concept = concept_map[concept_id]
        gap = gap_by_id[concept_id].required_mastery - gap_by_id[concept_id].current_mastery
        difficulty_factor = 0.75 + concept.difficulty * 0.5
        estimated = max(
            5,
            ceil(concept.estimated_minutes * difficulty_factor * (1 + gap)),
        )
        remaining = estimated
        chunk_index = 0
        while remaining:
            chunk = min(minutes_per_day, remaining)
            if deadline and planned_date > deadline:
                raise RoadmapCapacityError(
                    "The roadmap cannot fit the learner's daily capacity before "
                    f"the deadline {deadline.isoformat()}"
                )
            items.append(
                RoadmapItemPlan(
                    concept_id=concept_id,
                    title=concept.name,
                    sequence=sequence,
                    session_number=session,
                    planned_date=planned_date,
                    estimated_minutes=chunk,
                    activity_type=activities[chunk_index % len(activities)],
                )
            )
            remaining -= chunk
            chunk_index += 1
            sequence += 1
            session += 1
            planned_date = _next_study_date(
                planned_date + timedelta(days=1), days_per_week
            )

    return RoadmapPlan(
        title=request.title or f"{subject} personalized roadmap",
        subject=subject,
        deadline=deadline,
        total_estimated_minutes=sum(item.estimated_minutes for item in items),
        profile_version=profile_version,
        learning_gaps=sorted(gaps, key=lambda gap: ordered.index(gap.concept_id)),
        skipped_concepts=sorted(
            skipped_by_id.values(), key=lambda item: item.concept_id
        ),
        items=items,
    )
