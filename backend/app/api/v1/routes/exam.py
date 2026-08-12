"""
Exam & Personalized Learning API routes.

Luồng 1 — Onboarding (Bắt đầu học mới):
  Step 1: POST /analyze-document  → AI detect môn học + gợi ý mục tiêu
  Step 2: POST /generate-quiz     → Sinh quiz BÁM SÁT nội dung tài liệu
  Step 3: POST /                  → Nộp quiz + lưu kết quả + update mastery

Luồng 2 — Post-Exam (Cải thiện sau thi):
  Step 1: POST /                  → Upload đề thi + điểm số → phân tích AI
"""
from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_student
from app.core.config import settings
from app.db.session import get_db_session
from app.models.exam_analysis_model import ExamAnalysis
from app.models.personalized_roadmap import PersonalizedRoadmap
from app.models.user import User
from app.services.exam_service import (
    ALL_SUPPORTED_EXTS,
    analyze_document_for_learning,
    generate_diagnostic_quiz,
    get_ai_recommendation_groq,
    run_full_exam_pipeline,
    crawl_resources_smart,
    generate_learning_roadmap,
    crawl_resources_per_phase,
)
from app.services.learner_service import (
    ensure_learner_profile,
    get_learner_profile,
    record_learning_event,
)
from app.services.student_profile_service import get_student_profile
from app.schemas.learner import LearningEventRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learners/me/exams", tags=["Personalized Learning"])

CurrentStudent = Annotated[User, Depends(get_current_student)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DocumentAnalysisResponse(BaseModel):
    """Kết quả phân tích tài liệu — bước đầu Luồng 1."""
    is_learning_doc: bool
    subject: str
    topics: list[str]
    suggested_goals: list[str]
    content_summary: str
    is_code_related: bool
    raw_text: str  # Dùng cho bước sinh quiz
    ocr_engine: str
    not_learning_message: str | None = None
    document_level: int | None = None
    level_gap: str | None = None  # "exceeds_user", "below_user", "match"
    warning_message: str | None = None


class QuizGenerateRequest(BaseModel):
    subject: str = Field(..., description="Môn học (từ analyze-document)")
    document_text: str = Field(..., description="Nội dung thực của file (raw_text từ analyze-document)")
    selected_goal: str = Field(..., description="Mục tiêu người dùng đã chọn/nhập")
    num_questions: int = Field(default=6, ge=3, le=10)


class QuizGenerateResponse(BaseModel):
    quiz: list[dict[str, Any]]
    topic_summary: str


class ParseExamResponse(BaseModel):
    header: str
    question_count: int
    formula_count: int
    questions: list[dict[str, Any]]
    raw_markdown: str
    ocr_engine: str
    filename: str


class ExamAnalysisSummary(BaseModel):
    id: str
    filename: str
    mode: str
    question_count: int
    formula_count: int
    ocr_engine: str
    exam_score: float | None
    exam_max_score: float | None
    mastery_updates_count: int
    created_at: datetime
    model_config = {"from_attributes": True}


class ExamAnalysisDetail(BaseModel):
    id: str
    filename: str
    mode: str
    question_count: int
    formula_count: int
    ocr_engine: str
    exam_score: float | None
    exam_max_score: float | None
    questions: list[dict[str, Any]]
    raw_markdown: str | None
    ai_recommendation: dict[str, Any]
    resources: dict[str, Any]
    mastery_updates: list[dict[str, Any]]
    roadmap: dict[str, Any] = {}
    phase_resources: dict[str, Any] = {}
    created_at: datetime
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_topics_from_recommendation(ai_rec: dict) -> list[tuple[str, str]]:
    topics = []
    for group_key in ("nhom_co_ban", "nhom_van_dung", "nhom_van_dung_cao"):
        group = ai_rec.get(group_key, {})
        for q in group.get("chi_tiet_tung_cau", []):
            topic = q.get("id_cau", "").strip()
            if topic:
                topics.append((topic, group_key))
    return topics


def _mastery_for_group(group_key: str, score_ratio: float | None) -> dict:
    base = {
        "nhom_co_ban": {"correct": True, "difficulty": 0.3, "hint_used": False, "attempt_count": 1},
        "nhom_van_dung": {"correct": False, "difficulty": 0.6, "hint_used": False, "attempt_count": 2},
        "nhom_van_dung_cao": {"correct": False, "difficulty": 0.9, "hint_used": True, "attempt_count": 3},
    }
    params = base.get(group_key, base["nhom_van_dung"]).copy()
    if score_ratio is not None and score_ratio < 0.5:
        params["correct"] = False
        params["attempt_count"] = max(params["attempt_count"], 2)
    return params


def _calculate_level(education_level: str | None, grade_level: int | None) -> int:
    """
    Chuyển đổi education_level và grade_level sang 1 thang đo duy nhất (1-19).
    Dưới đại học (1-12) -> 1-12.
    Đại học (năm 1-7) -> 13-19.
    """
    if not education_level or not grade_level:
        return 0
    if education_level == "under_university":
        return min(max(grade_level, 1), 12)
    elif education_level == "university":
        return 12 + min(max(grade_level, 1), 7)
    return 0


def _require_llm():
    if not settings.llm_api_key or not settings.llm_model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM chưa được cấu hình. Hãy kiểm tra LLM_API_KEY và LLM_MODEL trong .env.",
        )


