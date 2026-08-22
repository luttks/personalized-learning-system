"""
Exam & Personalized Learning API routes.

Luồng 1 — Onboarding (Bắt đầu học mới):
  Step 1: POST /analyze-document  → AI detect môn học + gợi ý mục tiêu (nhiều file)
  Step 2: POST /generate-quiz     → Sinh quiz BÁM SÁT nội dung tài liệu (có skip nếu đã có mastery)
  Step 3: POST /                  → Nộp quiz + lưu kết quả + update mastery

Luồng 2 — Post-Exam (Cải thiện sau thi):
  Step 1: POST /parse-exam        → Parse đề thi, lấy danh sách câu hỏi
  Step 2: POST /                  → Upload + điểm số + câu hỏi + mức độ → phân tích AI + crawl lời giải

Quản lý lịch sử:
  GET /subjects?mode=onboarding|post_exam       → Danh sách môn/đề cũ
  GET /subjects/{subject}/analyses              → Danh sách analyses theo môn
  GET /                                         → Danh sách tất cả analyses
  GET /{id}                                     → Chi tiết 1 analysis
"""
from __future__ import annotations

import json
import logging
import os
from datetime import UTC, date, datetime
from uuid import UUID
from typing import Annotated, Any, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_student
from app.core.config import settings
from app.db.session import get_db_session
from app.models.content import Course, CourseStatus
from app.models.exam_analysis_model import ExamAnalysis
from app.models.personalized_roadmap import PersonalizedRoadmap
from app.models.user import User
from app.services.exam_service import (
    ALL_SUPPORTED_EXTS,
    analyze_competency_evidence,
    analyze_document_for_learning,
    analyze_multiple_documents,
    generate_diagnostic_quiz,
    get_ai_recommendation_groq,
    run_full_exam_pipeline,
    crawl_resources_smart,
    generate_learning_roadmap,
    crawl_resources_per_phase,
    crawl_solution_for_question,
    generate_solution_hint,
    save_upload_file,
)
from app.services.learner_service import (
    ensure_learner_profile,
    get_learner_profile,
    record_learning_event,
)
from app.services.student_profile_service import get_student_profile
from app.services.temp_upload_service import (
    discard_temp_file,
    read_temp_file,
    save_temp_file,
)
from app.schemas.learner import LearningEventRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learners/me/exams", tags=["Personalized Learning"])

