"""Quản lý vòng đời PhaseAssessment: tạo hàng loạt (rẻ, không gọi LLM) ngay lúc lộ trình được
tạo, kiểm tra điều kiện mở khóa, và chấm điểm khi người học nộp bài. Việc SINH câu hỏi (gọi LLM)
nằm ở app.worker.tasks — service này chỉ thao tác DB + logic chấm điểm."""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.learner import LearnerProfile
from app.models.personalized_roadmap import PersonalizedRoadmap
from app.models.phase_assessment import PhaseAssessment
from app.models.roadmap_final_exam import RoadmapFinalExam
from app.schemas.learner import LearningEventRequest
from app.services.learner_service import record_learning_event

_DIFFICULTY_SCORE: dict[str, float] = {"easy": 0.3, "medium": 0.6, "hard": 0.9}


async def create_pending_assessments_for_roadmap(
    session: AsyncSession,
    roadmap: PersonalizedRoadmap,
    phases: list[dict],
) -> list[PhaseAssessment]:
    """Tạo 1 dòng PhaseAssessment(status='pending') cho mỗi giai đoạn — thuần ghi DB, KHÔNG gọi
    LLM, để gọi ngay sau khi roadmap được commit mà không làm chậm response tạo lộ trình.
    Dùng enumerate(phases, start=1) làm phase_number chuẩn — KHÔNG dùng phase.get('phase_number')
    vì đó là số LLM tự đặt ở Lớp 1, không đảm bảo liên tục/duy nhất."""
    assessments: list[PhaseAssessment] = []
    for phase_number, _phase in enumerate(phases, start=1):
        assessment = PhaseAssessment(
            roadmap_id=roadmap.id,
            phase_number=phase_number,
            status="pending",
            pass_threshold=settings.phase_assessment_pass_threshold,
            questions_json=[],
        )
        session.add(assessment)
        assessments.append(assessment)
    await session.flush()
    return assessments


async def list_assessments_for_roadmap(
    session: AsyncSession, roadmap: PersonalizedRoadmap
) -> list[PhaseAssessment]:
    result = await session.execute(
        select(PhaseAssessment)
        .where(PhaseAssessment.roadmap_id == roadmap.id)
        .order_by(PhaseAssessment.phase_number)
    )
    return list(result.scalars().all())


async def get_or_create_status_list(
    session: AsyncSession, roadmap: PersonalizedRoadmap
) -> list[PhaseAssessment]:
    """Tự chữa cho lộ trình tạo TRƯỚC khi tính năng này tồn tại (chưa có dòng PhaseAssessment
    nào) — tạo bù các dòng 'pending' khi vừa truy cập lần đầu, để không cần script backfill
    riêng. KHÔNG tự động enqueue sinh câu hỏi ở đây — việc đó do route gọi rõ ràng, tránh import
    vòng (tasks.py import ngược lại service này)."""
    existing = await list_assessments_for_roadmap(session, roadmap)
    if existing:
        return existing
    phases = roadmap.roadmap_data.get("phases", []) if roadmap.roadmap_data else []
    if not phases:
        return []
    return await create_pending_assessments_for_roadmap(session, roadmap, phases)


def phase_end_date(roadmap_data: dict, phase_number: int) -> date | None:
    """Ngày học cuối cùng đã lên lịch cho giai đoạn — None nếu giai đoạn không tồn tại hoặc
    không có ngày nào (trường hợp hiếm khi lịch xếp bị lỗi hoàn toàn)."""
    phases = roadmap_data.get("phases", []) if roadmap_data else []
    if phase_number < 1 or phase_number > len(phases):
        return None
    days = phases[phase_number - 1].get("days", [])
    if not days:
        return None
    try:
        return date.fromisoformat(days[-1]["date"])
    except Exception:
        return None


def is_phase_gated_open(
    assessment: PhaseAssessment, roadmap: PersonalizedRoadmap, today: date
) -> bool:
    """Giai đoạn coi là 'đã xong' (được phép mở bài kiểm tra) khi lịch học đã tới ngày cuối cùng
    của giai đoạn HOẶC người học tự bấm mở khóa sớm. Không đòi hỏi tick từng ngày/từng chủ đề —
    bài kiểm tra chính là cửa chặn thật, không phải việc đánh dấu đã học."""
    if assessment.manually_unlocked_at is not None:
        return True
    end_date = phase_end_date(roadmap.roadmap_data, assessment.phase_number)
    return end_date is not None and today >= end_date


def can_access_phase(assessment: PhaseAssessment, roadmap: PersonalizedRoadmap) -> bool:
    """Chặn vượt cấp — chỉ được truy cập đúng giai đoạn hiện tại của lộ trình, kể cả khi giai
    đoạn sau đã lỡ sinh xong câu hỏi."""
    return assessment.phase_number == roadmap.current_phase_number


def public_questions(assessment: PhaseAssessment) -> list[dict]:
    """Câu hỏi trả cho client TRƯỚC khi nộp bài — bỏ 'correct'/'explanation' vì đây là cửa chặn
    thật (có động cơ để nhìn trộm đáp án), khác generate_diagnostic_quiz cũ vốn chấm phía client."""
    return [
        {
            "id": q.get("id"),
            "question": q.get("question"),
            "options": q.get("options"),
            "difficulty": q.get("difficulty"),
        }
        for q in assessment.questions_json or []
    ]