# ---------------------------------------------------------------------------
# Luồng 1 — Step 1: Phân tích tài liệu (detect subject + gợi ý mục tiêu)
# ---------------------------------------------------------------------------

@router.post(
    "/analyze-document",
    response_model=DocumentAnalysisResponse,
    summary="[Luồng 1] Phân tích tài liệu: detect môn học + gợi ý mục tiêu",
)
async def analyze_document(
    _: CurrentStudent,
    session: DatabaseSession,
    file: Annotated[UploadFile, File(description="File tài liệu học (PDF/DOCX/TXT/ảnh)")],
) -> DocumentAnalysisResponse:
    """
    Bước 1 Luồng 1: Upload tài liệu + thông tin cá nhân.
    Hệ thống đọc file, detect môn học và trả về gợi ý mục tiêu.
    """
    current_user = _
    student_profile = await get_student_profile(session, current_user.id)
    
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALL_SUPPORTED_EXTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Định dạng '{ext}' không được hỗ trợ. Chấp nhận: JPG, PNG, PDF, DOCX, TXT.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File rỗng. Vui lòng chọn file khác.",
        )
    if len(file_bytes) > 20 * 1024 * 1024:  # 20MB limit for analysis
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File quá lớn (tối đa 20MB cho phân tích).",
        )

    try:
        result = await analyze_document_for_learning(
            file_bytes=file_bytes,
            filename=filename,
            gemini_api_keys=settings.gemini_api_keys,
            llm_api_keys=settings.llm_api_keys,
            llm_base_url=settings.llm_base_url,
            llm_model=settings.llm_model,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Document analysis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Lỗi phân tích tài liệu. Vui lòng thử lại.",
        ) from e

    # Level comparison
    doc_level = result.get("document_level")
    level_gap = "match"
    warning_message = None
    
    if doc_level and student_profile:
        try:
            doc_level_int = int(doc_level)
            user_level_int = _calculate_level(
                student_profile.education_level.value if hasattr(student_profile.education_level, 'value') else student_profile.education_level, 
                student_profile.grade_level
            )
            
            if user_level_int > 0:
                if doc_level_int > user_level_int:
                    level_gap = "exceeds_user"
                    warning_message = "Tài liệu này có vẻ vượt quá trình độ hiện tại của bạn. Bạn có muốn thử thách bản thân và tiếp tục không?"
                elif doc_level_int < user_level_int:
                    level_gap = "below_user"
                    warning_message = "Tài liệu này thấp hơn trình độ của bạn. Hệ thống sẽ tối ưu lộ trình theo hướng ôn tập nhanh."
        except Exception as err:
            logger.warning(f"Error comparing levels: {err}")

    return DocumentAnalysisResponse(
        **result,
        level_gap=level_gap,
        warning_message=warning_message
    )