CurrentStudent = Annotated[User, Depends(get_current_student)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ReadingTimeEstimate(BaseModel):
    """Ước lượng thời gian đọc tài liệu — tính bằng code (đếm từ), KHÔNG dùng LLM, chưa cá nhân hóa."""
    word_count: int
    survey_minutes_min: int
    survey_minutes_max: int
    general_minutes_min: int
    general_minutes_max: int
    technical_minutes_min: int
    technical_minutes_max: int
    deep_study_minutes_min: int
    deep_study_minutes_max: int


class DocumentAnalysisResponse(BaseModel):
    """Kết quả phân tích tài liệu — bước đầu Luồng 1."""
    is_learning_doc: bool
    subject: str
    subjects: list[str] = []              # Danh sách môn khi upload nhiều file
    multi_subject_detected: bool = False  # True nếu phát hiện > 1 môn khác nhau
    topics: list[str]
    suggested_goals: list[str]
    content_summary: str
    is_code_related: bool
    raw_text: str  # Dùng cho bước sinh quiz
    ocr_engine: str
    not_learning_message: str | None = None
    has_clear_structure: bool = True  # False nếu tài liệu không chia chương/mục rõ ràng
    structure_reason: str | None = None  # Lý do khi has_clear_structure=False
    reading_time: ReadingTimeEstimate | None = None
    temp_file_id: str | None = None  # Tham chiếu file đã lưu tạm — dùng khi nộp bài cuối cùng
    document_level: int | None = None
    level_gap: str | None = None  # "exceeds_user", "below_user", "match"
    warning_message: str | None = None
    # Kiểm tra lịch sử
    has_existing_mastery: bool = False    # Đã có mastery cho môn này
    existing_roadmap_title: str | None = None  # Tên lộ trình đang học nếu trùng
    # Phát hiện file trùng lập
    duplicate_file: bool = False           # True nếu file này đã tồn tại trong kho
    existing_analysis_id: str | None = None  # ID phân tích trước có cùng hash
    duplicate_subject: str | None = None   # Tên môn của phân tích trước
    duplicate_created_at: str | None = None  # Ngày tạo phân tích trước


class CompetencyEvidenceResponse(BaseModel):
    """Kết quả xác thực tài liệu minh chứng năng lực (Luồng 1 — Nhóm 2)."""
    is_competency_evidence: bool
    evidence_type: str  # "transcript" | "certificate" | "exam" | "other"
    reason: str | None = None


class QuizGenerateRequest(BaseModel):
    subject: str = Field(..., description="Môn học (từ analyze-document)")
    document_text: str = Field(..., description="Nội dung thực của file (raw_text từ analyze-document)")
    selected_goal: str = Field(..., description="Mục tiêu người dùng đã chọn/nhập")
    num_questions: int = Field(default=6, ge=3, le=10)


class QuizGenerateResponse(BaseModel):
    quiz: list[dict[str, Any]]
    topic_summary: str
    quiz_skipped: bool = False  # True nếu đã có mastery, không cần quiz


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
    subject: str | None
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
    subject: str | None
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
    roadmap_error: str | None = None  # Ghi nhận lỗi nếu sinh lộ trình thất bại
    # Post-exam: kết quả theo từng phương án
    solution_results: list[dict[str, Any]] = []  # Per-question: hint, traps, tips, crawled_solutions
    created_at: datetime
    model_config = {"from_attributes": True}


class SubjectSummary(BaseModel):
    subject: str
    mode: str
    count: int
    last_used: datetime


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


async def _check_duplicate_file(
    session: AsyncSession,
    learner_id,
    file_hash: str,
) -> tuple[bool, str | None, str | None, str | None]:
    """
    Kiểm tra xem file (theo SHA-256) đã tồn tại trong kho của learner này chưa.
    Trả về (is_duplicate, analysis_id, subject, created_at_str).
    """
    try:
        result = await session.execute(
            select(ExamAnalysis).where(
                ExamAnalysis.learner_id == learner_id,
                ExamAnalysis.file_hash == file_hash,
            ).order_by(ExamAnalysis.created_at.desc()).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            subj = existing.subject or existing.ai_recommendation_json.get("_goal", "Không xác định") or "Không xác định"
            return True, str(existing.id), subj, existing.created_at.isoformat()
        return False, None, None, None
    except Exception as e:
        logger.warning(f"Duplicate file check failed: {e}")
        return False, None, None, None


async def _check_existing_mastery(session: AsyncSession, learner_id, subject: str) -> tuple[bool, str | None]:
    """
    Kiểm tra xem người dùng đã có mastery data cho môn này chưa.
    Trả về (has_mastery, roadmap_title_if_exists).
    """
    try:
        import re as _re
        # Tìm analyses cùng môn (so sánh subject không phân biệt case)
        result = await session.execute(
            select(ExamAnalysis).where(
                ExamAnalysis.learner_id == learner_id,
            ).order_by(ExamAnalysis.created_at.desc()).limit(50)
        )
        analyses = list(result.scalars().all())

        norm_subj = _re.sub(r"[\d\s\W]+", "", subject.lower())[:15]
        for a in analyses:
            a_subj = (a.subject or a.ai_recommendation_json.get("_goal", ""))
            norm_a = _re.sub(r"[\d\s\W]+", "", a_subj.lower())[:15]
            if norm_a == norm_subj and len(a.mastery_updates_json) > 0:
                # Kiểm tra có roadmap không
                roadmap_result = await session.execute(
                    select(PersonalizedRoadmap).where(
                        PersonalizedRoadmap.learner_id == learner_id,
                        PersonalizedRoadmap.exam_analysis_id == a.id,
                    ).limit(1)
                )
                roadmap = roadmap_result.scalar_one_or_none()
                roadmap_title = roadmap.title if roadmap else None
                return True, roadmap_title
        return False, None
    except Exception as e:
        logger.warning(f"Check existing mastery failed: {e}")
        return False, None


# ---------------------------------------------------------------------------
# Luồng 1 — Step 1: Phân tích tài liệu (detect subject + gợi ý mục tiêu)
# Hỗ trợ nhiều file
# ---------------------------------------------------------------------------

@router.post(
    "/analyze-document",
    response_model=DocumentAnalysisResponse,
    summary="[Luồng 1] Phân tích tài liệu: detect môn học + gợi ý mục tiêu (hỗ trợ nhiều file)",
)
async def analyze_document(
    current_user: CurrentStudent,
    session: DatabaseSession,
    files: Annotated[List[UploadFile], File(description="File tài liệu học (PDF/DOCX/TXT/ảnh) — có thể upload nhiều file")],
) -> DocumentAnalysisResponse:
    """
    Bước 1 Luồng 1: Upload tài liệu.
    Hệ thống đọc file(s), detect môn học, trả về gợi ý mục tiêu + kiểm tra lịch sử.
    """
    student_profile = await get_student_profile(session, current_user.id)

    if not files:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Vui lòng chọn ít nhất 1 file.")

    all_file_data: list[tuple[bytes, str]] = []
    all_hashes: list[str] = []
    for file in files:
        filename = file.filename or "upload"
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALL_SUPPORTED_EXTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Định dạng '{ext}' không được hỗ trợ. Chấp nhận: JPG, PNG, PDF, DOCX, TXT.",
            )
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"File '{filename}' rỗng.")
        if len(file_bytes) > 100 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"File '{filename}' quá lớn (tối đa 100MB).")
        # Tính SHA-256 hash của file để kiểm tra trùng lập
        import hashlib
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        all_hashes.append(file_hash)
        all_file_data.append((file_bytes, filename))

    # Lưu tạm file đầu tiên (file thực sự được dùng khi nộp bài cuối cùng) — để nếu người dùng
    # chuyển sang trang khác rồi quay lại, không cần chọn lại file.
    temp_file_id = save_temp_file(all_file_data[0][0], all_file_data[0][1], str(current_user.id))

    try:
        if len(all_file_data) == 1:
            # Single file — dùng hàm cũ
            result = await analyze_document_for_learning(
                file_bytes=all_file_data[0][0],
                filename=all_file_data[0][1],
                gemini_api_keys=settings.gemini_api_keys,
                llm_api_keys=settings.llm_api_keys,
                llm_base_url=settings.llm_base_url,
                llm_model=settings.llm_model,
            )
            subjects = [result.get("subject", "")] if result.get("subject") else []
            multi_subject_detected = False
            subject = result.get("subject", "Tài liệu học tập")
            raw_text = result.get("raw_text", "")
            topics = result.get("topics", [])
            suggested_goals = result.get("suggested_goals", [])
            content_summary = result.get("content_summary", "")
            is_code_related = result.get("is_code_related", False)
            ocr_engine = result.get("ocr_engine", "")
            is_learning_doc = result.get("is_learning_doc", True)
            not_learning_message = result.get("not_learning_message")
            document_level = result.get("document_level")
            has_clear_structure = result.get("has_clear_structure", True)
            structure_reason = result.get("structure_reason")
            reading_time = result.get("reading_time")
        else:
            # Multi file
            merged = await analyze_multiple_documents(
                files=all_file_data,
                gemini_api_keys=settings.gemini_api_keys,
                llm_api_keys=settings.llm_api_keys,
                llm_base_url=settings.llm_base_url,
                llm_model=settings.llm_model,
            )
            subject = merged["merged_subject"]
            subjects = merged["subjects"]
            multi_subject_detected = merged["multi_subject_detected"]
            raw_text = merged["merged_raw_text"]
            topics = merged["merged_topics"]
            suggested_goals = merged["merged_goals"]
            content_summary = f"Đã phân tích {len(all_file_data)} tài liệu: {', '.join(subjects)}"
            is_code_related = merged["is_code_related"]
            ocr_engine = merged["ocr_engine"]
            is_learning_doc = True
            not_learning_message = None
            document_level = None
            has_clear_structure = merged.get("has_clear_structure", True)
            structure_reason = merged.get("structure_reason")
            reading_time = merged.get("reading_time")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Document analysis error: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Lỗi phân tích tài liệu. Vui lòng thử lại.") from e

    # Level comparison (single file only)
    doc_level = document_level
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

    # Kiểm tra lịch sử mastery
    has_existing_mastery = False
    existing_roadmap_title = None
    learner = await get_learner_profile(session, current_user.id)
    if learner and is_learning_doc and subject:
        has_existing_mastery, existing_roadmap_title = await _check_existing_mastery(session, learner.id, subject)

    # Kiểm tra file trùng lập theo hash (chỉ khi upload 1 file và đã xác nhận là tài liệu học)
    duplicate_file = False
    existing_analysis_id = None
    duplicate_subject = None
    duplicate_created_at = None
    if learner and all_hashes and is_learning_doc:
        primary_hash = all_hashes[0]  # Kiểm tra file đầu tiên
        duplicate_file, existing_analysis_id, duplicate_subject, duplicate_created_at = await _check_duplicate_file(
            session, learner.id, primary_hash
        )

    return DocumentAnalysisResponse(
        is_learning_doc=is_learning_doc,
        subject=subject,
        subjects=subjects,
        multi_subject_detected=multi_subject_detected,
        topics=topics,
        suggested_goals=suggested_goals,
        content_summary=content_summary,
        is_code_related=is_code_related,
        raw_text=raw_text,
        ocr_engine=ocr_engine,
        not_learning_message=not_learning_message,
        has_clear_structure=has_clear_structure,
        temp_file_id=temp_file_id,
        structure_reason=structure_reason,
        reading_time=ReadingTimeEstimate(**reading_time) if reading_time else None,
        document_level=document_level,
        level_gap=level_gap,
        warning_message=warning_message,
        has_existing_mastery=has_existing_mastery,
        existing_roadmap_title=existing_roadmap_title,
        duplicate_file=duplicate_file,
        existing_analysis_id=existing_analysis_id,
        duplicate_subject=duplicate_subject,
        duplicate_created_at=duplicate_created_at,
    )


