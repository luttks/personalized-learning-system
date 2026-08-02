from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Course, CourseStatus
from app.models.content_catalog import ConceptPrerequisite, CourseConcept
from app.models.content_chunk import ContentChunk
from app.models.course_learning_path import CourseLearningPath
from app.models.diagnostic import DiagnosticAssessment, DiagnosticAttempt
from app.models.learner import LearnerProfile, LearnerTopicMastery
from app.models.learner_course_profile import LearnerCourseProfile
from app.models.user import User
from app.schemas.learner import ConceptInput, RoadmapCreateRequest
from app.services.roadmap_planner import (
    InvalidKnowledgeGraphError,
    RoadmapCapacityError,
    build_roadmap,
)


class CourseLearningPathUnavailableError(Exception):
    pass


class CourseLearningPathNotFoundError(Exception):
    pass


def path_response(path: CourseLearningPath, active_publication_id: UUID | None) -> dict:
    return {
        "id": path.id,
        "course_id": path.course_id,
        "publication_id": path.publication_id,
        "diagnostic_attempt_id": path.diagnostic_attempt_id,
        "path_version": path.path_version,
        "status": path.status,
        "title": path.title,
        "summary": path.summary,
        "required_mastery": path.required_mastery,
        "total_estimated_minutes": path.total_estimated_minutes,
        "profile_version": path.profile_version,
        "stale": path.publication_id != active_publication_id,
        "gaps": path.gaps_json,
        "skipped": path.skipped_json,
        "items": path.items_json,
        "created_at": path.created_at,
    }


