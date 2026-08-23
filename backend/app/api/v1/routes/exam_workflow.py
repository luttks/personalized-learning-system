"""
Exam Workflow API — OCR, parsing, AI recommendations, and resource crawling.

Provides REST endpoints that replace the server-side rendered Jinja2 pages
from the original WorkFlow project.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.crawler_service import crawl_resources_parallel
from app.services.exam_parser_service import parse_exam_questions
from app.services.ocr_service import (
    get_ai_recommendation,
    read_text_document,
    run_gemini_ocr,
)

router = APIRouter(prefix="/exam-workflow", tags=["Exam Workflow"])

# Supported file extensions
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_DOC_EXTS = {".docx", ".doc", ".txt", ".html", ".htm"}
_ALL_SUPPORTED = _IMAGE_EXTS | {".pdf"} | _DOC_EXTS


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ParseTextRequest(BaseModel):
    markdown_text: str


class RecommendationRequest(BaseModel):
    questions: list[str]


class CrawlQueryRequest(BaseModel):
    query: str


# ---------------------------------------------------------------------------
# Helper: resolve Gemini API keys from environment
# ---------------------------------------------------------------------------

def _get_gemini_keys() -> list[str]:
    """Collect all configured Gemini API keys."""
    keys: list[str] = []
    for env_var in ("GEMINI_API_KEY", "GEMINI_API_KEY2"):
        val = os.environ.get(env_var, "").strip()
        if val:
            keys.append(val)
    return keys


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/process-file")
async def process_file(
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    Upload an exam image / PDF / document and receive structured OCR results.

    - Images & PDFs are sent to Gemini for OCR.
    - Text documents (.txt, .docx, .html) are read directly.
    - The response is either an exam (``loai=1``) or a gradebook (``loai=2``).
    """
    start_time = time.time()
    suffix = os.path.splitext(file.filename or "")[1].lower()

    if suffix not in _ALL_SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Định dạng '{suffix}' không được hỗ trợ. "
                "Vui lòng chọn JPG, PNG, WEBP, PDF, DOCX, TXT."
            ),
        )

    # Save uploaded file to a temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        if suffix in _DOC_EXTS:
            raw_text = read_text_document(tmp_path, suffix)
            ocr_engine_used = "document_reader"
            ocr_data: dict[str, Any] = {"loai": 1, "exam_content": raw_text}
        else:
            keys_to_try = _get_gemini_keys()
            if not keys_to_try:
                raise HTTPException(
                    status_code=400,
                    detail="Thiếu GEMINI_API_KEY trong cấu hình .env.",
                )

            raw_text = None
            last_err: Exception | None = None

            for key in keys_to_try:
                try:
                    raw_text = await run_gemini_ocr(tmp_path, suffix, key)
                    break
                except ValueError as ve:
                    raise HTTPException(
                        status_code=400, detail=str(ve),
                    ) from ve
                except Exception as exc:
                    last_err = exc
                    continue

            if raw_text is None:
                err_msg = str(last_err)
                if (
                    "api_key_invalid" in err_msg.lower()
                    or "api key not valid" in err_msg.lower()
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "API Key Gemini không hợp lệ hoặc đã hết hạn "
                            "(đã thử tất cả keys)."
                        ),
                    )
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Lỗi gọi Gemini API "
                        f"(đã thử {len(keys_to_try)} keys): {err_msg}"
                    ),
                )

            ocr_engine_used = "gemini-flash"

            try:
                ocr_data = json.loads(raw_text)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=500,
                    detail="Dữ liệu trả về từ mô hình không phải JSON hợp lệ.",
                )

        # ----- Build response -----
        loai = ocr_data.get("loai", 1)
        if loai == 1:
            exam_content = ocr_data.get("exam_content", "")
            parsed_result: dict[str, Any] = parse_exam_questions(exam_content)
            parsed_result["loai"] = 1
        elif loai == 2:
            parsed_result = ocr_data
            parsed_result["loai"] = 2
        else:
            raise HTTPException(
                status_code=500,
                detail="Không xác định được loại tài liệu (loai).",
            )

        elapsed = round(time.time() - start_time, 2)
        parsed_result["elapsed_seconds"] = elapsed
        parsed_result["filename"] = file.filename
        parsed_result["status"] = "success"
        parsed_result["ocr_engine"] = ocr_engine_used

        return parsed_result

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Lỗi xử lý: {exc}",
        ) from exc
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


@router.post("/parse-markdown")
async def parse_markdown(payload: ParseTextRequest) -> dict[str, Any]:
    """Parse raw Markdown / LaTeX text into structured exam questions."""
    result = parse_exam_questions(payload.markdown_text)
    return {"status": "success", "data": result}


@router.post("/recommend")
async def recommend_questions(
    payload: RecommendationRequest,
) -> dict[str, Any]:
    """
    Analyse a list of exam questions and return AI-generated difficulty
    classifications with learning recommendations.
    """
    keys_to_try = _get_gemini_keys()
    if not keys_to_try:
        raise HTTPException(
            status_code=400,
            detail="Thiếu GEMINI_API_KEY trong cấu hình .env.",
        )

    ai_res: dict[str, Any] | None = None
    last_err: Exception | None = None

    for key in keys_to_try:
        try:
            ai_res = await get_ai_recommendation(payload.questions, key)
            break
        except Exception as exc:
            last_err = exc
            continue

    if ai_res is None:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Lỗi phân tích AI "
                f"(đã thử {len(keys_to_try)} keys): {last_err}"
            ),
        )
    return ai_res


@router.post("/crawl-resources")
async def crawl_resources_endpoint(
    payload: CrawlQueryRequest,
) -> dict[str, Any]:
    """
    Crawl external educational resources (YouTube, quizzes, academic
    papers, GitHub repos) for a given search query.
    """
    if not payload.query or not payload.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Vui lòng nhập từ khóa/nội dung tìm kiếm.",
        )

    return await crawl_resources_parallel(payload.query.strip())
