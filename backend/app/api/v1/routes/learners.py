from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.learner.understanding_agent import (
    LearnerUnderstandingAgent,
    LearnerUnderstandingError,
    OpenAICompatibleProvider,
)
from app.api.dependencies.auth import get_current_student
from app.core.config import settings
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.learner import (
    LearnerProfileResponse,
    LearnerProfileUpdate,
    LearningEventRequest,
    MasteryResponse,
    RoadmapCreateRequest,
    RoadmapCreateResponse,
    UnderstandInputRequest,
    UnderstandInputResponse,
)
from app.services.learner_service import (
    apply_profile_patch,
    ensure_learner_profile,
    get_learner_profile,
    list_mastery,
    persist_roadmap,
    profile_context,
    record_learning_event,
    save_understanding_result,
)
from app.services.mastery_service import mastery_level
from app.services.roadmap_planner import (
    InvalidKnowledgeGraphError,
    RoadmapCapacityError,
    build_roadmap,
)
from app.services.exam_service import crawl_resources

router = APIRouter(prefix="/learners", tags=["Adaptive Learning"])

CurrentStudent = Annotated[User, Depends(get_current_student)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@lru_cache
def get_understanding_agent() -> LearnerUnderstandingAgent:
    if not settings.llm_api_key or not settings.llm_model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Learner understanding is not configured. Set LLM_API_KEY "
                "and LLM_MODEL."
            ),
        )
    return LearnerUnderstandingAgent(
        OpenAICompatibleProvider(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    )


@router.get("/me", response_model=LearnerProfileResponse)
async def get_my_learner_profile(
    current_user: CurrentStudent,
    session: DatabaseSession,
) -> LearnerProfileResponse:
    profile = await get_learner_profile(session, current_user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Chưa có learner profile.")
    return LearnerProfileResponse.model_validate(profile)


@router.patch("/me", response_model=LearnerProfileResponse)
async def update_my_learner_profile(
    payload: LearnerProfileUpdate,
    current_user: CurrentStudent,
    session: DatabaseSession,
) -> LearnerProfileResponse:
    profile = await ensure_learner_profile(session, current_user.id)
    if apply_profile_patch(profile, payload):
        profile.profile_version += 1
    await session.commit()
    await session.refresh(profile)
    return LearnerProfileResponse.model_validate(profile)


@router.post(
    "/me/understand-input",
    response_model=UnderstandInputResponse,
)
async def understand_my_input(
    payload: UnderstandInputRequest,
    current_user: CurrentStudent,
    session: DatabaseSession,
    agent: Annotated[LearnerUnderstandingAgent, Depends(get_understanding_agent)],
) -> UnderstandInputResponse:
    profile = await ensure_learner_profile(session, current_user.id)
    try:
        result = await agent.analyze(
            message=payload.message,
            existing_profile=profile_context(profile),
            conversation_context=payload.conversation_context,
        )
    except LearnerUnderstandingError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không thể phân tích đầu vào học tập từ LLM.",
        ) from error

    profile = await save_understanding_result(
        session,
        profile,
        result,
        source=payload.session_id or "learner_input",
    )
    return UnderstandInputResponse(
        **result.model_dump(),
        profile=LearnerProfileResponse.model_validate(profile),
    )


@router.get("/me/mastery", response_model=list[MasteryResponse])
async def get_my_mastery(
    current_user: CurrentStudent,
    session: DatabaseSession,
) -> list[MasteryResponse]:
    profile = await get_learner_profile(session, current_user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Chưa có learner profile.")
    records = await list_mastery(session, profile.id)
    return [
        MasteryResponse(
            topic_id=item.topic_id,
            mastery_score=item.mastery_score,
            confidence=item.confidence,
            repeated_errors=item.repeated_errors,
            level=mastery_level(item.mastery_score),
            last_assessed_at=item.last_assessed_at,
        )
        for item in records
    ]


@router.post("/me/learning-events", response_model=MasteryResponse)
async def create_learning_event(
    payload: LearningEventRequest,
    current_user: CurrentStudent,
    session: DatabaseSession,
) -> MasteryResponse:
    profile = await get_learner_profile(session, current_user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Chưa có learner profile.")
    item = await record_learning_event(session, profile, payload)
    return MasteryResponse(
        topic_id=item.topic_id,
        mastery_score=item.mastery_score,
        confidence=item.confidence,
        repeated_errors=item.repeated_errors,
        level=mastery_level(item.mastery_score),
        last_assessed_at=item.last_assessed_at,
    )


@router.post(
    "/me/roadmaps",
    response_model=RoadmapCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_roadmap(
    payload: RoadmapCreateRequest,
    current_user: CurrentStudent,
    session: DatabaseSession,
) -> RoadmapCreateResponse:
    profile = await get_learner_profile(session, current_user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Chưa có learner profile.")

    missing = [
        field
        for field in (
            "subject", "learning_goal", "deadline",
            "minutes_per_day", "days_per_week",
        )
        if not getattr(profile, field)
    ]
    mastery_records = await list_mastery(session, profile.id)
    if not profile.current_level and not mastery_records:
        missing.append("current_level_or_diagnostic")
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Learner profile is incomplete for roadmap generation.",
                "missing_fields": missing,
            },
        )

    try:
        plan = build_roadmap(
            payload,
            subject=profile.subject,
            deadline=profile.deadline,
            minutes_per_day=profile.minutes_per_day,
            days_per_week=profile.days_per_week,
            profile_version=profile.profile_version,
            mastery={item.topic_id: item.mastery_score for item in mastery_records},
            learning_preferences=profile.learning_preferences,
        )
    except (InvalidKnowledgeGraphError, RoadmapCapacityError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    roadmap, _ = await persist_roadmap(session, profile.id, plan)

    # Crawl tài nguyên theo từng topic song song
    import asyncio
    topic_resources: dict[str, dict] = {}
    if plan.items:
        # Lấy danh sách topic duy nhất (tối đa 8 để không quá chậm)
        unique_concepts = {}
        for item in plan.items:
            if item.concept_id not in unique_concepts:
                unique_concepts[item.concept_id] = item.title
        limited = dict(list(unique_concepts.items())[:8])

        crawl_tasks = [
            crawl_resources(f"{concept_name} {profile.subject or ''}")
            for concept_name in limited.values()
        ]
        try:
            results = await asyncio.gather(*crawl_tasks, return_exceptions=True)
            for concept_id, result in zip(limited.keys(), results):
                if isinstance(result, dict):
                    topic_resources[concept_id] = result
        except Exception:
            pass

    return RoadmapCreateResponse(
        **plan.model_dump(), id=roadmap.id, status=roadmap.status,
        topic_resources=topic_resources,
    )
