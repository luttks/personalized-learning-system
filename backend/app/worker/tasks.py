import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime as _datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from celery.exceptions import Retry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="system.health_check_task",
)
def health_check_task(
    self: Any,
    message: str = "Celery hoạt động",
) -> dict[str, str]:
    return {
        "status": "completed",
        "message": message,
    }


# ---------------------------------------------------------------------------
# Cầu nối async cho Celery task — KHÔNG dùng lại app.db.session.engine (module-level, gắn với
# event loop của tiến trình FastAPI). Mỗi lần task chạy, asyncio.run() tạo một event loop MỚI;
# tái sử dụng engine cũ qua nhiều event loop khác nhau trong cùng tiến trình worker sẽ vỡ
# (RuntimeError: Future attached to a different loop), và Celery mặc định fork tiến trình
# (prefork pool) nên connection asyncpg tạo trước khi fork cũng không an toàn để dùng sau fork.
# Giải pháp: tạo engine riêng (NullPool, không giữ pool giữa các lần gọi) cho từng lần task chạy.
# ---------------------------------------------------------------------------

async def _run_with_fresh_session(
    coro_fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
) -> Any:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as session:
            return await coro_fn(session, *args, **kwargs)
    finally:
        await engine.dispose()


async def _generate_phase_assessment_async(session: AsyncSession, phase_assessment_id: str) -> dict:
    from app.models.personalized_roadmap import PersonalizedRoadmap
    from app.models.phase_assessment import PhaseAssessment
    from app.services.exam_analysis_chunk_service import retrieve_relevant_chunks_for_topics
    from app.services.exam_service import collect_phase_topics, generate_phase_assessment_quiz

    assessment = await session.get(PhaseAssessment, UUID(phase_assessment_id))
    if assessment is None:
        return {"status": "skipped", "reason": "assessment not found"}

    roadmap = await session.get(PersonalizedRoadmap, assessment.roadmap_id)
    if roadmap is None:
        assessment.status = "failed"
        assessment.error_message = "Roadmap không còn tồn tại."
        await session.commit()
        return {"status": "failed"}

    assessment.status = "generating"
    await session.commit()

    phases = roadmap.roadmap_data.get("phases", []) if roadmap.roadmap_data else []
    if assessment.phase_number < 1 or assessment.phase_number > len(phases):
        assessment.status = "failed"
        assessment.error_message = "Giai đoạn tương ứng không còn tồn tại trong lộ trình."
        await session.commit()
        return {"status": "failed"}

    phase = phases[assessment.phase_number - 1]
    phase_topics = collect_phase_topics(phase.get("days", []))
    if not phase_topics:
        assessment.status = "failed"
        assessment.error_message = "Giai đoạn này không có nội dung ngày học nào để ra đề."
        await session.commit()
        return {"status": "failed"}

    topic_queries = {
        t["title"]: t["title"] + (f" — {t['why']}" if t.get("why") else "") for t in phase_topics
    }
    topic_context = await retrieve_relevant_chunks_for_topics(
        session, roadmap.exam_analysis_id, topic_queries, top_k=3
    )

    result = await generate_phase_assessment_quiz(
        subject=roadmap.title,
        phase_title=phase.get("title", ""),
        phase_topics=phase_topics,
        num_questions=settings.phase_assessment_num_questions,
        gemini_api_keys=settings.gemini_api_keys,
        llm_api_keys=settings.llm_api_keys,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model or "",
        topic_context=topic_context,
    )
    questions = result.get("questions", [])
    if not questions:
        assessment.status = "failed"
        assessment.error_message = "Sinh câu hỏi thất bại (AI không trả về câu hỏi hợp lệ)."
        await session.commit()
        return {"status": "failed"}

    assessment.questions_json = questions
    assessment.status = "ready"
    await session.commit()
    return {"status": "ready", "question_count": len(questions)}


async def _mark_assessment_failed_async(
    session: AsyncSession, phase_assessment_id: str, error_message: str
) -> None:
    from app.models.phase_assessment import PhaseAssessment

    assessment = await session.get(PhaseAssessment, UUID(phase_assessment_id))
    if assessment is None:
        return
    assessment.status = "failed"
    assessment.error_message = error_message[:500]
    await session.commit()