async def grade_submission(
    session: AsyncSession,
    assessment: PhaseAssessment,
    roadmap: PersonalizedRoadmap,
    learner: LearnerProfile,
    answers: dict[Any, str],
) -> dict[str, Any]:
    """Chấm theo questions_json lưu ở server (answers của client không được tin tưởng). Với mỗi
    câu, gọi record_learning_event() có sẵn để cập nhật LearnerTopicMastery theo topic_ref — tái
    dùng nguyên vẹn pipeline mastery đang dùng cho quiz/đề thi, không viết lại.

    Mỗi giai đoạn CHỈ được làm bài 1 lần duy nhất — không có cơ chế làm lại. current_phase_number
    LUÔN tăng sau khi chấm, dù đậu hay rớt (rớt mà vẫn khóa lại mãi mãi thì không bao giờ "hoàn
    thành toàn bộ" lộ trình được) — điểm khác biệt DUY NHẤT là rớt thì caller (route) kích hoạt
    apply_phase_remediation để điều chỉnh nội dung các giai đoạn còn lại, đậu thì giữ nguyên. Rớt
    là trạng thái CHUNG CUỘC (status='not_passed', không phải 'generating' như đậu vẫn dùng chờ làm
    lại trước đây) — questions_json KHÔNG bị xóa nữa vì không còn lượt làm lại nào để phòng học
    thuộc, giữ lại để người học xem lại bài đã làm bất cứ lúc nào."""
    questions = assessment.questions_json or []
    total = len(questions)
    correct_count = 0
    results: list[dict] = []

    for q in questions:
        qid = q.get("id")
        selected = answers.get(qid) or answers.get(str(qid))
        is_correct = bool(selected) and selected == q.get("correct")
        if is_correct:
            correct_count += 1

        difficulty = _DIFFICULTY_SCORE.get(str(q.get("difficulty", "medium")), 0.6)
        try:
            await record_learning_event(
                session,
                learner,
                LearningEventRequest(
                    topic_id=q.get("topic_ref") or f"phase_{assessment.phase_number}",
                    correct=is_correct,
                    difficulty=difficulty,
                    hint_used=False,
                    attempt_count=1,
                    source="phase_assessment",
                ),
            )
        except Exception:
            pass  # Không để lỗi ghi mastery làm hỏng việc chấm điểm/mở khóa giai đoạn.

        results.append({
            "question_id": qid,
            "question": q.get("question"),
            "selected": selected,
            "correct": q.get("correct"),
            "is_correct": is_correct,
            "explanation": q.get("explanation"),
            "topic_ref": q.get("topic_ref"),
        })

    score_ratio = round(correct_count / total, 4) if total else 0.0
    passed = score_ratio >= assessment.pass_threshold
    now = datetime.now(UTC)

    assessment.score_ratio = score_ratio
    assessment.attempts_count += 1
    assessment.last_attempted_at = now

    assessment.status = "passed" if passed else "not_passed"

    unlocked_next_phase = False
    if roadmap.current_phase_number == assessment.phase_number:
        roadmap.current_phase_number += 1
        unlocked_next_phase = True

    await session.commit()

    return {
        "score_ratio": score_ratio,
        "passed": passed,
        "pass_threshold": assessment.pass_threshold,
        "unlocked_next_phase": unlocked_next_phase,
        "results": results,
    }


async def grade_final_exam(
    session: AsyncSession,
    exam: RoadmapFinalExam,
    learner: LearnerProfile,
    answers: dict[Any, str],
) -> dict[str, Any]:
    """Chấm bài thi chốt hạ — mirror grade_submission ở trên (cùng cách chấm + ghi mastery từng
    câu qua record_learning_event) nhưng KHÔNG có khái niệm đậu/rớt hay mở khóa giai đoạn: đây là
    báo cáo tổng kết cuối lộ trình, chỉ 1 lần duy nhất (status chuyển hẳn sang 'completed')."""
    questions = exam.questions_json or []
    total = len(questions)
    correct_count = 0
    results: list[dict] = []

    for q in questions:
        qid = q.get("id")
        selected = answers.get(qid) or answers.get(str(qid))
        is_correct = bool(selected) and selected == q.get("correct")
        if is_correct:
            correct_count += 1

        difficulty = _DIFFICULTY_SCORE.get(str(q.get("difficulty", "medium")), 0.6)
        try:
            await record_learning_event(
                session,
                learner,
                LearningEventRequest(
                    topic_id=q.get("topic_ref") or "final_exam",
                    correct=is_correct,
                    difficulty=difficulty,
                    hint_used=False,
                    attempt_count=1,
                    source="final_exam",
                ),
            )
        except Exception:
            pass  # Không để lỗi ghi mastery làm hỏng việc chấm điểm.

        results.append({
            "question_id": qid,
            "question": q.get("question"),
            "selected": selected,
            "correct": q.get("correct"),
            "is_correct": is_correct,
            "explanation": q.get("explanation"),
            "topic_ref": q.get("topic_ref"),
            "phase_number": q.get("phase_number"),
        })

    score_ratio = round(correct_count / total, 4) if total else 0.0

    exam.score_ratio = score_ratio
    exam.attempts_count += 1
    exam.last_attempted_at = datetime.now(UTC)
    exam.status = "completed"
    await session.commit()

    return {
        "score_ratio": score_ratio,
        "results": results,
    }
