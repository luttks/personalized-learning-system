from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learner import (
    LearnerEvidence,
    LearnerProfile,
    LearnerTopicMastery,
    MasteryHistory,
)
from app.schemas.learner import LearningEventRequest
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