@celery_app.task(bind=True, name="phase_assessment.generate", max_retries=3, default_retry_delay=30)
def generate_phase_assessment_task(self: Any, phase_assessment_id: str) -> dict:
    """Sinh bộ câu hỏi cho MỘT giai đoạn — chạy hoàn toàn trong tiến trình worker, KHÔNG nằm
    trên đường request tạo lộ trình. Mỗi giai đoạn một task riêng nên các giai đoạn tự sinh
    song song với nhau. Lỗi tạm thời (LLM/mạng) được Celery tự retry; hết lượt retry mới đánh
    dấu 'failed' để người dùng có thể tự bấm thử lại từ giao diện."""
    try:
        return asyncio.run(_run_with_fresh_session(_generate_phase_assessment_async, phase_assessment_id))
    except Exception as exc:
        logger.warning(f"generate_phase_assessment_task lỗi cho {phase_assessment_id}: {exc}")
        try:
            raise self.retry(exc=exc)
        except Retry:
            # Celery đã lên lịch retry thành công — để nguyên cho Celery tự requeue.
            raise
        except Exception:
            # Hết lượt retry: vì đã truyền exc=exc ở trên, Celery.retry() KHÔNG raise
            # MaxRetriesExceededError như tài liệu ngụ ý — mà raise thẳng lại exc gốc (xem
            # celery/app/task.py: `if exc: raise_with_context(exc)`). Bất kỳ exception nào
            # khác Retry lọt tới đây tức là đã hết lượt, phải đánh dấu 'failed'.
            asyncio.run(
                _run_with_fresh_session(_mark_assessment_failed_async, phase_assessment_id, str(exc))
            )
            raise


async def _index_exam_analysis_chunks_async(session: AsyncSession, exam_analysis_id: str) -> dict:
    from sqlalchemy import delete

    from app.models.exam_analysis_chunk import ExamAnalysisChunk
    from app.models.exam_analysis_model import ExamAnalysis
    from app.services.exam_service import chunk_document_text
    from app.core.llm_client import get_llm_client

    analysis = await session.get(ExamAnalysis, UUID(exam_analysis_id))
    if analysis is None or not analysis.raw_markdown or not analysis.raw_markdown.strip():
        return {"status": "skipped", "reason": "no raw_markdown"}

    chunks = chunk_document_text(analysis.raw_markdown)
    if not chunks:
        return {"status": "skipped", "reason": "chunking produced 0 chunks"}

    vectors = await get_llm_client().embed_texts(chunks, task_type="RETRIEVAL_DOCUMENT")
    if len(vectors) != len(chunks):
        raise RuntimeError(f"Số vector ({len(vectors)}) không khớp số chunk ({len(chunks)}).")

    # Idempotent qua các lần Celery tự retry — xóa index cũ của CHÍNH exam_analysis này trước khi
    # ghi mới, tránh trùng lặp/lệch dữ liệu nếu lần trước bị lỗi giữa chừng.
    await session.execute(
        delete(ExamAnalysisChunk).where(ExamAnalysisChunk.exam_analysis_id == analysis.id)
    )
    for i, (text, vec) in enumerate(zip(chunks, vectors)):
        session.add(ExamAnalysisChunk(exam_analysis_id=analysis.id, chunk_index=i, text=text, embedding=vec))
    await session.commit()
    return {"status": "indexed", "chunk_count": len(chunks)}