async def create_course_learning_path(
    session: AsyncSession, user: User, course_id: UUID, required_mastery: float
) -> dict:
    course = await session.get(Course, course_id)
    profile = await session.scalar(
        select(LearnerCourseProfile).where(
            LearnerCourseProfile.user_id == user.id,
            LearnerCourseProfile.course_id == course_id,
        )
    )
    if (
        course is None
        or course.status != CourseStatus.PUBLISHED.value
        or profile is None
        or course.active_publication_id != profile.publication_id
    ):
        raise CourseLearningPathUnavailableError("Onboarding chưa hoàn tất hoặc đã cũ.")
    diagnostic_row = (
        await session.execute(
            select(DiagnosticAttempt, DiagnosticAssessment)
            .join(
                DiagnosticAssessment,
                DiagnosticAssessment.id == DiagnosticAttempt.assessment_id,
            )
            .where(
                DiagnosticAttempt.user_id == user.id,
                DiagnosticAssessment.course_id == course_id,
                DiagnosticAttempt.status == "submitted",
            )
            .order_by(DiagnosticAttempt.submitted_at.desc())
            .limit(1)
        )
    ).one_or_none()
    if diagnostic_row is None:
        raise CourseLearningPathUnavailableError(
            "Hãy hoàn thành bài chẩn đoán trước khi tạo lộ trình."
        )
    attempt, assessment = diagnostic_row
    if (
        assessment.publication_id != profile.publication_id
        or assessment.profile_version != profile.profile_version
    ):
        raise CourseLearningPathUnavailableError(
            "Bài chẩn đoán đã cũ; hãy làm lại sau khi cập nhật onboarding."
        )
    version_ids = [UUID(value) for value in profile.version_ids_json]
    concepts = list(
        (
            await session.scalars(
                select(CourseConcept)
                .where(CourseConcept.course_version_id.in_(version_ids))
                .order_by(CourseConcept.created_at)
            )
        ).all()
    )
    concept_ids = [item.id for item in concepts]
    prerequisites = (
        list(
            (
                await session.scalars(
                    select(ConceptPrerequisite).where(
                        ConceptPrerequisite.concept_id.in_(concept_ids)
                    )
                )
            ).all()
        )
        if concept_ids
        else []
    )
    prerequisites_by_concept: dict[UUID, list[str]] = {}
    for item in prerequisites:
        prerequisites_by_concept.setdefault(item.concept_id, []).append(
            str(item.prerequisite_concept_id)
        )
    request = RoadmapCreateRequest(
        title=f"Lộ trình {course.title}",
        target_concept_ids=[str(item.id) for item in concepts],
        concepts=[
            ConceptInput(
                id=str(item.id),
                name=item.title,
                description=item.description,
                difficulty=0.5,
                estimated_minutes=item.estimated_minutes,
                prerequisites=prerequisites_by_concept.get(item.id, []),
            )
            for item in concepts
        ],
        required_mastery=required_mastery,
        start_date=profile.start_date,
    )
    learner = await session.scalar(
        select(LearnerProfile).where(LearnerProfile.user_id == user.id)
    )
    mastery_records = (
        list(
            (
                await session.scalars(
                    select(LearnerTopicMastery).where(
                        LearnerTopicMastery.learner_id == learner.id
                    )
                )
            ).all()
        )
        if learner
        else []
    )
    mastery = {item.topic_id: item.mastery_score for item in mastery_records}
    try:
        plan = build_roadmap(
            request,
            subject=course.subject,
            deadline=profile.deadline,
            minutes_per_day=profile.minutes_per_day,
            days_per_week=profile.days_per_week,
            profile_version=profile.profile_version,
            mastery=mastery,
            learning_preferences={"preferred_sequence": profile.content_formats},
        )
    except (InvalidKnowledgeGraphError, RoadmapCapacityError) as error:
        raise CourseLearningPathUnavailableError(str(error)) from error
    concept_by_id = {str(item.id): item for item in concepts}
    items = []
    for item in plan.items:
        concept = concept_by_id[item.concept_id]
        chunks = list(
            (
                await session.scalars(
                    select(ContentChunk)
                    .where(ContentChunk.lesson_id == concept.lesson_id)
                    .order_by(ContentChunk.chunk_index)
                    .limit(3)
                )
            ).all()
        )
        items.append(
            {
                **item.model_dump(mode="json"),
                "concept_id": item.concept_id,
                "lesson_id": str(concept.lesson_id),
                "objective": concept.description,
                "instructions": f"Học nội dung '{concept.title}', ghi lại ý chính và hoàn thành hoạt động {item.activity_type}.",
                "completion_criteria": [
                    "Nêu được ý chính bằng lời của mình.",
                    "Hoàn thành hoạt động của phiên học.",
                ],
                "source_chunk_ids": [str(chunk.id) for chunk in chunks],
            }
        )
    path_version = (
        int(
            await session.scalar(
                select(
                    func.coalesce(func.max(CourseLearningPath.path_version), 0)
                ).where(
                    CourseLearningPath.user_id == user.id,
                    CourseLearningPath.course_id == course_id,
                )
            )
            or 0
        )
        + 1
    )
    path = CourseLearningPath(
        user_id=user.id,
        course_id=course_id,
        publication_id=profile.publication_id,
        learner_course_profile_id=profile.id,
        profile_version=profile.profile_version,
        diagnostic_attempt_id=attempt.id,
        path_version=path_version,
        status="proposed",
        title=plan.title,
        summary=f"Lộ trình dựa trên mục tiêu '{profile.learning_goal}' và kết quả chẩn đoán gần nhất.",
        required_mastery=required_mastery,
        total_estimated_minutes=plan.total_estimated_minutes,
        mastery_snapshot_json=mastery,
        gaps_json=[item.model_dump() for item in plan.learning_gaps],
        skipped_json=[item.model_dump() for item in plan.skipped_concepts],
        items_json=items,
        generator="deterministic-course-planner-v1",
    )
    session.add(path)
    await session.commit()
    await session.refresh(path)
    return path_response(path, course.active_publication_id)


async def get_latest_course_learning_path(
    session: AsyncSession, user: User, course_id: UUID
) -> dict:
    path = await session.scalar(
        select(CourseLearningPath)
        .where(
            CourseLearningPath.user_id == user.id,
            CourseLearningPath.course_id == course_id,
        )
        .order_by(CourseLearningPath.path_version.desc())
        .limit(1)
    )
    if path is None:
        raise CourseLearningPathNotFoundError
    course = await session.get(Course, course_id)
    return path_response(path, course.active_publication_id if course else None)
