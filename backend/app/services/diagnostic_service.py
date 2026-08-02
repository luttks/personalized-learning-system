from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.learner.understanding_agent import OpenAICompatibleProvider
from app.core.config import settings
from app.models.content import Course, CourseStatus
from app.models.content_catalog import CourseChapter, CourseConcept, CourseLesson
from app.models.content_chunk import ContentChunk
from app.models.diagnostic import DiagnosticAssessment, DiagnosticAttempt
from app.models.learner import LearnerEvidence, LearnerTopicMastery
from app.models.learner_course_profile import LearnerCourseProfile
from app.models.user import User
from app.services.diagnostic_question_generator import generate_diagnostic_questions
from app.services.learner_service import ensure_learner_profile
from app.services.mastery_service import update_mastery


class DiagnosticUnavailableError(Exception):
    pass


class DiagnosticConflictError(Exception):
    pass


class DiagnosticNotFoundError(Exception):
    pass


def public_question(question: dict) -> dict:
    return {
        key: question[key]
        for key in (
            "id",
            "concept_id",
            "lesson_title",
            "prompt",
            "options",
            "source_label",
        )
    }


async def start_diagnostic(session: AsyncSession, user: User, course_id: UUID) -> dict:
    profile = await session.scalar(
        select(LearnerCourseProfile).where(
            LearnerCourseProfile.user_id == user.id,
            LearnerCourseProfile.course_id == course_id,
        )
    )
    if profile is None:
        raise DiagnosticUnavailableError(
            "Hãy hoàn thành onboarding trước khi làm bài chẩn đoán."
        )
    course = await session.get(Course, course_id)
    if (
        course is None
        or course.status != CourseStatus.PUBLISHED.value
        or course.active_publication_id != profile.publication_id
    ):
        raise DiagnosticUnavailableError(
            "Onboarding đã cũ hoặc khóa học không còn được publish. Hãy cập nhật onboarding."
        )
    version_ids = [UUID(value) for value in profile.version_ids_json]
    concepts = list(
        (
            await session.scalars(
                select(CourseConcept)
                .join(CourseLesson, CourseLesson.id == CourseConcept.lesson_id)
                .join(CourseChapter, CourseChapter.id == CourseLesson.chapter_id)
                .where(CourseConcept.course_version_id.in_(version_ids))
                .order_by(
                    CourseChapter.order_index,
                    CourseLesson.order_index,
                    CourseConcept.order_index,
                )
            )
        ).all()
    )
    if len(concepts) < 2:
        raise DiagnosticUnavailableError(
            "Catalog chưa đủ concept để tạo bài chẩn đoán."
        )
    if not settings.llm_api_key or not settings.llm_model:
        raise DiagnosticUnavailableError(
            "Chưa cấu hình LLM để sinh bộ câu hỏi chẩn đoán đạt chuẩn."
        )
    concepts_by_lesson: dict[UUID, list[CourseConcept]] = {}
    for concept in concepts:
        concepts_by_lesson.setdefault(concept.lesson_id, []).append(concept)
    lessons = list(
        (
            await session.scalars(
                select(CourseLesson)
                .join(CourseChapter, CourseChapter.id == CourseLesson.chapter_id)
                .where(CourseLesson.id.in_(concepts_by_lesson))
                .order_by(CourseChapter.order_index, CourseLesson.order_index)
            )
        ).all()
    )
    lesson_contexts = []
    for lesson in lessons:
        chunks = list(
            (
                await session.scalars(
                    select(ContentChunk)
                    .where(ContentChunk.lesson_id == lesson.id)
                    .order_by(ContentChunk.chunk_index)
                    .limit(4)
                )
            ).all()
        )
        if not chunks:
            raise DiagnosticUnavailableError(
                f"Bài học '{lesson.title}' chưa có chunk nguồn."
            )
        lesson_contexts.append(
            {
                "lesson_id": str(lesson.id),
                "title": lesson.title,
                "summary": lesson.summary,
                "concepts": [
                    {
                        "id": str(concept.id),
                        "title": concept.title,
                        "description": concept.description,
                    }
                    for concept in concepts_by_lesson[lesson.id]
                ],
                "chunks": [
                    {
                        "id": str(chunk.id),
                        "source_label": chunk.source_label,
                        "source_text": chunk.text[:1600],
                    }
                    for chunk in chunks
                ],
            }
        )
    provider = OpenAICompatibleProvider(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    questions = await generate_diagnostic_questions(provider, lesson_contexts)
    for question in questions:
        question["id"] = str(uuid4())
    assessment_version = (
        int(
            await session.scalar(
                select(
                    func.coalesce(func.max(DiagnosticAssessment.assessment_version), 0)
                ).where(
                    DiagnosticAssessment.user_id == user.id,
                    DiagnosticAssessment.course_id == course_id,
                )
            )
            or 0
        )
        + 1
    )
    assessment = DiagnosticAssessment(
        user_id=user.id,
        course_id=course_id,
        publication_id=profile.publication_id,
        learner_course_profile_id=profile.id,
        profile_version=profile.profile_version,
        assessment_version=assessment_version,
        status="active",
        questions_json=questions,
    )
    session.add(assessment)
    await session.flush()
    now = datetime.now(UTC)
    attempt = DiagnosticAttempt(
        assessment_id=assessment.id,
        user_id=user.id,
        status="in_progress",
        answers_json=[],
        result_json={},
        started_at=now,
    )
    session.add(attempt)
    await session.commit()
    return {
        "attempt_id": attempt.id,
        "assessment_id": assessment.id,
        "course_id": course_id,
        "status": attempt.status,
        "assessment_version": assessment_version,
        "questions": [public_question(item) for item in questions],
        "started_at": now,
    }


async def submit_diagnostic(
    session: AsyncSession,
    user: User,
    attempt_id: UUID,
    answers: list[int],
    idempotency_key: str,
) -> dict:
    row = (
        await session.execute(
            select(DiagnosticAttempt, DiagnosticAssessment)
            .join(
                DiagnosticAssessment,
                DiagnosticAssessment.id == DiagnosticAttempt.assessment_id,
            )
            .where(
                DiagnosticAttempt.id == attempt_id, DiagnosticAttempt.user_id == user.id
            )
            .with_for_update()
        )
    ).one_or_none()
    if row is None:
        raise DiagnosticNotFoundError
    attempt, assessment = row
    if attempt.status == "submitted":
        if attempt.idempotency_key != idempotency_key:
            raise DiagnosticConflictError("Bài chẩn đoán đã được nộp.")
        return attempt.result_json
    questions = assessment.questions_json
    if len(answers) != len(questions) or any(
        answer < 0 or answer >= len(questions[index]["options"])
        for index, answer in enumerate(answers)
    ):
        raise DiagnosticUnavailableError(
            "Số lượng hoặc lựa chọn câu trả lời không hợp lệ."
        )
    learner = await ensure_learner_profile(session, user.id)
    now = datetime.now(UTC)
    results = []
    for question, answer in zip(questions, answers, strict=True):
        correct = answer == question["correct_index"]
        concept_id = UUID(question["concept_id"])
        mastery = await session.get(LearnerTopicMastery, (learner.id, str(concept_id)))
        if mastery is None:
            mastery = LearnerTopicMastery(
                learner_id=learner.id,
                topic_id=str(concept_id),
                mastery_score=0,
                confidence=0,
                repeated_errors=0,
                updated_at=now,
            )
            session.add(mastery)
        mastery.mastery_score = update_mastery(
            mastery.mastery_score,
            correct=correct,
            difficulty=0.5,
            hint_used=False,
            attempt_count=1,
        )
        mastery.confidence = round(min(1.0, mastery.confidence + 0.2), 4)
        mastery.repeated_errors = 0 if correct else mastery.repeated_errors + 1
        mastery.last_assessed_at = now
        mastery.updated_at = now
        session.add(
            LearnerEvidence(
                learner_id=learner.id,
                evidence_type="assessment",
                source=f"diagnostic:{attempt.id}",
                topic_id=str(concept_id),
                field_name="topic_mastery",
                value_json={"correct": correct, "selected_index": answer},
                confidence=mastery.confidence,
                created_at=now,
            )
        )
        results.append(
            {
                "concept_id": str(concept_id),
                "concept_title": question["concept_title"],
                "correct": correct,
                "selected_index": answer,
                "correct_index": question["correct_index"],
            }
        )
    correct_count = sum(1 for item in results if item["correct"])
    result = {
        "attempt_id": str(attempt.id),
        "status": "submitted",
        "score": round(correct_count / len(results) * 100, 2),
        "correct_count": correct_count,
        "question_count": len(results),
        "results": results,
        "submitted_at": now.isoformat(),
    }
    attempt.status = "submitted"
    attempt.answers_json = answers
    attempt.result_json = result
    attempt.score = result["score"]
    attempt.idempotency_key = idempotency_key
    attempt.submitted_at = now
    await session.commit()
    return result