@celery_app.task(bind=True, name="exam_analysis.index_chunks", max_retries=3, default_retry_delay=30)
def index_exam_analysis_chunks_task(self: Any, exam_analysis_id: str) -> dict:
    """Chunk + embed + lưu ExamAnalysisChunk (RAG) — chạy NGẦM ngay sau khi ExamAnalysis được
    commit (routes/exam.py: submit_exam), KHÔNG chặn request. Best-effort: nếu thất bại hoàn toàn
    sau hết lượt retry, sinh câu hỏi kiểm tra sau đó tự động rơi về KHÔNG có ngữ cảnh tài liệu gốc
    như trước khi có RAG (xem exam_analysis_chunk_service.retrieve_relevant_chunks_for_topics) —
    không cần cơ chế 'gỡ kẹt' riêng như tính năng khóa giai đoạn."""
    try:
        return asyncio.run(_run_with_fresh_session(_index_exam_analysis_chunks_async, exam_analysis_id))
    except Exception as exc:
        logger.warning(f"index_exam_analysis_chunks_task lỗi cho {exam_analysis_id}: {exc}")
        try:
            raise self.retry(exc=exc)
        except Retry:
            raise
        except Exception:
            logger.error(
                f"index_exam_analysis_chunks_task THẤT BẠI HOÀN TOÀN sau hết lượt retry cho "
                f"exam_analysis {exam_analysis_id} — sinh câu hỏi liên quan sẽ không có ngữ cảnh "
                f"tài liệu gốc: {exc}",
                exc_info=True,
            )
            raise


async def _apply_phase_remediation_async(
    session: AsyncSession,
    roadmap_id: str,
    failed_phase_number: int,
    assessment_id: str,
    wrong_answers: list[dict],
) -> dict:
    import copy
    from datetime import UTC, datetime

    from app.models.personalized_roadmap import PersonalizedRoadmap
    from app.models.phase_assessment import PhaseAssessment
    from app.services.exam_service import apply_phase_remediation

    assessment = await session.get(PhaseAssessment, UUID(assessment_id))
    if assessment is None:
        return {"status": "skipped", "reason": "assessment not found"}
    if assessment.remediation_applied_at is not None:
        # Đã áp dụng rồi (task tự retry/redeliver, hoặc 2 request nộp bài chạy đồng thời) — không
        # áp dụng lại lần 2, tránh chèn/chỉnh chồng chéo nhiều lần.
        return {"status": "skipped", "reason": "already applied"}

    roadmap = await session.get(PersonalizedRoadmap, UUID(roadmap_id))
    if roadmap is None or not roadmap.roadmap_data:
        return {"status": "skipped", "reason": "roadmap not found"}

    phases = roadmap.roadmap_data.get("phases", [])
    meta = roadmap.roadmap_data.get("_schedule_meta") or {}
    # Lộ trình tạo TRƯỚC khi có _schedule_meta (dòng này thêm sau) — dùng đúng mặc định exam.py
    # đang dùng khi không có giá trị người dùng chọn, để hành vi nhất quán.
    minutes_per_day = meta.get("minutes_per_day") or 60
    days_per_week = meta.get("days_per_week") or 7
    schedule_pattern = meta.get("schedule_pattern") or "consecutive"
    deadline = meta.get("deadline")
    study_depth_mode = meta.get("study_depth_mode")
    reading_time = meta.get("reading_time")
    selected_goal = meta.get("selected_goal") or "Nắm vững kiến thức"

    try:
        new_phases = await apply_phase_remediation(
            phases, roadmap.title, selected_goal,
            minutes_per_day, days_per_week, schedule_pattern, deadline,
            study_depth_mode, reading_time,
            failed_phase_number, wrong_answers,
            gemini_api_keys=settings.gemini_api_keys, llm_api_keys=settings.llm_api_keys,
            llm_base_url=settings.llm_base_url, llm_model=settings.llm_model or "",
        )
    except Exception as e:
        logger.error(f"apply_phase_remediation lỗi cho roadmap {roadmap_id}: {e}", exc_info=True)
        raise

    if not new_phases:
        # Không có gì để chỉnh (VD giai đoạn vừa rớt là giai đoạn cuối) — KHÔNG coi là lỗi, chỉ là
        # không áp dụng. Không set remediation_applied_at để lần rớt sau (nếu logic gọi thay đổi)
        # vẫn có thể thử lại — nhưng route chỉ gọi task này 1 lần cho lần rớt đầu nên không lặp lại.
        return {"status": "skipped", "reason": "nothing to adjust"}

    # Bắt buộc deepcopy + gán lại TOÀN BỘ roadmap_data — xem cảnh báo trên PersonalizedRoadmap.roadmap_data.
    new_data = copy.deepcopy(roadmap.roadmap_data)
    new_data["phases"] = new_phases
    roadmap.roadmap_data = new_data
    assessment.remediation_applied_at = datetime.now(UTC)

    # Bộ câu hỏi cũ của các giai đoạn phía sau giờ tham chiếu nội dung đã đổi — reset để sinh lại.
    # Dùng "pending" (không phải "generating") để cơ chế tự phục hồi có sẵn (_enqueue_pending trong
    # personalized_roadmap.py) tự bắn lại task nếu bước .delay() dưới đây lỡ thất bại.
    touched = (await session.execute(
        select(PhaseAssessment).where(
            PhaseAssessment.roadmap_id == roadmap.id,
            PhaseAssessment.phase_number > failed_phase_number,
        )
    )).scalars().all()
    for pa in touched:
        pa.status = "pending"
        pa.questions_json = []

    await session.commit()

    for pa in touched:
        generate_phase_assessment_task.delay(str(pa.id))

    return {"status": "applied", "phases_touched": len(touched)}


