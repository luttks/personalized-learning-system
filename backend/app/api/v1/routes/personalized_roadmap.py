from datetime import UTC, date, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_student
from app.api.dependencies.rate_limit import rate_limit_by_user
from app.core.config import settings
from app.db.session import get_db_session
from app.models.exam_analysis_model import ExamAnalysis
from app.models.personalized_roadmap import PersonalizedRoadmap
from app.models.phase_assessment import PhaseAssessment
from app.models.roadmap_final_exam import RoadmapFinalExam
from app.models.user import User
from app.services.learner_service import get_learner_profile
from app.services.phase_assessment_service import (
    can_access_phase,
    get_or_create_status_list,
    grade_final_exam,
    grade_submission,
    is_phase_gated_open,
    public_questions,
)
from app.worker.tasks import (
    apply_phase_lockout_reinforcement_task,
    apply_phase_remediation_task,
    generate_final_exam_task,
    generate_phase_assessment_task,
)

router = APIRouter()

CurrentStudent = Annotated[User, Depends(get_current_student)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


class PersonalizedRoadmapResponse(BaseModel):
    id: UUID
    title: str
    overview: str
    total_weeks: int
    roadmap_data: dict[str, Any]
    created_at: str
    applied_at: str | None = None
    current_phase_number: int = 1
    exam_analysis_id: str | None = None
    source_filename: str | None = None

    @classmethod
    def from_orm(
        cls, roadmap: PersonalizedRoadmap, source_filename: str | None = None
    ) -> "PersonalizedRoadmapResponse":
        return cls(
            id=roadmap.id,
            title=roadmap.title,
            overview=roadmap.overview,
            total_weeks=roadmap.total_weeks,
            roadmap_data=roadmap.roadmap_data,
            created_at=roadmap.created_at.isoformat(),
            applied_at=roadmap.applied_at.isoformat() if roadmap.applied_at else None,
            current_phase_number=roadmap.current_phase_number,
            exam_analysis_id=str(roadmap.exam_analysis_id) if roadmap.exam_analysis_id else None,
            source_filename=source_filename,
        )


class PhaseAssessmentStatusResponse(BaseModel):
    phase_number: int
    status: str
    unlocked: bool
    is_current_phase: bool
    score_ratio: float | None
    pass_threshold: float
    attempts_count: int
    error_message: str | None = None
    retry_unlock_at: str | None = None


class PhaseAssessmentQuestionsResponse(BaseModel):
    phase_number: int
    status: str
    questions: list[dict[str, Any]] = []


class SubmitAnswerItem(BaseModel):
    question_id: int | str
    selected: str


class SubmitPhaseAssessmentRequest(BaseModel):
    answers: list[SubmitAnswerItem]


class SubmitPhaseAssessmentResponse(BaseModel):
    score_ratio: float
    passed: bool
    pass_threshold: float
    unlocked_next_phase: bool
    results: list[dict[str, Any]]
    status: str = "passed"  # passed | not_passed | locked_for_retry — frontend dùng để hiện đúng thông điệp


class PhaseRecapItem(BaseModel):
    phase_number: int
    title: str
    status: str
    score_ratio: float | None = None


class RoadmapFinalExamResponse(BaseModel):
    status: str
    questions: list[dict[str, Any]] = []
    phase_recap: list[PhaseRecapItem] = []
    score_ratio: float | None = None
    error_message: str | None = None


class SubmitFinalExamRequest(BaseModel):
    answers: list[SubmitAnswerItem]


class SubmitFinalExamResponse(BaseModel):
    score_ratio: float
    results: list[dict[str, Any]]
    phase_recap: list[PhaseRecapItem] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_owned_roadmap(
    session: AsyncSession, current_user: User, roadmap_id: UUID
) -> PersonalizedRoadmap:
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner profile not found")
    result = await session.execute(
        select(PersonalizedRoadmap).where(
            PersonalizedRoadmap.id == roadmap_id,
            PersonalizedRoadmap.learner_id == learner.id,
        )
    )
    roadmap = result.scalar_one_or_none()
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return roadmap


async def _get_owned_assessment(
    session: AsyncSession, roadmap: PersonalizedRoadmap, phase_number: int
) -> PhaseAssessment:
    result = await session.execute(
        select(PhaseAssessment).where(
            PhaseAssessment.roadmap_id == roadmap.id,
            PhaseAssessment.phase_number == phase_number,
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài kiểm tra cho giai đoạn này.")
    return assessment


def _enqueue_pending(assessments: list[PhaseAssessment]) -> None:
    """Bắn lại task sinh câu hỏi cho các dòng còn 'pending' hoặc 'failed' — bao gồm cả trường hợp
    tự tạo bù cho lộ trình cũ (chưa từng có PhaseAssessment), trường hợp hiếm request đầu bị crash
    giữa lúc commit dòng 'pending' và gọi .delay(), và trường hợp sinh lỗi tạm thời trước đó (cho
    người dùng một đường tự phục hồi mỗi khi họ mở lại trang, không cần endpoint "thử lại" riêng).
    Idempotent về mặt kết quả cuối cùng (task ghi đè đúng 'questions_json' của chính assessment đó)
    nên gọi lại không gây hại."""
    for a in assessments:
        if a.status in ("pending", "failed"):
            generate_phase_assessment_task.delay(str(a.id))


async def _build_phase_recap(session: AsyncSession, roadmap: PersonalizedRoadmap) -> list["PhaseRecapItem"]:
    """Tóm tắt điểm từng giai đoạn cho màn hình bài thi chốt hạ — đọc lại PhaseAssessment đã có
    sẵn, KHÔNG tốn thêm LLM call nào."""
    phases = roadmap.roadmap_data.get("phases", []) if roadmap.roadmap_data else []
    result = await session.execute(
        select(PhaseAssessment).where(PhaseAssessment.roadmap_id == roadmap.id)
    )
    by_phase = {a.phase_number: a for a in result.scalars().all()}
    recap = []
    for phase_number, phase in enumerate(phases, start=1):
        a = by_phase.get(phase_number)
        recap.append(PhaseRecapItem(
            phase_number=phase_number,
            title=phase.get("title", f"Giai đoạn {phase_number}"),
            status=a.status if a else "pending",
            score_ratio=a.score_ratio if a else None,
        ))
    return recap


def _public_final_exam_questions(exam: RoadmapFinalExam) -> list[dict]:
    """Câu hỏi trả cho client TRƯỚC khi nộp bài — bỏ 'correct'/'explanation', giữ 'phase_number'
    (không lộ đáp án, chỉ để FinalExamModal nhóm hiển thị theo giai đoạn)."""
    return [
        {
            "id": q.get("id"),
            "question": q.get("question"),
            "options": q.get("options"),
            "difficulty": q.get("difficulty"),
            "phase_number": q.get("phase_number"),
        }
        for q in exam.questions_json or []
    ]


def _reopen_if_due(assessment: PhaseAssessment) -> bool:
    """Tự phục hồi (self-heal) — mở lại 1 PhaseAssessment đang 'locked_for_retry' khi đã hết thời
    gian học lại (retry_unlock_at đã qua), tái dùng ĐÚNG cơ chế _enqueue_pending: chuyển về
    'pending', caller phải tự gọi _enqueue_pending sau đó để bắn task sinh câu hỏi MỚI (không tái
    dùng questions_json cũ — người học đã thấy). Reset remediation_applied_at=None để cho phép 1
    CHU KỲ KHÓA MỚI nếu lần làm lại này cũng rớt (guard idempotency trong
    _apply_phase_lockout_reinforcement_async chỉ chặn ĐÚNG chu kỳ hiện tại, không chặn vĩnh viễn).
    Trả về True nếu vừa mở, để caller biết cần commit."""
    if assessment.status != "locked_for_retry":
        return False
    if assessment.retry_unlock_at is not None and date.today() < assessment.retry_unlock_at:
        return False
    assessment.status = "pending"
    assessment.remediation_applied_at = None
    assessment.retry_unlock_at = None
    return True


# ---------------------------------------------------------------------------
# Roadmap CRUD (đã có từ trước)
# ---------------------------------------------------------------------------

@router.get("", response_model=list[PersonalizedRoadmapResponse])
async def get_my_roadmaps(
    session: DatabaseSession,
    current_user: CurrentStudent,
) -> Any:
    """Lấy danh sách các lộ trình AI đã lưu của học sinh."""
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        return []

    stmt = select(PersonalizedRoadmap).where(
        PersonalizedRoadmap.learner_id == learner.id
    ).order_by(PersonalizedRoadmap.created_at.desc())

    result = await session.execute(stmt)
    roadmaps = result.scalars().all()

    # Batch tra tên file gốc theo exam_analysis_id — tránh N+1 khi liệt kê nhiều lộ trình. Tên
    # file thật (không chỉ id) cần thiết để frontend xác định đúng cách xem trước (PDF/ảnh/...).
    analysis_ids = [r.exam_analysis_id for r in roadmaps if r.exam_analysis_id]
    filenames: dict[UUID, str] = {}
    if analysis_ids:
        fname_result = await session.execute(
            select(ExamAnalysis.id, ExamAnalysis.filename).where(ExamAnalysis.id.in_(analysis_ids))
        )
        filenames = {row.id: row.filename for row in fname_result}

    return [
        PersonalizedRoadmapResponse.from_orm(
            r, source_filename=filenames.get(r.exam_analysis_id) if r.exam_analysis_id else None
        )
        for r in roadmaps
    ]


@router.get("/{roadmap_id}", response_model=PersonalizedRoadmapResponse)
async def get_roadmap(
    roadmap_id: UUID,
    session: DatabaseSession,
    current_user: CurrentStudent,
) -> Any:
    """Xem chi tiết một lộ trình AI."""
    roadmap = await _get_owned_roadmap(session, current_user, roadmap_id)
    source_filename = None
    if roadmap.exam_analysis_id:
        analysis = await session.get(ExamAnalysis, roadmap.exam_analysis_id)
        source_filename = analysis.filename if analysis else None
    return PersonalizedRoadmapResponse.from_orm(roadmap, source_filename=source_filename)


@router.delete("/{roadmap_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_roadmap(
    roadmap_id: UUID,
    session: DatabaseSession,
    current_user: CurrentStudent,
) -> None:
    """Xóa một lộ trình AI."""
    roadmap = await _get_owned_roadmap(session, current_user, roadmap_id)
    await session.delete(roadmap)
    await session.commit()


# ---------------------------------------------------------------------------
# Áp dụng lộ trình — bật nhắc học hằng ngày qua email
# ---------------------------------------------------------------------------

@router.post("/{roadmap_id}/apply", response_model=PersonalizedRoadmapResponse)
async def apply_roadmap(
    roadmap_id: UUID,
    session: DatabaseSession,
    current_user: CurrentStudent,
) -> Any:
    """Đánh dấu lộ trình đang được áp dụng — bật nhắc học hằng ngày qua email. Idempotent: gọi
    lại khi đã áp dụng rồi không lỗi, không đổi applied_at gốc. Có thể áp dụng nhiều lộ trình
    cùng lúc (VD học song song nhiều môn) — email nhắc học được gộp thành 1 digest/ngày."""
    roadmap = await _get_owned_roadmap(session, current_user, roadmap_id)
    if roadmap.applied_at is None:
        roadmap.applied_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(roadmap)
    return PersonalizedRoadmapResponse.from_orm(roadmap)


# ---------------------------------------------------------------------------
# Bài kiểm tra cuối giai đoạn (phase gate)
# ---------------------------------------------------------------------------

@router.get("/{roadmap_id}/phases", response_model=list[PhaseAssessmentStatusResponse])
async def list_phase_assessments(
    roadmap_id: UUID,
    session: DatabaseSession,
    current_user: CurrentStudent,
) -> Any:
    """Trạng thái bài kiểm tra của từng giai đoạn. Tự tạo bù cho lộ trình tạo trước khi tính
    năng này tồn tại (self-heal), và tự bắn lại task sinh câu hỏi nếu phát hiện dòng còn kẹt ở
    'pending'."""
    roadmap = await _get_owned_roadmap(session, current_user, roadmap_id)
    assessments = await get_or_create_status_list(session, roadmap)
    for a in assessments:
        _reopen_if_due(a)
    await session.commit()
    _enqueue_pending(assessments)  # nhặt luôn các dòng vừa reopened (giờ status='pending')

    today = date.today()
    return [
        PhaseAssessmentStatusResponse(
            phase_number=a.phase_number,
            status=a.status,
            unlocked=(
                can_access_phase(a, roadmap)
                and a.status == "ready"
                and is_phase_gated_open(a, roadmap, today)
            ),
            is_current_phase=can_access_phase(a, roadmap),
            score_ratio=a.score_ratio,
            pass_threshold=a.pass_threshold,
            attempts_count=a.attempts_count,
            error_message=a.error_message,
            retry_unlock_at=a.retry_unlock_at.isoformat() if a.retry_unlock_at else None,
        )
        for a in assessments
    ]


@router.post(
    "/{roadmap_id}/phases/{phase_number}/unlock-early",
    response_model=PhaseAssessmentStatusResponse,
)
async def unlock_phase_assessment_early(
    roadmap_id: UUID,
    phase_number: int,
    session: DatabaseSession,
    current_user: CurrentStudent,
) -> Any:
    """Người học tự xác nhận đã học xong sớm giai đoạn hiện tại, không cần chờ tới ngày cuối lịch
    học mới được làm bài kiểm tra."""
    roadmap = await _get_owned_roadmap(session, current_user, roadmap_id)
    assessment = await _get_owned_assessment(session, roadmap, phase_number)
    if not can_access_phase(assessment, roadmap):
        raise HTTPException(status_code=409, detail="Chỉ có thể mở khóa giai đoạn hiện tại.")
    if assessment.manually_unlocked_at is None:
        assessment.manually_unlocked_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(assessment)

    return PhaseAssessmentStatusResponse(
        phase_number=assessment.phase_number,
        status=assessment.status,
        unlocked=assessment.status == "ready" and is_phase_gated_open(assessment, roadmap, date.today()),
        is_current_phase=True,
        score_ratio=assessment.score_ratio,
        pass_threshold=assessment.pass_threshold,
        attempts_count=assessment.attempts_count,
        error_message=assessment.error_message,
        retry_unlock_at=assessment.retry_unlock_at.isoformat() if assessment.retry_unlock_at else None,
    )


@router.get(
    "/{roadmap_id}/phases/{phase_number}/questions",
    response_model=PhaseAssessmentQuestionsResponse,
)
async def get_phase_assessment_questions(
    roadmap_id: UUID,
    phase_number: int,
    session: DatabaseSession,
    current_user: CurrentStudent,
) -> Any:
    """Lấy câu hỏi của bài kiểm tra — KHÔNG bao giờ trả 'correct'/'explanation' (chỉ lộ ra sau khi
    nộp bài). Luôn trả 200 kèm 'status' để frontend tự poll khi bài đang 'generating', thay vì
    phải bắt lỗi."""
    roadmap = await _get_owned_roadmap(session, current_user, roadmap_id)
    assessment = await _get_owned_assessment(session, roadmap, phase_number)

    if not can_access_phase(assessment, roadmap):
        raise HTTPException(status_code=409, detail="Bạn cần hoàn thành các giai đoạn trước đó trước.")

    if _reopen_if_due(assessment):
        await session.commit()

    if assessment.status == "locked_for_retry":
        raise HTTPException(
            status_code=403,
            detail=(
                f"Bạn đang trong giai đoạn học lại — bài kiểm tra sẽ mở lại vào "
                f"{assessment.retry_unlock_at.isoformat()}." if assessment.retry_unlock_at
                else "Bạn đang trong giai đoạn học lại — bài kiểm tra sẽ mở lại sau khi học đủ thời gian."
            ),
        )
    if not is_phase_gated_open(assessment, roadmap, date.today()):
        raise HTTPException(
            status_code=403,
            detail="Giai đoạn này chưa kết thúc. Hãy học hết lịch hoặc bấm 'học xong sớm' để mở khóa.",
        )

    _enqueue_pending([assessment])  # nhặt cả 'failed' lẫn 'pending' (VD vừa reopened ở trên)

    questions = public_questions(assessment) if assessment.status == "ready" else []
    return PhaseAssessmentQuestionsResponse(
        phase_number=assessment.phase_number,
        status=assessment.status,
        questions=questions,
    )


@router.post(
    "/{roadmap_id}/phases/{phase_number}/submit",
    response_model=SubmitPhaseAssessmentResponse,
    dependencies=[
        Depends(
            rate_limit_by_user(
                "phase_assessment_submit",
                max_requests=settings.phase_assessment_submit_rate_limit_max,
                window_seconds=settings.phase_assessment_submit_rate_limit_window_seconds,
            )
        )
    ],
)
async def submit_phase_assessment(
    roadmap_id: UUID,
    phase_number: int,
    payload: SubmitPhaseAssessmentRequest,
    session: DatabaseSession,
    current_user: CurrentStudent,
) -> Any:
    """Nộp bài kiểm tra cuối giai đoạn — chấm điểm phía server (không tin đáp án đúng do client
    gửi lên), cập nhật mastery theo từng chủ đề. Chỉ được nộp 1 LẦN DUY NHẤT cho mỗi giai đoạn (bảo
    vệ tự nhiên bởi check `assessment.status != "ready"` phía dưới — sau lần nộp đầu, status chuyển
    hẳn sang 'passed'/'not_passed'/'locked_for_retry', không bao giờ quay lại 'ready' nữa nên lần
    nộp thứ 2 luôn bị chặn ở đây). Đậu hay rớt đều mở khóa giai đoạn tiếp theo — rớt thì kích hoạt
    điều chỉnh (remediation) nội dung các giai đoạn còn lại thay vì chặn lại.

    NGOẠI LỆ DUY NHẤT: nếu giai đoạn TRƯỚC đó chưa đạt (not_passed) và người học đã bấm "mở khóa
    sớm" để bỏ qua thời gian học lại (is_risky_skip) rồi CŨNG rớt luôn giai đoạn này — KHÔNG mở khóa
    giai đoạn tiếp theo, thay vào đó khóa lại (status='locked_for_retry') và bắt học lại CHÍNH giai
    đoạn này (xem apply_phase_remediation(reinforce_same_phase=True))."""
    roadmap = await _get_owned_roadmap(session, current_user, roadmap_id)
    assessment = await _get_owned_assessment(session, roadmap, phase_number)
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner profile not found")

    if not can_access_phase(assessment, roadmap):
        raise HTTPException(status_code=409, detail="Bạn cần hoàn thành các giai đoạn trước đó trước.")
    if assessment.status != "ready":
        raise HTTPException(status_code=409, detail="Bài kiểm tra chưa sẵn sàng để nộp.")
    if not is_phase_gated_open(assessment, roadmap, date.today()):
        raise HTTPException(status_code=403, detail="Giai đoạn này chưa kết thúc.")

    previous_assessment = None
    if phase_number > 1:
        previous_assessment = await session.scalar(
            select(PhaseAssessment).where(
                PhaseAssessment.roadmap_id == roadmap.id,
                PhaseAssessment.phase_number == phase_number - 1,
            )
        )
    # Bất biến: previous_assessment KHÔNG BAO GIỜ là 'locked_for_retry' ở đây — trạng thái đó không
    # bao giờ mở khóa giai đoạn tiếp theo, nên không thể nào đang nộp bài giai đoạn phase_number
    # nếu giai đoạn trước còn khóa (can_access_phase đã chặn từ trước rồi).
    is_risky_skip = (
        assessment.manually_unlocked_at is not None
        and previous_assessment is not None
        and previous_assessment.status == "not_passed"
    )

    answers = {item.question_id: item.selected for item in payload.answers}
    result = await grade_submission(session, assessment, roadmap, learner, answers)

    if is_risky_skip and not result["passed"]:
        # Rớt SAU KHI bỏ qua giai đoạn trước đang hổng kiến thức — ngoại lệ CÓ CHỦ ĐÍCH, DUY NHẤT
        # với quy tắc "luôn tiến tới": hoàn tác việc grade_submission vừa mở khóa giai đoạn tiếp
        # theo, khóa lại và bắt học lại chính giai đoạn này.
        if result["unlocked_next_phase"]:
            roadmap.current_phase_number -= 1
        assessment.status = "locked_for_retry"
        result["unlocked_next_phase"] = False
        await session.commit()

        wrong_answers = [
            {k: r[k] for k in ("topic_ref", "question", "selected", "correct", "explanation")}
            for r in result["results"]
            if not r["is_correct"] and r.get("topic_ref")
        ]
        if wrong_answers:
            apply_phase_lockout_reinforcement_task.delay(
                str(roadmap.id), assessment.phase_number, str(assessment.id), wrong_answers
            )
        else:
            # Không có topic_ref hợp lệ nào để chẩn đoán — không có gì để task nền làm, mở khóa
            # ngay thay vì khóa vô thời hạn không có retry_unlock_at.
            assessment.status = "pending"
            await session.commit()
    elif not result["passed"]:
        # Không còn lượt làm lại (chỉ 1 lần/giai đoạn) nên KHÔNG cần sinh lại bộ câu hỏi mới cho
        # giai đoạn vừa rớt — assessment.status đã là 'not_passed', chung cuộc.
        #
        # attempts_count==1 + remediation_applied_at is None ở đây không còn phân biệt "lần rớt đầu
        # tiên" (giờ luôn đúng vì chỉ có 1 lần) — vẫn giữ làm chốt chặn phòng race condition (2
        # request nộp bài cùng lúc trước khi request đầu kịp commit đổi status khỏi 'ready').
        phases = roadmap.roadmap_data.get("phases", []) if roadmap.roadmap_data else []
        if (
            assessment.attempts_count == 1
            and assessment.remediation_applied_at is None
            and assessment.phase_number < len(phases)
        ):
            wrong_answers = [
                {k: r[k] for k in ("topic_ref", "question", "selected", "correct", "explanation")}
                for r in result["results"]
                if not r["is_correct"] and r.get("topic_ref")
            ]
            if wrong_answers:
                apply_phase_remediation_task.delay(
                    str(roadmap.id), assessment.phase_number, str(assessment.id), wrong_answers
                )

    result["status"] = assessment.status
    return SubmitPhaseAssessmentResponse(**result)


# ---------------------------------------------------------------------------
# Bài thi chốt hạ cuối lộ trình
# ---------------------------------------------------------------------------

@router.get("/{roadmap_id}/final-exam", response_model=RoadmapFinalExamResponse)
async def get_final_exam(
    roadmap_id: UUID,
    session: DatabaseSession,
    current_user: CurrentStudent,
) -> Any:
    """Lấy bài thi chốt hạ — chỉ mở khi đã đi qua HẾT mọi giai đoạn (đậu hay rớt đều tính là đã đi
    qua, đúng quy ước current_phase_number luôn tăng). Sinh LAZY (self-heal) giống PhaseAssessment:
    tạo dòng RoadmapFinalExam nếu chưa có, bắn lại task sinh câu hỏi nếu đang 'pending'/'failed'."""
    roadmap = await _get_owned_roadmap(session, current_user, roadmap_id)
    phases = roadmap.roadmap_data.get("phases", []) if roadmap.roadmap_data else []
    if not phases or roadmap.current_phase_number <= len(phases):
        raise HTTPException(status_code=409, detail="Bạn cần hoàn thành mọi giai đoạn trước khi làm bài thi chốt hạ.")

    exam = await session.scalar(
        select(RoadmapFinalExam).where(RoadmapFinalExam.roadmap_id == roadmap.id)
    )
    if exam is None:
        exam = RoadmapFinalExam(roadmap_id=roadmap.id, status="pending", questions_json=[])
        session.add(exam)
        await session.commit()
        await session.refresh(exam)

    if exam.status in ("pending", "failed"):
        generate_final_exam_task.delay(str(exam.id))

    phase_recap = await _build_phase_recap(session, roadmap)
    return RoadmapFinalExamResponse(
        status=exam.status,
        questions=_public_final_exam_questions(exam) if exam.status == "ready" else [],
        phase_recap=phase_recap,
        score_ratio=exam.score_ratio,
        error_message=exam.error_message,
    )


@router.post(
    "/{roadmap_id}/final-exam/submit",
    response_model=SubmitFinalExamResponse,
    dependencies=[
        Depends(
            rate_limit_by_user(
                "final_exam_submit",
                max_requests=settings.final_exam_submit_rate_limit_max,
                window_seconds=settings.final_exam_submit_rate_limit_window_seconds,
            )
        )
    ],
)
async def submit_final_exam(
    roadmap_id: UUID,
    payload: SubmitFinalExamRequest,
    session: DatabaseSession,
    current_user: CurrentStudent,
) -> Any:
    """Nộp bài thi chốt hạ — chỉ 1 LẦN DUY NHẤT (bảo vệ tự nhiên bởi check status != 'ready', sau
    khi nộp status chuyển hẳn sang 'completed'). Không có khái niệm đậu/rớt hay mở khóa gì thêm —
    đây thuần túy là báo cáo tổng kết cuối lộ trình."""
    roadmap = await _get_owned_roadmap(session, current_user, roadmap_id)
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner profile not found")

    exam = await session.scalar(
        select(RoadmapFinalExam).where(RoadmapFinalExam.roadmap_id == roadmap.id)
    )
    if exam is None:
        raise HTTPException(status_code=404, detail="Chưa có bài thi chốt hạ cho lộ trình này.")
    if exam.status != "ready":
        raise HTTPException(status_code=409, detail="Bài thi chưa sẵn sàng hoặc đã được nộp rồi.")

    answers = {item.question_id: item.selected for item in payload.answers}
    result = await grade_final_exam(session, exam, learner, answers)
    phase_recap = await _build_phase_recap(session, roadmap)

    return SubmitFinalExamResponse(
        score_ratio=result["score_ratio"],
        results=result["results"],
        phase_recap=phase_recap,
    )