# ---------------------------------------------------------------------------
# Luồng 1 — Step 2: Sinh Quick Quiz từ nội dung tài liệu thực
# ---------------------------------------------------------------------------

@router.post(
    "/generate-quiz",
    response_model=QuizGenerateResponse,
    summary="[Luồng 1] Sinh câu hỏi diagnostic bám sát nội dung tài liệu",
)
async def generate_quiz(
    _: CurrentStudent,
    session: DatabaseSession,
    payload: QuizGenerateRequest,
) -> QuizGenerateResponse:
    """
    Bước 2 Luồng 1: Sinh quiz từ raw_text thực của tài liệu (không phải user nhập).
    Quiz hoàn toàn bám sát nội dung tài liệu đã phân tích ở bước trước.
    """
    _require_llm()

    if not payload.document_text or len(payload.document_text.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nội dung tài liệu quá ngắn để sinh câu hỏi. Hãy thử file khác.",
        )

    current_user = _
    student_profile = await get_student_profile(session, current_user.id)
    edu_level = ""
    grade_level = ""
    if student_profile:
        edu_level = student_profile.education_level.value if hasattr(student_profile.education_level, 'value') else student_profile.education_level
        grade_level = student_profile.grade_level
    user_level_info = f"Trình độ học vấn: {edu_level}, Lớp/Năm: {grade_level}"

    result = await generate_diagnostic_quiz(
        subject=payload.subject,
        document_text=payload.document_text,
        selected_goal=payload.selected_goal,
        user_level_info=user_level_info,
        gemini_api_keys=settings.gemini_api_keys,
        llm_api_keys=settings.llm_api_keys,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,  # type: ignore
    )

    if not result.get("quiz"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không thể sinh câu hỏi từ tài liệu này. Hãy thử file khác.",
        )

    return QuizGenerateResponse(
        quiz=result.get("quiz", []),
        topic_summary=result.get("topic_summary", ""),
    )


# ---------------------------------------------------------------------------
# Luồng 1 — Step 3 / Luồng 2: Nộp kết quả + Lưu DB
# ---------------------------------------------------------------------------