@celery_app.task(bind=True, name="phase_assessment.apply_remediation", max_retries=3, default_retry_delay=30)
def apply_phase_remediation_task(
    self: Any, roadmap_id: str, failed_phase_number: int, assessment_id: str, wrong_answers: list[dict]
) -> dict:
    """Sau khi học viên RỚT LẦN ĐẦU 1 giai đoạn: chèn nội dung củng cố vào giai đoạn kế tiếp và
    xếp lại lịch phần còn lại để vẫn kịp hạn mục tiêu (xem apply_phase_remediation trong
    exam_service.py). Chạy nền, KHÔNG chặn luồng nộp bài/nhận kết quả của người học — nếu thất bại
    hoàn toàn (hết lượt retry), người học vẫn không bị ảnh hưởng gì đến việc làm lại bài kiểm tra
    giai đoạn vừa rớt (2 luồng độc lập, xem submit_phase_assessment)."""
    try:
        return asyncio.run(_run_with_fresh_session(
            _apply_phase_remediation_async, roadmap_id, failed_phase_number, assessment_id, wrong_answers
        ))
    except Exception as exc:
        logger.warning(f"apply_phase_remediation_task lỗi cho assessment {assessment_id}: {exc}")
        try:
            raise self.retry(exc=exc)
        except Retry:
            raise
        except Exception:
            # Hết lượt retry — đây là tính năng best-effort, KHÔNG có cột status riêng để đánh dấu
            # thất bại (không cần chặn gì cả), nhưng PHẢI log rõ ràng ở mức error (không phải
            # warning) để không lặp lại bài học "lỗi sinh lộ trình mất tích hoàn toàn" đã gặp trong
            # phiên này — nếu không log rõ, sẽ không có cách nào biết remediation đã âm thầm thất bại.
            logger.error(
                f"apply_phase_remediation_task THẤT BẠI HOÀN TOÀN sau hết lượt retry cho "
                f"assessment {assessment_id}, roadmap {roadmap_id}, giai đoạn {failed_phase_number}: {exc}",
                exc_info=True,
            )
            raise


async def _unlock_stuck_assessment_async(session: AsyncSession, phase_assessment_id: str) -> None:
    """Van an toàn: mở khóa NGAY một PhaseAssessment đang 'locked_for_retry' về lại 'pending' (không
    gia hạn thêm), dùng khi apply_phase_lockout_reinforcement_task thất bại hoàn toàn hoặc
    apply_phase_remediation không tạo được nội dung củng cố nào — KHÔNG để người học kẹt vĩnh viễn
    vì không có retry_unlock_at nào được set."""
    from app.models.phase_assessment import PhaseAssessment

    assessment = await session.get(PhaseAssessment, UUID(phase_assessment_id))
    if assessment is None:
        return
    assessment.status = "pending"
    assessment.remediation_applied_at = None
    assessment.retry_unlock_at = None
    await session.commit()