# ---------------------------------------------------------------------------
# Luồng 1 — Nhóm 2: Xác thực tài liệu minh chứng năng lực (bảng điểm/chứng chỉ/bài kiểm tra)
# ---------------------------------------------------------------------------

@router.post(
    "/analyze-competency-evidence",
    response_model=CompetencyEvidenceResponse,
    summary="[Luồng 1] Xác thực tài liệu minh chứng năng lực do người dùng upload",
)
async def analyze_competency_evidence_route(
    current_user: CurrentStudent,
    file: Annotated[UploadFile, File(description="Bảng điểm / chứng chỉ / bài kiểm tra đã làm")],
) -> CompetencyEvidenceResponse:
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALL_SUPPORTED_EXTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Định dạng '{ext}' không được hỗ trợ. Chấp nhận: JPG, PNG, PDF, DOCX, TXT.",
        )
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File rỗng.")
    if len(file_bytes) > 100 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File quá lớn (tối đa 100MB).")

    try:
        result = await analyze_competency_evidence(
            file_bytes=file_bytes,
            filename=filename,
            gemini_api_keys=settings.gemini_api_keys,
            llm_api_keys=settings.llm_api_keys,
            llm_base_url=settings.llm_base_url,
            llm_model=settings.llm_model,
        )
    except Exception as e:
        logger.error(f"Competency evidence analysis error: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Lỗi xác thực tài liệu. Vui lòng thử lại.") from e

    return CompetencyEvidenceResponse(
        is_competency_evidence=result["is_competency_evidence"],
        evidence_type=result["evidence_type"],
        reason=result["reason"],
    )