@router.post(
    "/parse-exam",
    response_model=ParseExamResponse,
    summary="[Luồng 2] Parse đề thi, lấy danh sách câu hỏi và đoạn văn (header)",
)
async def parse_exam(
    current_user: CurrentStudent,
    session: DatabaseSession,
    file: Annotated[UploadFile, File()],
) -> ParseExamResponse:
    """OCR và Parse đề thi, trả về JSON."""
    _require_llm()
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALL_SUPPORTED_EXTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Định dạng '{ext}' không được hỗ trợ.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File rỗng.")

    try:
        from app.services.exam_service import ocr_and_parse
        result = await ocr_and_parse(file_bytes, filename, settings.gemini_api_keys)
        return ParseExamResponse(
            header=result.get("header", ""),
            question_count=result.get("question_count", 0),
            formula_count=result.get("formula_count", 0),
            questions=result.get("questions", []),
            raw_markdown=result.get("raw_markdown", ""),
            ocr_engine=result.get("ocr_engine", ""),
            filename=filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post(
    "",
    response_model=ExamAnalysisDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Upload và phân tích bài thi / nộp kết quả onboarding",
)
async def submit_exam(
    current_user: CurrentStudent,
    session: DatabaseSession,
    mode: Annotated[str, Form()] = "post_exam",
    file: Annotated[UploadFile | None, File()] = None,
    # Luồng 1 fields
    selected_goal: Annotated[str | None, Form()] = None,
    quick_quiz_results: Annotated[str | None, Form()] = None,
    subject: Annotated[str | None, Form()] = None,
    raw_text_for_crawl: Annotated[str | None, Form()] = None,
    is_code_related: Annotated[str, Form()] = "false",
    # Luồng 2 fields
    exam_score: Annotated[str | None, Form()] = None,
    exam_max_score: Annotated[str | None, Form()] = None,
    selected_questions: Annotated[str | None, Form()] = None,
    raw_text: Annotated[str | None, Form()] = None,
) -> ExamAnalysisDetail:
    """
    Nộp kết quả cuối cùng cho cả 2 luồng.
    - mode='onboarding': kèm quick_quiz_results và selected_goal
    - mode='post_exam':  kèm exam_score, exam_max_score, selected_questions, raw_text
    """
    filename = file.filename if file else "upload"
    ext = os.path.splitext(filename)[1].lower() if file else ""
    if file and ext not in ALL_SUPPORTED_EXTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Định dạng '{ext}' không được hỗ trợ.",
        )

    file_bytes = await file.read() if file else b""
    if file and not file_bytes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File rỗng.")

    # Parse numeric fields
    score: float | None = None
    max_score: float | None = None
    score_ratio: float | None = None
    try:
        if exam_score and exam_score.strip():
            score = float(exam_score)
        if exam_max_score and exam_max_score.strip():
            max_score = float(exam_max_score)
        if score is not None and max_score and max_score > 0:
            score_ratio = score / max_score
    except ValueError:
        pass

    code_related = is_code_related.lower() in ("true", "1", "yes")

    # Parse quiz results (Luồng 1)
    quiz_results_parsed: list[dict] = []
    if quick_quiz_results:
        try:
            quiz_results_parsed = json.loads(quick_quiz_results)
        except Exception:
            pass

    # Ensure learner profile
    learner = await ensure_learner_profile(session, current_user.id)

    # OCR + parse file (Luồng 1) hoặc parse từ raw_text (Luồng 2)
    parsed = {}
    resources = {}
    if mode == "onboarding":
        try:
            result = await run_full_exam_pipeline(
                file_bytes=file_bytes,
                filename=filename,
                gemini_api_keys=settings.gemini_api_keys,
            )
            parsed = result["parsed"]
            resources = result.get("resources", {})
            code_related = code_related or result.get("is_code_related", False)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
        except RuntimeError as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    else:
        # Luồng 2 (post_exam): parse từ raw_text
        from app.services.exam_service import parse_exam_questions
        if not raw_text:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Thiếu raw_text.")
        parsed = parse_exam_questions(raw_text)
        parsed["ocr_engine"] = "none"
        parsed["filename"] = filename

    # AI Recommendation (Groq)
    ai_rec: dict = {}
    if settings.llm_api_key and settings.llm_model:
        if mode == "post_exam" and selected_questions:
            try:
                selected_qs = json.loads(selected_questions)
            except Exception:
                selected_qs = []
            
            ai_rec = await get_ai_recommendation_groq(
                questions=selected_qs,  # Pass the list of dicts directly
                score_ratio=score_ratio,
                weak_areas=None,
                gemini_api_keys=settings.gemini_api_keys,
                llm_api_keys=settings.llm_api_keys,
                base_url=settings.llm_base_url,
                model=settings.llm_model,
            )
        elif mode == "onboarding":
            questions = parsed.get("questions", [])
            question_texts = [
                f"{q.get('id', '')}: {q.get('content', '')[:300]}"
                for q in questions
            ]
            if question_texts:
                ai_rec = await get_ai_recommendation_groq(
                    questions=question_texts,
                    score_ratio=score_ratio,
                    weak_areas=None,
                    gemini_api_keys=settings.gemini_api_keys,
                    llm_api_keys=settings.llm_api_keys,
                    base_url=settings.llm_base_url,
                    model=settings.llm_model,
                )

    # Nếu có raw_text từ luồng 1 (đã analyze trước đó), dùng để crawl chính xác hơn
    crawl_query = raw_text_for_crawl or parsed.get("raw_markdown", "")[:500]
    if crawl_query.strip() and not resources.get("youtube_tutorials"):
        try:
            resources = await crawl_resources_smart(crawl_query, is_code_related=code_related)
        except Exception as e:
            logger.warning(f"Resource crawl failed: {e}")

    # === SINH LỘ TRÌNH AI (Inline Roadmap) ===
    weak_topics: list[str] = []
    if ai_rec:
        for group_key in ("nhom_co_ban", "nhom_van_dung", "nhom_van_dung_cao"):
            for q in ai_rec.get(group_key, {}).get("chi_tiet_tung_cau", []):
                kn = q.get("kien_thuc_can_hoc", "").strip()
                if kn and kn not in weak_topics:
                    weak_topics.append(kn)

    # Fallback: dùng topics từ quiz answers nếu không có ai_rec
    if not weak_topics and quick_quiz_results:
        try:
            qr_list = json.loads(quick_quiz_results)
            weak_topics = list({qr.get("topic", "") for qr in qr_list if not qr.get("correct", True) and qr.get("topic")})
        except Exception:
            pass

    goal_for_roadmap = selected_goal or ai_rec.get("_goal", "Nắm vững kiến thức")
    minutes_pd = 60  # default

    inline_roadmap: dict = {}
    phase_resources: dict = {}
    try:
        inline_roadmap = await generate_learning_roadmap(
            subject=subject or "Học tập tổng quát",
            weak_topics=weak_topics,
            selected_goal=goal_for_roadmap,
            score_ratio=score_ratio,
            minutes_per_day=minutes_pd,
            quick_quiz_results_str=quick_quiz_results,
            gemini_api_keys=settings.gemini_api_keys,
            llm_api_keys=settings.llm_api_keys,
            llm_base_url=settings.llm_base_url,
            llm_model=settings.llm_model,
        )
        # Crawl tài nguyên theo từng giai đoạn
        phases = inline_roadmap.get("phases", [])
        if phases:
            phase_resources = await crawl_resources_per_phase(
                phases=phases,
                subject=subject or "học tập",
                is_code_related=code_related,
            )
    except Exception as e:
        logger.warning(f"Inline roadmap or phase crawl failed: {e}")

    # Cập nhật mastery từ AI recommendation (Luồng 2)
    mastery_updates: list[dict] = []
    if ai_rec:
        for topic_id, group_key in _extract_topics_from_recommendation(ai_rec):
            event_params = _mastery_for_group(group_key, score_ratio)
            try:
                mastery = await record_learning_event(
                    session,
                    learner,
                    LearningEventRequest(
                        topic_id=topic_id,
                        source=f"exam_{mode}",
                        **event_params,
                    ),
                )
                mastery_updates.append({
                    "topic_id": topic_id,
                    "group": group_key,
                    "mastery_score": mastery.mastery_score,
                    "confidence": mastery.confidence,
                })
            except Exception as e:
                logger.warning(f"Mastery update failed for topic '{topic_id}': {e}")

    # Cập nhật mastery từ quiz onboarding (Luồng 1)
    if quiz_results_parsed and mode == "onboarding":
        difficulty_map = {"easy": 0.3, "medium": 0.6, "hard": 0.9}
        for qr in quiz_results_parsed:
            topic = qr.get("topic", "").strip()
            correct = bool(qr.get("correct", False))
            difficulty = difficulty_map.get(qr.get("difficulty", "medium"), 0.6)
            if topic:
                try:
                    mastery = await record_learning_event(
                        session,
                        learner,
                        LearningEventRequest(
                            topic_id=topic,
                            source="onboarding_quiz",
                            correct=correct,
                            difficulty=difficulty,
                            hint_used=not correct,
                            attempt_count=1,
                        ),
                    )
                    mastery_updates.append({
                        "topic_id": topic,
                        "group": "quiz_diagnostic",
                        "mastery_score": mastery.mastery_score,
                        "confidence": mastery.confidence,
                    })
                except Exception as e:
                    logger.warning(f"Quiz mastery update failed: {e}")

    # Lưu DB
    analysis = ExamAnalysis(
        learner_id=learner.id,
        filename=filename,
        ocr_engine=parsed.get("ocr_engine", "unknown"),
        question_count=parsed.get("question_count", 0),
        formula_count=parsed.get("formula_count", 0),
        questions_json=parsed.get("questions", []),
        raw_markdown=parsed.get("raw_markdown"),
        ai_recommendation_json={
            **ai_rec,
            "_mode": mode,
            "_goal": selected_goal or "",
            "_roadmap": inline_roadmap,
        },
        resources_json=resources,
        mastery_updates_json=mastery_updates,
        created_at=datetime.now(UTC),
    )
    session.add(analysis)
    await session.commit()
    await session.refresh(analysis)

    # Save Roadmap to new table if generated
    if inline_roadmap:
        # Merge phase resources into the phases for unified storage
        phases_with_resources = inline_roadmap.get("phases", [])
        for p in phases_with_resources:
            phase_num = p.get("phase_number")
            p["resources"] = phase_resources.get(f"phase_{phase_num}", {})
            
        roadmap_record = PersonalizedRoadmap(
            learner_id=learner.id,
            exam_analysis_id=analysis.id,
            title=subject or "Học tập tổng quát",
            overview=inline_roadmap.get("overview", ""),
            total_weeks=inline_roadmap.get("total_weeks", 0),
            roadmap_data={"phases": phases_with_resources},
            created_at=datetime.now(UTC),
        )
        session.add(roadmap_record)
        await session.commit()

    return ExamAnalysisDetail(
        id=str(analysis.id),
        filename=analysis.filename,
        mode=mode,
        question_count=analysis.question_count,
        formula_count=analysis.formula_count,
        ocr_engine=analysis.ocr_engine,
        exam_score=score,
        exam_max_score=max_score,
        questions=analysis.questions_json,
        raw_markdown=analysis.raw_markdown,
        ai_recommendation=analysis.ai_recommendation_json,
        resources=analysis.resources_json,
        mastery_updates=analysis.mastery_updates_json,
        roadmap=inline_roadmap,
        phase_resources=phase_resources,
        created_at=analysis.created_at,
    )