async def _apply_phase_lockout_reinforcement_async(
    session: AsyncSession,
    roadmap_id: str,
    locked_phase_number: int,
    assessment_id: str,
    wrong_answers: list[dict],
) -> dict:
    import copy
    from datetime import UTC, date, datetime

    from app.models.personalized_roadmap import PersonalizedRoadmap
    from app.models.phase_assessment import PhaseAssessment
    from app.services.exam_service import apply_phase_remediation

    assessment = await session.get(PhaseAssessment, UUID(assessment_id))
    if assessment is None:
        return {"status": "skipped", "reason": "assessment not found"}
    if assessment.remediation_applied_at is not None:
        # Idempotency guard cho ĐÚNG chu kỳ khóa hiện tại — KHÁC guard remediation bình thường vì
        # 1 giai đoạn có thể trải qua NHIỀU chu kỳ khóa/học lại (rớt lại sau khi mở khóa); mỗi chu
        # kỳ mới, _reopen_if_due đã reset remediation_applied_at=None nên guard này vẫn đúng cho
        # từng chu kỳ riêng biệt, không chặn nhầm chu kỳ sau.
        return {"status": "skipped", "reason": "already applied this cycle"}

    roadmap = await session.get(PersonalizedRoadmap, UUID(roadmap_id))
    if roadmap is None or not roadmap.roadmap_data:
        return {"status": "skipped", "reason": "roadmap not found"}

    phases = roadmap.roadmap_data.get("phases", [])
    meta = roadmap.roadmap_data.get("_schedule_meta") or {}
    minutes_per_day = meta.get("minutes_per_day") or 60
    days_per_week = meta.get("days_per_week") or 7
    schedule_pattern = meta.get("schedule_pattern") or "consecutive"
    deadline = meta.get("deadline")
    study_depth_mode = meta.get("study_depth_mode")
    reading_time = meta.get("reading_time")
    selected_goal = meta.get("selected_goal") or "Nắm vững kiến thức"

    try:
        new_phases = await apply_phase_remediation(
            phases, roadmap.title, selected_goal,
            minutes_per_day, days_per_week, schedule_pattern, deadline,
            study_depth_mode, reading_time,
            locked_phase_number, wrong_answers,
            gemini_api_keys=settings.gemini_api_keys, llm_api_keys=settings.llm_api_keys,
            llm_base_url=settings.llm_base_url, llm_model=settings.llm_model or "",
            reinforce_same_phase=True,
        )
    except Exception as e:
        logger.error(
            f"apply_phase_remediation(reinforce_same_phase=True) lỗi cho roadmap {roadmap_id}: {e}",
            exc_info=True,
        )
        raise

    if not new_phases:
        # Van an toàn: LLM lỗi hết retry / không có topic_ref hợp lệ — KHÔNG để người học kẹt vĩnh
        # viễn không có retry_unlock_at nào cả, mở khóa lại ngay (không gia hạn thêm thời gian).
        await _unlock_stuck_assessment_async(session, assessment_id)
        return {"status": "unlocked_immediately", "reason": "nothing to reinforce"}

    # Bắt buộc deepcopy + gán lại TOÀN BỘ roadmap_data — xem cảnh báo trên PersonalizedRoadmap.roadmap_data.
    new_data = copy.deepcopy(roadmap.roadmap_data)
    new_data["phases"] = new_phases
    roadmap.roadmap_data = new_data

    locked_phase_days = new_phases[locked_phase_number - 1].get("days", [])
    assessment.remediation_applied_at = datetime.now(UTC)
    assessment.retry_unlock_at = (
        date.fromisoformat(locked_phase_days[-1]["date"]) if locked_phase_days else date.today()
    )
    # Câu hỏi cũ người học đã thấy khi rớt — không tái dùng, phải sinh mới khi mở lại (giống hệt lý
    # do questions_json bị xóa trong luồng remediation bình thường trước đây, giờ đã bỏ vì không còn
    # làm lại — nhưng ở ĐÂY thì có làm lại thật nên vẫn cần xóa).
    assessment.questions_json = []

    touched = (await session.execute(
        select(PhaseAssessment).where(
            PhaseAssessment.roadmap_id == roadmap.id,
            PhaseAssessment.phase_number > locked_phase_number,
        )
    )).scalars().all()
    for pa in touched:
        pa.status = "pending"
        pa.questions_json = []

    await session.commit()

    for pa in touched:
        generate_phase_assessment_task.delay(str(pa.id))

    return {
        "status": "locked",
        "retry_unlock_at": assessment.retry_unlock_at.isoformat(),
        "phases_touched": len(touched),
    }


