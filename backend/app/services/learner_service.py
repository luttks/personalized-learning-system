from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learner import (
    LearnerEvidence,
    LearnerProfile,
    LearnerTopicMastery,
    MasteryHistory,
    Roadmap,
    RoadmapItem,
)
from app.schemas.learner import (
    LearnerProfilePatch,
    LearningEventRequest,
    RoadmapPlan,
    UnderstandingResult,
)
from app.services.mastery_service import update_mastery


async def get_learner_profile(
    session: AsyncSession, user_id: UUID
) -> LearnerProfile | None:
    result = await session.execute(
        select(LearnerProfile).where(LearnerProfile.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def ensure_learner_profile(
    session: AsyncSession, user_id: UUID
) -> LearnerProfile:
    profile = await get_learner_profile(session, user_id)
    if profile is None:
        profile = LearnerProfile(user_id=user_id, missing_fields=[])
        session.add(profile)
        await session.flush()
    return profile


def profile_context(profile: LearnerProfile) -> dict[str, Any]:
    return {
        "education_level": profile.education_level,
        "subject": profile.subject,
        "learning_goal": profile.learning_goal,
        "deadline": profile.deadline,
        "current_level": profile.current_level,
        "known_concepts": profile.known_concepts,
        "weak_concepts": profile.weak_concepts,
        "misconceptions": profile.misconceptions,
        "minutes_per_day": profile.minutes_per_day,
        "days_per_week": profile.days_per_week,
        "available_periods": profile.available_periods,
        "learning_preferences": profile.learning_preferences,
        "diagnostic_results": profile.diagnostic_results,
        "confidence_scores": profile.confidence_scores,
    }


def apply_profile_patch(
    profile: LearnerProfile, patch: LearnerProfilePatch
) -> bool:
    data = patch.model_dump(exclude_unset=True, exclude_none=True)
    new_confidence = data.pop("confidence_scores", {})
    changed = False
    for field_name, value in data.items():
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if getattr(profile, field_name) != value:
            setattr(profile, field_name, value)
            changed = True
    merged_confidence = {**profile.confidence_scores, **new_confidence}
    if merged_confidence != profile.confidence_scores:
        profile.confidence_scores = merged_confidence
        changed = True
    return changed


async def save_understanding_result(
    session: AsyncSession,
    profile: LearnerProfile,
    result: UnderstandingResult,
    *,
    source: str,
) -> LearnerProfile:
    changed = apply_profile_patch(profile, result.profile_patch)
    if profile.missing_fields != result.missing_fields:
        profile.missing_fields = result.missing_fields
        changed = True
    if changed:
        profile.profile_version += 1

    now = datetime.now(UTC)
    for item in result.evidence:
        session.add(
            LearnerEvidence(
                learner_id=profile.id,
                evidence_type=item.evidence_type,
                source=source,
                topic_id=item.topic_id,
                field_name=item.field_name,
                value_json={"value": item.value},
                confidence=item.confidence,
                created_at=now,
            )
        )
    await session.commit()
    await session.refresh(profile)
    return profile


async def list_mastery(
    session: AsyncSession, learner_id: UUID
) -> list[LearnerTopicMastery]:
    result = await session.execute(
        select(LearnerTopicMastery)
        .where(LearnerTopicMastery.learner_id == learner_id)
        .order_by(LearnerTopicMastery.topic_id)
    )
    return list(result.scalars().all())


async def record_learning_event(
    session: AsyncSession,
    profile: LearnerProfile,
    event: LearningEventRequest,
) -> LearnerTopicMastery:
    now = datetime.now(UTC)
    mastery = await session.get(
        LearnerTopicMastery, (profile.id, event.topic_id)
    )
    if mastery is None:
        mastery = LearnerTopicMastery(
            learner_id=profile.id,
            topic_id=event.topic_id,
            mastery_score=0.0,
            confidence=0.0,
            repeated_errors=0,
            updated_at=now,
        )
        session.add(mastery)

    old_score = mastery.mastery_score
    mastery.mastery_score = update_mastery(
        mastery.mastery_score,
        correct=event.correct,
        difficulty=event.difficulty,
        hint_used=event.hint_used,
        attempt_count=event.attempt_count,
    )
    mastery.confidence = round(min(1.0, mastery.confidence + 0.15), 4)
    mastery.repeated_errors = 0 if event.correct else mastery.repeated_errors + 1
    mastery.last_assessed_at = now
    mastery.updated_at = now
    session.add(
        MasteryHistory(
            learner_id=profile.id,
            topic_id=event.topic_id,
            old_score=old_score,
            new_score=mastery.mastery_score,
            delta=round(mastery.mastery_score - old_score, 4),
            source=event.source,
            created_at=now,
        )
    )
    session.add(
        LearnerEvidence(
            learner_id=profile.id,
            evidence_type="assessment",
            source=event.source,
            topic_id=event.topic_id,
            field_name="topic_mastery",
            value_json=event.model_dump(mode="json"),
            confidence=mastery.confidence,
            created_at=now,
        )
    )
    await session.commit()
    await session.refresh(mastery)
    return mastery


async def persist_roadmap(
    session: AsyncSession,
    learner_id: UUID,
    plan: RoadmapPlan,
) -> tuple[Roadmap, list[RoadmapItem]]:
    roadmap = Roadmap(
        learner_id=learner_id,
        title=plan.title,
        subject=plan.subject,
        deadline=plan.deadline,
        total_estimated_minutes=plan.total_estimated_minutes,
        profile_version=plan.profile_version,
        context_json={
            "learning_gaps": [item.model_dump() for item in plan.learning_gaps],
            "skipped_concepts": [item.model_dump() for item in plan.skipped_concepts],
        },
    )
    session.add(roadmap)
    await session.flush()
    items = [
        RoadmapItem(
            roadmap_id=roadmap.id,
            **item.model_dump(),
        )
        for item in plan.items
    ]
    session.add_all(items)
    await session.commit()
    await session.refresh(roadmap)
    return roadmap, items