# ---------------------------------------------------------------------------
# Luồng 1 — Step 2: Sinh Quick Quiz
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
    Bước 2 Luồng 1: Sinh quiz từ raw_text thực của tài liệu.
    Nếu đã có mastery cho môn này, trả về quiz_skipped=True.
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
        quiz_skipped=False,
    )


# ---------------------------------------------------------------------------
# Luồng 2 — Step 1: Parse đề thi
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


# ---------------------------------------------------------------------------
# Luồng 1 Step 3 / Luồng 2 Step 2: Nộp kết quả + Lưu DB
# ---------------------------------------------------------------------------

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
    # Luồng 1 — vị trí hiện tại trong chương trình + thời hạn/quỹ thời gian mục tiêu
    curriculum_position: Annotated[str | None, Form()] = None,  # JSON: {"topic": str, "on_track": bool}
    topics: Annotated[str | None, Form()] = None,  # JSON: toàn bộ mục lục tài liệu theo đúng thứ tự
    deadline: Annotated[str | None, Form()] = None,  # ISO date YYYY-MM-DD
    start_date: Annotated[str | None, Form()] = None,  # ISO date YYYY-MM-DD — mặc định hôm nay
    minutes_per_day: Annotated[str | None, Form()] = None,
    days_per_week: Annotated[str | None, Form()] = None,
    evidence_type: Annotated[str | None, Form()] = None,  # "transcript"|"certificate"|"exam"|"other"
    reading_time_hint: Annotated[str | None, Form()] = None,  # JSON: kết quả estimate_reading_time() từ bước phân tích
    temp_file_id: Annotated[str | None, Form()] = None,  # Dùng lại file đã lưu tạm ở bước phân tích, khỏi phải upload lại
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
      (điểm số đã được gộp vào bước chọn câu hỏi, không cần bước riêng nữa)
    """
    filename = file.filename if file else "upload"
    file_bytes = await file.read() if file else b""

    # Nếu không upload file trực tiếp, thử dùng lại file đã lưu tạm ở bước phân tích tài liệu
    if not file and temp_file_id:
        staged = read_temp_file(temp_file_id, str(current_user.id))
        if staged is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="File tạm đã hết hạn hoặc không tìm thấy. Vui lòng chọn lại file tài liệu.",
            )
        file_bytes, filename = staged

    ext = os.path.splitext(filename)[1].lower() if file_bytes else ""
    if file_bytes and ext not in ALL_SUPPORTED_EXTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Định dạng '{ext}' không được hỗ trợ.",
        )

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

    # Parse vị trí hiện tại trong chương trình (chỉ 1 điểm mốc + có bị hổng hay không)
    curriculum_position_parsed: dict | None = None
    if curriculum_position:
        try:
            parsed_pos = json.loads(curriculum_position)
            if isinstance(parsed_pos, dict) and parsed_pos.get("topic"):
                curriculum_position_parsed = {
                    "topic": str(parsed_pos["topic"]),
                    "on_track": bool(parsed_pos.get("on_track", True)),
                }
        except Exception:
            pass

    deadline_date: date | None = None
    if deadline:
        try:
            deadline_date = date.fromisoformat(deadline.strip())
        except Exception:
            pass

    minutes_per_day_parsed = 60
    if minutes_per_day:
        try:
            minutes_per_day_parsed = max(10, min(600, int(minutes_per_day)))
        except Exception:
            pass

    days_per_week_parsed = 7
    if days_per_week:
        try:
            days_per_week_parsed = max(1, min(7, int(days_per_week)))
        except Exception:
            pass

    # Toàn bộ mục lục tài liệu (theo thứ tự) — dùng để tách phần đã học / cần học
    topics_parsed: list[str] = []
    if topics:
        try:
            topics_parsed = [str(t) for t in json.loads(topics) if str(t).strip()]
        except Exception:
            pass

    # Ước lượng thời gian đọc đã tính ở bước phân tích tài liệu (Layer 0) — dùng làm ngữ cảnh
    # tham khảo cho bước sinh lộ trình, không tính lại.
    reading_time_parsed: dict | None = None
    if reading_time_hint:
        try:
            reading_time_parsed = json.loads(reading_time_hint)
        except Exception:
            pass

    # Tách "đã học" (loại khỏi lộ trình) và "cần học/ưu tiên" dựa trên vị trí đã tick:
    # các mục TRƯỚC vị trí tick coi như đã học (trừ khi on_track=False → coi như cần ôn lại),
    # mục TẠI và SAU vị trí tick coi như chưa học — ưu tiên đưa vào lộ trình.
    learned_topics: list[str] = []
    priority_topics: list[str] = list(topics_parsed)
    if curriculum_position_parsed and curriculum_position_parsed["topic"] in topics_parsed:
        idx = topics_parsed.index(curriculum_position_parsed["topic"])
        if curriculum_position_parsed["on_track"]:
            learned_topics = topics_parsed[:idx]
            priority_topics = topics_parsed[idx:]
        else:
            # Bị hổng — không loại phần trước mốc, ưu tiên ôn lại toàn bộ từ đầu đến mốc + phần sau
            priority_topics = topics_parsed

    # Ensure learner profile
    learner = await ensure_learner_profile(session, current_user.id)

    # Ghi nhận vị trí hiện tại + hạn mục tiêu vào LearnerProfile (chỉ luồng onboarding)
    if mode == "onboarding" and (curriculum_position_parsed or deadline_date):
        if deadline_date:
            learner.deadline = deadline_date
        if curriculum_position_parsed:
            learner.diagnostic_results = [
                *[
                    d for d in learner.diagnostic_results
                    if not (isinstance(d, dict) and d.get("type") == "curriculum_position")
                ],
                {"type": "curriculum_position", **curriculum_position_parsed},
            ]
        learner.profile_version += 1

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

    # AI Recommendation (Groq) — chỉ Luồng 2 (post_exam). Luồng 1 (onboarding) không dùng phân
    # tích theo câu hỏi kiểu đề thi này nữa — tài liệu học không phải đề thi nên phân tích này
    # không phù hợp; toàn bộ "vì sao học phần này" giờ nằm trong chính lộ trình sinh ra bên dưới.
    ai_rec: dict = {}
    if settings.llm_api_key and settings.llm_model and mode == "post_exam" and selected_questions:
        try:
            selected_qs = json.loads(selected_questions)
        except Exception:
            selected_qs = []

        ai_rec = await get_ai_recommendation_groq(
            questions=selected_qs,
            score_ratio=score_ratio,
            weak_areas=None,
            gemini_api_keys=settings.gemini_api_keys,
            llm_api_keys=settings.llm_api_keys,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )

    # Crawl resources (general)
    crawl_query = raw_text_for_crawl or parsed.get("raw_markdown", "")[:500]
    if crawl_query.strip() and not resources.get("youtube_tutorials"):
        try:
            resources = await crawl_resources_smart(crawl_query, is_code_related=code_related)
        except Exception as e:
            logger.warning(f"Resource crawl failed: {e}")

    # === LUỒNG 2: Xử lý 3 phương án — crawl lời giải + sinh gợi ý AI ===
    solution_results: list[dict] = []
    if mode == "post_exam" and selected_questions and settings.llm_api_key and settings.llm_model:
        try:
            selected_qs_parsed = json.loads(selected_questions)
        except Exception:
            selected_qs_parsed = []

        # Tách câu theo phương án
        questions_by_level: dict[str, list[dict]] = {
            "Không biết làm": [],
            "Hiểu đề nhưng không biết bắt đầu từ đâu": [],
            "Sắp làm được rồi nhưng vẫn còn thiếu một chút": [],
        }
        for q in selected_qs_parsed:
            lvl = q.get("level", "Không biết làm")
            if lvl in questions_by_level:
                questions_by_level[lvl].append(q)

        # Xử lý các phương án có crawl lời giải
        for level_key in ["Hiểu đề nhưng không biết bắt đầu từ đâu", "Sắp làm được rồi nhưng vẫn còn thiếu một chút"]:
            for q in questions_by_level[level_key]:
                q_content = q.get("content", "")
                q_id = q.get("id", "")

                # Crawl lời giải + sinh gợi ý song song
                try:
                    import asyncio as _aio
                    hint_task = generate_solution_hint(
                        question_content=q_content,
                        support_level=level_key,
                        gemini_api_keys=settings.gemini_api_keys,
                        llm_api_keys=settings.llm_api_keys,
                        llm_base_url=settings.llm_base_url,
                        llm_model=settings.llm_model,
                    )
                    crawl_task = crawl_solution_for_question(q_content)
                    hint_result, crawled = await _aio.gather(hint_task, crawl_task, return_exceptions=True)
                except Exception as e:
                    logger.warning(f"Solution processing failed for {q_id}: {e}")
                    hint_result = {"hint": "", "traps": "", "tips": ""}
                    crawled = []

                solution_results.append({
                    "question_id": q_id,
                    "question_content": q_content,
                    "support_level": level_key,
                    "hint": hint_result.get("hint", "") if isinstance(hint_result, dict) else "",
                    "traps": hint_result.get("traps", "") if isinstance(hint_result, dict) else "",
                    "tips": hint_result.get("tips", "") if isinstance(hint_result, dict) else "",
                    "crawled_solutions": crawled if isinstance(crawled, list) else [],
                })

        # Lấy thông tin từ ai_rec cho các câu "Không biết làm"
        q_ai_details = {}
        if ai_rec:
            for group_key in ("nhom_co_ban", "nhom_van_dung", "nhom_van_dung_cao"):
                for q in ai_rec.get(group_key, {}).get("chi_tiet_tung_cau", []):
                    q_id = q.get("id_cau", "")
                    if q_id:
                        q_ai_details[q_id] = q

        # Phương án "Không biết làm" → lấy thông tin từ ai_rec
        for q in questions_by_level["Không biết làm"]:
            q_id = q.get("id", "")
            q_ai = q_ai_details.get(q_id, {})
            loi_khuyen = q_ai.get("loi_khuyen_ngan", "")
            mini_test = q_ai.get("mini_test_and_roadmap", "")
            
            hint_text = ""
            if loi_khuyen:
                hint_text += f"**Hướng dẫn / Lời khuyên:**\n{loi_khuyen}\n\n"
            if mini_test:
                hint_text += f"**Đánh giá & Ôn tập:**\n{mini_test}"

            solution_results.append({
                "question_id": q_id,
                "question_content": q.get("content", ""),
                "support_level": "Không biết làm",
                "hint": hint_text.strip(),
                "traps": "",
                "tips": "",
                "crawled_solutions": [],
            })

    # === SINH LỘ TRÌNH AI (chỉ khi có câu "Không biết làm" hoặc luồng onboarding) ===
    weak_topics: list[str] = []
    if ai_rec:
        for group_key in ("nhom_co_ban", "nhom_van_dung", "nhom_van_dung_cao"):
            for q in ai_rec.get(group_key, {}).get("chi_tiet_tung_cau", []):
                kn = q.get("kien_thuc_can_hoc", "").strip()
                if kn and kn not in weak_topics:
                    weak_topics.append(kn)

    if not weak_topics and quick_quiz_results:
        try:
            qr_list = json.loads(quick_quiz_results)
            weak_topics = list({qr.get("topic", "") for qr in qr_list if not qr.get("correct", True) and qr.get("topic")})
        except Exception:
            pass

    # Luồng onboarding: ưu tiên dùng mục lục thật (đã tách đã học/cần học theo vị trí đã tick);
    # nếu người dùng không tick vị trí nào (topics_parsed rỗng), fallback về weak_topics như cũ.
    roadmap_topics = priority_topics if priority_topics else weak_topics

    # Cho post_exam: chỉ sinh lộ trình nếu có "Không biết làm"
    should_generate_roadmap = mode == "onboarding"
    if mode == "post_exam" and selected_questions:
        try:
            selected_qs_check = json.loads(selected_questions)
            has_dont_know = any(q.get("level") == "Không biết làm" for q in selected_qs_check)
            should_generate_roadmap = has_dont_know
        except Exception:
            pass

    goal_for_roadmap = selected_goal or ai_rec.get("_goal", "Nắm vững kiến thức")
    inline_roadmap: dict = {}
    phase_resources: dict = {}
    roadmap_error: str | None = None

    if should_generate_roadmap:
        if not settings.llm_model or not settings.llm_api_key:
            roadmap_error = "LLM chưa được cấu hình — không thể sinh lộ trình học tập."
            logger.warning("Roadmap generation skipped: LLM not configured")
        else:
            try:
                inline_roadmap = await generate_learning_roadmap(
                    subject=subject or "Học tập tổng quát",
                    weak_topics=roadmap_topics if mode == "onboarding" else weak_topics,
                    learned_topics=learned_topics,
                    selected_goal=goal_for_roadmap,
                    score_ratio=score_ratio,
                    minutes_per_day=minutes_per_day_parsed,
                    days_per_week=days_per_week_parsed,
                    quick_quiz_results_str=quick_quiz_results,
                    evidence_summary=evidence_type,
                    curriculum_position=curriculum_position_parsed,
                    deadline=deadline,
                    start_date=start_date,
                    reading_time=reading_time_parsed,
                    gemini_api_keys=settings.gemini_api_keys,
                    llm_api_keys=settings.llm_api_keys,
                    llm_base_url=settings.llm_base_url,
                    llm_model=settings.llm_model,
                )
                phases = inline_roadmap.get("phases", [])
                if phases:
                    phase_resources = await crawl_resources_per_phase(
                        phases=phases,
                        subject=subject or "học tập",
                        is_code_related=code_related,
                    )
            except Exception as e:
                roadmap_error = f"Sinh lộ trình thất bại: {str(e)[:200]}"
                logger.error(f"Roadmap generation failed (mode={mode}, subject={subject}): {e}", exc_info=True)


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

    # Lưu file vào thư mục uploads
    file_path: str | None = None
    if file_bytes and filename and subject:
        try:
            folder_type = "Doc" if mode == "onboarding" else "Exam"
            file_path = save_upload_file(
                file_bytes=file_bytes,
                filename=filename,
                user_id=str(current_user.id),
                folder_type=folder_type,
                subject_name=subject,
                base_uploads_dir="uploads",
            )
        except Exception as e:
            logger.warning(f"File save failed: {e}")

    # File đã lưu chính thức (hoặc lưu thất bại) — dọn bản tạm, không cần giữ nữa
    if temp_file_id:
        discard_temp_file(temp_file_id, str(current_user.id))

    # Tính hash của file để lưu vào DB (phát hiện trùng lập sau này)
    import hashlib as _hashlib
    computed_file_hash: str | None = None
    if file_bytes:
        computed_file_hash = _hashlib.sha256(file_bytes).hexdigest()

    # Gắn với Course thay vì lưu subject dạng chuỗi tự do rời rạc — tìm course nháp đã có
    # của chính người dùng theo tên môn (không phân biệt hoa/thường), nếu chưa có thì tạo mới.
    resolved_subject = subject or (ai_rec.get("_goal", "") if ai_rec else None)
    course_id: UUID | None = None
    if resolved_subject:
        existing_course = (
            await session.execute(
                select(Course).where(
                    Course.owner_id == current_user.id,
                    func.lower(Course.subject) == resolved_subject.strip().lower(),
                )
            )
        ).scalars().first()
        if existing_course is None:
            existing_course = Course(
                owner_id=current_user.id,
                title=resolved_subject.strip(),
                subject=resolved_subject.strip(),
                grade_level=12,  # placeholder cho môn học tổng quát (không phải K-12 cụ thể)
                status=CourseStatus.DRAFT.value,
            )
            session.add(existing_course)
            await session.flush()
        course_id = existing_course.id

    # Lưu DB
    analysis = ExamAnalysis(
        learner_id=learner.id,
        filename=filename,
        subject=resolved_subject,
        course_id=course_id,
        file_path=file_path,
        file_hash=computed_file_hash,
        ocr_engine=parsed.get("ocr_engine", "unknown"),
        question_count=parsed.get("question_count", 0),
        formula_count=parsed.get("formula_count", 0),
        exam_score=score,
        exam_max_score=max_score,
        questions_json=parsed.get("questions", []),
        raw_markdown=parsed.get("raw_markdown"),
        ai_recommendation_json={
            **ai_rec,
            "_mode": mode,
            "_goal": selected_goal or ai_rec.get("_goal", ""),
            "_roadmap": inline_roadmap,
            "_solution_results": solution_results,
            # Snapshot các bước người dùng đã điền — dùng để xem lại sau này (chỉ đọc, không sửa)
            "_curriculum_position": curriculum_position_parsed,
            "_deadline": deadline,
            "_minutes_per_day": minutes_per_day_parsed,
            "_evidence_type": evidence_type,
            "_quiz_summary": (
                {
                    "correct": sum(1 for q in quiz_results_parsed if q.get("correct")),
                    "total": len(quiz_results_parsed),
                }
                if quiz_results_parsed
                else None
            ),
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
        subject=analysis.subject,
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
        roadmap_error=roadmap_error,
        solution_results=solution_results,
        created_at=analysis.created_at,
    )



# ---------------------------------------------------------------------------
# History endpoints
# ---------------------------------------------------------------------------

@router.get("/subjects", response_model=list[SubjectSummary])
async def list_subjects(
    current_user: CurrentStudent,
    session: DatabaseSession,
    mode: str = Query(default="onboarding", description="onboarding hoặc post_exam"),
) -> list[SubjectSummary]:
    """Trả về danh sách môn học / đề thi đã làm của user theo mode."""
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        return []
    result = await session.execute(
        select(ExamAnalysis)
        .where(ExamAnalysis.learner_id == learner.id)
        .order_by(ExamAnalysis.created_at.desc())
        .limit(200)
    )
    analyses = list(result.scalars().all())

    # Group by subject + mode
    subject_map: dict[str, dict] = {}
    for a in analyses:
        a_mode = a.ai_recommendation_json.get("_mode", "post_exam")
        if a_mode != mode:
            continue
        subj = a.subject or a.ai_recommendation_json.get("_goal", "Không xác định") or "Không xác định"
        key = subj
        if key not in subject_map:
            subject_map[key] = {"subject": subj, "mode": mode, "count": 0, "last_used": a.created_at}
        subject_map[key]["count"] += 1

    return [SubjectSummary(**v) for v in subject_map.values()]


@router.get("/subjects/{subject}/analyses", response_model=list[ExamAnalysisSummary])
async def list_analyses_by_subject(
    subject: str,
    current_user: CurrentStudent,
    session: DatabaseSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ExamAnalysisSummary]:
    """Trả về danh sách analyses theo môn học."""
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        return []
    result = await session.execute(
        select(ExamAnalysis)
        .where(
            ExamAnalysis.learner_id == learner.id,
            ExamAnalysis.subject == subject,
        )
        .order_by(ExamAnalysis.created_at.desc())
        .limit(limit)
    )
    analyses = list(result.scalars().all())
    return [
        ExamAnalysisSummary(
            id=str(a.id),
            filename=a.filename,
            subject=a.subject,
            mode=a.ai_recommendation_json.get("_mode", "post_exam"),
            question_count=a.question_count,
            formula_count=a.formula_count,
            ocr_engine=a.ocr_engine,
            exam_score=a.exam_score,
            exam_max_score=a.exam_max_score,
            mastery_updates_count=len(a.mastery_updates_json),
            created_at=a.created_at,
        )
        for a in analyses
    ]


@router.delete("/temp-files/{temp_file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_staged_temp_file(
    temp_file_id: str,
    current_user: CurrentStudent,
) -> None:
    """Xóa file đã lưu tạm khi người dùng bỏ dở luồng (không nộp bài)."""
    discard_temp_file(temp_file_id, str(current_user.id))


def _delete_file_on_disk(file_path: str | None) -> None:
    """Xóa file vật lý tương ứng một ExamAnalysis — best-effort, không chặn nếu đã mất/thiếu quyền."""
    if not file_path:
        return
    try:
        if os.path.isfile(file_path):
            os.remove(file_path)
    except OSError as e:
        logger.warning(f"Không thể xóa file '{file_path}': {e}")


@router.delete("/subjects/{subject}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject: str,
    current_user: CurrentStudent,
    session: DatabaseSession,
) -> None:
    """Học viên tự xóa toàn bộ tài liệu/lộ trình của một môn học của chính mình."""
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        return
    result = await session.execute(
        select(ExamAnalysis).where(
            ExamAnalysis.learner_id == learner.id,
            ExamAnalysis.subject == subject,
        )
    )
    analyses = list(result.scalars().all())
    if not analyses:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy môn học này.")
    ids = [a.id for a in analyses]
    await session.execute(delete(PersonalizedRoadmap).where(PersonalizedRoadmap.exam_analysis_id.in_(ids)))
    await session.execute(delete(ExamAnalysis).where(ExamAnalysis.id.in_(ids)))
    await session.commit()
    for a in analyses:
        _delete_file_on_disk(a.file_path)


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam_analysis(
    analysis_id: str,
    current_user: CurrentStudent,
    session: DatabaseSession,
) -> None:
    """Học viên tự xóa một tài liệu/bản phân tích của chính mình."""
    learner = await get_learner_profile(session, current_user.id)
    if not learner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy.")
    try:
        uuid_id = UUID(analysis_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ID không hợp lệ.")
    result = await session.execute(
        select(ExamAnalysis).where(
            ExamAnalysis.id == uuid_id,
            ExamAnalysis.learner_id == learner.id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy.")
    await session.execute(delete(PersonalizedRoadmap).where(PersonalizedRoadmap.exam_analysis_id == analysis.id))
    file_path = analysis.file_path
    await session.delete(analysis)
    await session.commit()
    _delete_file_on_disk(file_path)


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
            subject=a.subject,
            mode=a.ai_recommendation_json.get("_mode", "post_exam"),
            question_count=a.question_count,
            formula_count=a.formula_count,
            ocr_engine=a.ocr_engine,
            exam_score=a.exam_score,
            exam_max_score=a.exam_max_score,
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

    ai_rec = analysis.ai_recommendation_json or {}
    roadmap = ai_rec.get("_roadmap", {})
    solution_results = ai_rec.get("_solution_results", [])

    return ExamAnalysisDetail(
        id=str(analysis.id),
        filename=analysis.filename,
        subject=analysis.subject,
        mode=ai_rec.get("_mode", "post_exam"),
        question_count=analysis.question_count,
        formula_count=analysis.formula_count,
        ocr_engine=analysis.ocr_engine,
        exam_score=analysis.exam_score,
        exam_max_score=analysis.exam_max_score,
        questions=analysis.questions_json,
        raw_markdown=analysis.raw_markdown,
        ai_recommendation=ai_rec,
        resources=analysis.resources_json,
        mastery_updates=analysis.mastery_updates_json,
        roadmap=roadmap,
        phase_resources={},
        solution_results=solution_results,
        created_at=analysis.created_at,
    )


@router.get("/{analysis_id}/file")
async def get_exam_analysis_file(
    analysis_id: str,
    current_user: CurrentStudent,
    session: DatabaseSession,
) -> FileResponse:
    """Trả về file gốc đã upload (để xem lại) — chỉ chủ sở hữu mới xem được."""
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
    if not analysis or not analysis.file_path or not os.path.isfile(analysis.file_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy file gốc (có thể đã bị xóa).")
    return FileResponse(
        analysis.file_path,
        filename=analysis.filename,
        content_disposition_type="inline",
    )