@celery_app.task(bind=True, name="phase_assessment.apply_lockout_reinforcement", max_retries=3, default_retry_delay=30)
def apply_phase_lockout_reinforcement_task(
    self: Any, roadmap_id: str, locked_phase_number: int, assessment_id: str, wrong_answers: list[dict]
) -> dict:
    """Sau khi học viên bỏ qua giai đoạn TRƯỚC đang hổng kiến thức (mở khóa sớm) rồi CŨNG rớt luôn
    giai đoạn này: chèn nội dung củng cố + xếp lại lịch DÀI HƠN cho CHÍNH giai đoạn vừa rớt (không
    chuyển tiếp sang giai đoạn sau — xem apply_phase_remediation(reinforce_same_phase=True) trong
    exam_service.py), khóa giai đoạn sau lại cho tới khi retry_unlock_at qua (xem _reopen_if_due
    trong routes/personalized_roadmap.py). Nếu thất bại hoàn toàn sau hết lượt retry: van an toàn
    PHẢI tự mở khóa ngay, không để người học kẹt vĩnh viễn."""
    try:
        return asyncio.run(_run_with_fresh_session(
            _apply_phase_lockout_reinforcement_async, roadmap_id, locked_phase_number, assessment_id, wrong_answers
        ))
    except Exception as exc:
        logger.warning(f"apply_phase_lockout_reinforcement_task lỗi cho assessment {assessment_id}: {exc}")
        try:
            raise self.retry(exc=exc)
        except Retry:
            raise
        except Exception:
            logger.error(
                f"apply_phase_lockout_reinforcement_task THẤT BẠI HOÀN TOÀN sau hết lượt retry cho "
                f"assessment {assessment_id}, roadmap {roadmap_id}, giai đoạn {locked_phase_number} — "
                f"MỞ KHÓA NGAY để không kẹt người học: {exc}",
                exc_info=True,
            )
            try:
                asyncio.run(_run_with_fresh_session(_unlock_stuck_assessment_async, assessment_id))
            except Exception:
                logger.error(
                    f"Van an toàn mở khóa khẩn cấp cũng thất bại cho assessment {assessment_id}",
                    exc_info=True,
                )
            raise


async def _generate_final_exam_async(session: AsyncSession, final_exam_id: str) -> dict:
    from app.models.personalized_roadmap import PersonalizedRoadmap
    from app.models.roadmap_final_exam import RoadmapFinalExam
    from app.services.exam_analysis_chunk_service import retrieve_relevant_chunks_for_topics
    from app.services.exam_service import (
        _final_exam_blueprint,
        collect_all_roadmap_topics,
        generate_final_exam_quiz,
    )

    exam = await session.get(RoadmapFinalExam, UUID(final_exam_id))
    if exam is None:
        return {"status": "skipped", "reason": "final exam not found"}

    roadmap = await session.get(PersonalizedRoadmap, exam.roadmap_id)
    if roadmap is None:
        exam.status = "failed"
        exam.error_message = "Roadmap không còn tồn tại."
        await session.commit()
        return {"status": "failed"}

    exam.status = "generating"
    await session.commit()

    phases = roadmap.roadmap_data.get("phases", []) if roadmap.roadmap_data else []
    topics = collect_all_roadmap_topics(phases)
    if not topics:
        exam.status = "failed"
        exam.error_message = "Lộ trình không có nội dung nào để ra đề."
        await session.commit()
        return {"status": "failed"}

    blueprint = _final_exam_blueprint(topics, settings.final_exam_num_questions)

    topic_queries = {
        t["title"]: t["title"] + (f" — {t['why']}" if t.get("why") else "") for t in topics
    }
    topic_context = await retrieve_relevant_chunks_for_topics(
        session, roadmap.exam_analysis_id, topic_queries, top_k=2
    )

    result = await generate_final_exam_quiz(
        subject=roadmap.title, blueprint=blueprint,
        gemini_api_keys=settings.gemini_api_keys, llm_api_keys=settings.llm_api_keys,
        llm_base_url=settings.llm_base_url, llm_model=settings.llm_model or "",
        topic_context=topic_context,
    )
    questions = result.get("questions", [])
    if not questions:
        exam.status = "failed"
        exam.error_message = "Sinh câu hỏi thất bại (AI không trả về câu hỏi hợp lệ)."
        await session.commit()
        return {"status": "failed"}

    exam.questions_json = questions
    exam.status = "ready"
    await session.commit()
    return {"status": "ready", "question_count": len(questions)}