# ---------------------------------------------------------------------------
# History endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ExamAnalysisSummary])
async def list_exam_analyses(
    current_user: CurrentStudent,
    session: DatabaseSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ExamAnalysisSummary]:
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        return []
    result = await session.execute(
        select(ExamAnalysis)
        .where(ExamAnalysis.learner_id == learner.id)
        .order_by(ExamAnalysis.created_at.desc())
        .limit(limit).offset(offset)
    )
    analyses = list(result.scalars().all())
    return [
        ExamAnalysisSummary(
            id=str(a.id),
            filename=a.filename,
            mode=a.ai_recommendation_json.get("_mode", "post_exam"),
            question_count=a.question_count,
            formula_count=a.formula_count,
            ocr_engine=a.ocr_engine,
            exam_score=None,
            exam_max_score=None,
            mastery_updates_count=len(a.mastery_updates_json),
            created_at=a.created_at,
        )
        for a in analyses
    ]


@router.get("/{analysis_id}", response_model=ExamAnalysisDetail)
async def get_exam_analysis(
    analysis_id: str,
    current_user: CurrentStudent,
    session: DatabaseSession,
) -> ExamAnalysisDetail:
    from uuid import UUID
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        raise HTTPException(status_code=404, detail="Chưa có learner profile.")
    try:
        uuid_id = UUID(analysis_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="ID không hợp lệ.")
    result = await session.execute(
        select(ExamAnalysis).where(
            ExamAnalysis.id == uuid_id,
            ExamAnalysis.learner_id == learner.id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Không tìm thấy phân tích.")
    return ExamAnalysisDetail(
        id=str(analysis.id),
        filename=analysis.filename,
        mode=analysis.ai_recommendation_json.get("_mode", "post_exam"),
        question_count=analysis.question_count,
        formula_count=analysis.formula_count,
        ocr_engine=analysis.ocr_engine,
        exam_score=None,
        exam_max_score=None,
        questions=analysis.questions_json,
        raw_markdown=analysis.raw_markdown,
        ai_recommendation=analysis.ai_recommendation_json,
        resources=analysis.resources_json,
        mastery_updates=analysis.mastery_updates_json,
        created_at=analysis.created_at,
    )