async def _mark_final_exam_failed_async(session: AsyncSession, final_exam_id: str, error_message: str) -> None:
    from app.models.roadmap_final_exam import RoadmapFinalExam

    exam = await session.get(RoadmapFinalExam, UUID(final_exam_id))
    if exam is None:
        return
    exam.status = "failed"
    exam.error_message = error_message[:500]
    await session.commit()


@celery_app.task(bind=True, name="final_exam.generate", max_retries=3, default_retry_delay=30)
def generate_final_exam_task(self: Any, final_exam_id: str) -> dict:
    """Sinh đề thi chốt hạ — chạy LAZY khi người học lần đầu mở màn hình này (KHÁC PhaseAssessment,
    không sinh sẵn hàng loạt lúc tạo lộ trình, vì roadmap_data có thể bị remediation sửa đổi bất cứ
    lúc nào trước khi hoàn thành toàn bộ — sinh sẵn dễ lệch nội dung thực tế đã học)."""
    try:
        return asyncio.run(_run_with_fresh_session(_generate_final_exam_async, final_exam_id))
    except Exception as exc:
        logger.warning(f"generate_final_exam_task lỗi cho {final_exam_id}: {exc}")
        try:
            raise self.retry(exc=exc)
        except Retry:
            raise
        except Exception:
            asyncio.run(_run_with_fresh_session(_mark_final_exam_failed_async, final_exam_id, str(exc)))
            raise


async def _send_daily_reminders_async(session: AsyncSession) -> dict:
    from app.models.personalized_roadmap import PersonalizedRoadmap
    from app.models.phase_assessment import PhaseAssessment
    from app.models.learner import LearnerProfile
    from app.models.user import User
    from app.services.email_service import send_daily_reminder_digest

    # Giờ nhắc học chạy theo lịch crontab timezone Asia/Ho_Chi_Minh (celery_app.py) — dùng đúng
    # ngày theo múi giờ đó khi so khớp lịch học, không phụ thuộc múi giờ hệ điều hành container.
    today = _datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()

    result = await session.execute(
        select(PersonalizedRoadmap).where(
            PersonalizedRoadmap.applied_at.is_not(None),
            (PersonalizedRoadmap.last_reminder_sent_at.is_(None))
            | (PersonalizedRoadmap.last_reminder_sent_at < today),
        )
    )
    roadmaps = list(result.scalars().all())
    if not roadmaps:
        return {"learners_notified": 0, "roadmaps_checked": 0}

    # Gom theo learner để gửi ĐÚNG 1 email/người/ngày dù học nhiều môn song song.
    items_by_learner: dict[UUID, list[dict]] = {}
    for roadmap in roadmaps:
        # Đánh dấu đã xử lý ngày hôm nay ngay cả khi hôm nay không có buổi học — tránh beat chạy
        # trùng trong ngày quét lại nhiều lần.
        roadmap.last_reminder_sent_at = today

        phases = roadmap.roadmap_data.get("phases", []) if roadmap.roadmap_data else []
        phase_idx = roadmap.current_phase_number - 1
        if phase_idx < 0 or phase_idx >= len(phases):
            continue
        phase = phases[phase_idx]
        today_day = next((d for d in phase.get("days", []) if d.get("date") == today.isoformat()), None)
        if today_day is None:
            continue

        assessment_result = await session.execute(
            select(PhaseAssessment).where(
                PhaseAssessment.roadmap_id == roadmap.id,
                PhaseAssessment.phase_number == roadmap.current_phase_number,
            )
        )
        assessment = assessment_result.scalar_one_or_none()

        items_by_learner.setdefault(roadmap.learner_id, []).append({
            "roadmap_title": roadmap.title,
            "phase_title": phase.get("title", ""),
            "topics": [t.get("title", "") for t in today_day.get("topics", [])],
            "total_minutes": today_day.get("total_minutes", 0),
            "assessment_ready": bool(assessment and assessment.status == "ready"),
        })

    await session.commit()

    if not items_by_learner:
        return {"learners_notified": 0, "roadmaps_checked": len(roadmaps)}

    learner_result = await session.execute(
        select(LearnerProfile, User)
        .join(User, User.id == LearnerProfile.user_id)
        .where(LearnerProfile.id.in_(items_by_learner.keys()))
    )
    notified = 0
    for learner, user in learner_result.all():
        items = items_by_learner.get(learner.id)
        if not items:
            continue
        await send_daily_reminder_digest(user.email, user.full_name, items)
        notified += 1

    return {"learners_notified": notified, "roadmaps_checked": len(roadmaps)}


@celery_app.task(bind=True, name="reminders.send_daily_digest")
def send_daily_reminders_task(self: Any) -> dict:
    return asyncio.run(_run_with_fresh_session(_send_daily_reminders_async))


async def _send_stuck_learner_reminders_async(session: AsyncSession) -> dict:
    from app.models.personalized_roadmap import PersonalizedRoadmap
    from app.models.phase_assessment import PhaseAssessment
    from app.models.learner import LearnerProfile
    from app.models.user import User
    from app.services.email_service import send_stuck_learner_reminder

    # Buổi nhắc THỨ 2 trong ngày, RIÊNG cho người học đang bị khóa 1 giai đoạn để học lại — độc lập
    # hoàn toàn với _send_daily_reminders_async (task khác, dedup khác last_boost_reminder_sent_at
    # thay vì last_reminder_sent_at của roadmap).
    today = _datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()

    result = await session.execute(
        select(PhaseAssessment, PersonalizedRoadmap)
        .join(PersonalizedRoadmap, PhaseAssessment.roadmap_id == PersonalizedRoadmap.id)
        .where(
            PhaseAssessment.status == "locked_for_retry",
            PhaseAssessment.phase_number == PersonalizedRoadmap.current_phase_number,
            PersonalizedRoadmap.applied_at.is_not(None),
            (PhaseAssessment.last_boost_reminder_sent_at.is_(None))
            | (PhaseAssessment.last_boost_reminder_sent_at < today),
        )
    )
    rows = result.all()
    if not rows:
        return {"learners_notified": 0, "assessments_checked": 0}

    items_by_learner: dict[UUID, list[dict]] = {}
    for assessment, roadmap in rows:
        # Đánh dấu đã xử lý hôm nay ngay cả khi không tìm được tiêu đề giai đoạn — tránh beat chạy
        # trùng trong ngày gửi lặp lại (cùng lý do với last_reminder_sent_at của digest thường).
        assessment.last_boost_reminder_sent_at = today

        phases = roadmap.roadmap_data.get("phases", []) if roadmap.roadmap_data else []
        phase_idx = assessment.phase_number - 1
        phase_title = phases[phase_idx].get("title", "") if 0 <= phase_idx < len(phases) else ""

        items_by_learner.setdefault(roadmap.learner_id, []).append({
            "roadmap_title": roadmap.title,
            "phase_title": phase_title,
            "retry_unlock_at": assessment.retry_unlock_at.isoformat() if assessment.retry_unlock_at else None,
        })

    await session.commit()

    learner_result = await session.execute(
        select(LearnerProfile, User)
        .join(User, User.id == LearnerProfile.user_id)
        .where(LearnerProfile.id.in_(items_by_learner.keys()))
    )
    notified = 0
    for learner, user in learner_result.all():
        items = items_by_learner.get(learner.id)
        if not items:
            continue
        await send_stuck_learner_reminder(user.email, user.full_name, items)
        notified += 1

    return {"learners_notified": notified, "assessments_checked": len(rows)}


@celery_app.task(bind=True, name="reminders.send_stuck_learner_boost")
def send_stuck_learner_reminders_task(self: Any) -> dict:
    return asyncio.run(_run_with_fresh_session(_send_stuck_learner_reminders_async))
