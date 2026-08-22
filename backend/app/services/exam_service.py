"""
Exam Service — tích hợp toàn bộ logic phân tích tài liệu và đề thi.

Chiến lược API:
  - OCR ảnh/PDF   → Gemini (KEY1 → KEY2 fallback) → text fallback
  - Phân tích AI  → Groq (nhanh, tốt cho tiếng Việt)
  - Crawl         → YouTube + DuckDuckGo luôn; GitHub chỉ khi code-related
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10)


# ---------------------------------------------------------------------------
# Ước lượng thời gian đọc tài liệu (Layer 0) — tính bằng code, KHÔNG dùng LLM để đếm/ước lượng
# vì LLM vốn kém trong việc đếm số lượng chính xác. Bảng tốc độ đọc tham khảo theo nghiên cứu
# phổ biến về tốc độ đọc trung bình của con người theo từng mục đích đọc.
# ---------------------------------------------------------------------------

READING_SPEED_WPM: dict[str, tuple[int, int]] = {
    "survey": (200, 300),      # Đọc lướt / khảo sát
    "general": (150, 200),     # Đọc hiểu đại trà
    "technical": (70, 100),    # Đọc chuyên ngành / kỹ thuật
    "deep_study": (20, 50),    # Học sâu (ghi chú, làm bài tập, phản biện, mã hóa)
}


def estimate_reading_time(text: str) -> dict[str, Any]:
    """Ước lượng khoảng thời gian (phút) một người trung bình cần để xử lý tài liệu, theo 4 mục
    đích đọc khác nhau. Đây là ước lượng TỔNG QUÁT (chưa cá nhân hóa) — dùng làm mốc tham chiếu
    ban đầu cho các bước cá nhân hóa sau."""
    word_count = len(text.split())
    result: dict[str, Any] = {"word_count": word_count}
    for key, (wpm_low, wpm_high) in READING_SPEED_WPM.items():
        # Tốc độ đọc CÀNG CAO thì thời gian CÀNG THẤP — nên min dùng wpm_high, max dùng wpm_low.
        result[f"{key}_minutes_min"] = round(word_count / wpm_high) if word_count else 0
        result[f"{key}_minutes_max"] = round(word_count / wpm_low) if word_count else 0
    return result

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_DOC_EXTS = {".docx", ".doc", ".txt", ".html", ".htm"}
ALL_SUPPORTED_EXTS = _IMAGE_EXTS | {".pdf"} | _DOC_EXTS

_GEMINI_OCR_PROMPT = (
    "Bạn là một mô hình phân tích và bóc tách tài liệu giáo dục. "
    "Hãy phân tích hình ảnh/tài liệu được cung cấp. "
    "PHẢI TRẢ VỀ KẾT QUẢ DƯỚI DẠNG ĐỊNH DẠNG JSON theo cấu trúc sau: "
    '{"exam_content": "Trích xuất TOÀN BỘ nội dung thành Markdown kết hợp LaTeX, LẦN LƯỢT theo '
    "ĐÚNG THỨ TỰ TỪNG TRANG, không bỏ sót trang nào. "
    "QUAN TRỌNG: nếu trong tài liệu có trang mục lục / danh mục / bìa, hãy chép qua thật nhanh rồi "
    "BẮT BUỘC tiếp tục chép đầy đủ nội dung TẤT CẢ các trang còn lại phía sau — TUYỆT ĐỐI KHÔNG được "
    "dừng lại hay coi như đã xong chỉ vì đã gặp trang mục lục. "
    "Giữ nguyên cấu trúc tài liệu. "
    "Tất cả công thức toán học PHẢI bọc trong $...$ hoặc $$...$$. "
    'Đảm bảo cú pháp LaTeX chính xác."}'
)

# CODE-RELATED keywords để detect xem có nên crawl GitHub không
_CODE_KEYWORDS = {
    "python", "java", "javascript", "typescript", "c++", "c#", "golang", "rust",
    "lập trình", "programming", "algorithm", "thuật toán", "data structure",
    "cấu trúc dữ liệu", "database", "cơ sở dữ liệu", "sql", "machine learning",
    "deep learning", "neural network", "mạng nơ-ron", "web", "backend", "frontend",
    "api", "microservices", "docker", "kubernetes", "git", "devops", "linux",
    "operating system", "hệ điều hành", "compiler", "trình biên dịch",
    "software engineering", "kỹ thuật phần mềm", "network", "mạng máy tính",
}


# ---------------------------------------------------------------------------
# LaTeX Normalizer
# ---------------------------------------------------------------------------

def auto_format_math_latex(text: str) -> str:
    r"""Chuẩn hoá cú pháp LaTeX: \(...\) → $...$, \[...\] → $$...$$"""
    if not text:
        return ""
    text = text.replace(r"\\(", "$").replace(r"\\)", "$")
    text = text.replace(r"\\\[", "$$").replace(r"\\\]", "$$")
    text = text.replace(r"\(", "$").replace(r"\)", "$")
    text = text.replace(r"\[", "$$").replace(r"\]", "$$")
    return text


def _parse_json_safely(raw: str) -> Any:
    """Loại bỏ trailing commas và dọn dẹp chuỗi JSON trước khi parse."""
    raw = raw.strip()
    # Tìm block ```json ... ```
    import re
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
    if match:
        raw = match.group(1)
    else:
        # Nếu không có markdown block, cố gắng tìm ngoặc nhọn đầu tiên và cuối cùng
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end != -1:
            raw = raw[start:end+1]
    
    raw = raw.strip()
    # Loại bỏ trailing commas trước ngoặc đóng
    import re
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    
    # Sửa lỗi LLM trả về \frac thay vì \\frac trong JSON
    # Tìm các dấu \ KHÔNG đi liền với các ký tự escape hợp lệ mà ta muốn giữ lại (", \, n)
    # VÀ không được đứng sau một dấu \ khác (để tránh làm hỏng \\frac thành \\\frac)
    raw = re.sub(r'(?<!\\)\\(?![\\n"])', r'\\\\', raw)
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"JSONDecodeError in _parse_json_safely: {e}. Raw text: {raw[:200]}...")
        # Fallback cuối cùng nếu vẫn lỗi
        raise ValueError(f"Không thể parse JSON từ AI: {e}")


def _sample_text_for_classification(raw_text: str, max_chars: int = 3000) -> str:
    """Lấy mẫu văn bản để đưa vào prompt phân loại môn học/cấu trúc tài liệu.

    Với tài liệu dài, chỉ lấy `max_chars` ký tự đầu tiên rất dễ chỉ rơi vào trang bìa/mục lục
    (đặc biệt với sách giáo khoa), khiến AI phân loại nhầm là "chỉ có mục lục, không có nội dung
    giảng dạy". Vì vậy lấy thêm một đoạn trích ở khoảng giữa tài liệu để đảm bảo luôn thấy được
    nội dung giảng dạy thực sự, không chỉ phần mở đầu.
    """
    if len(raw_text) <= max_chars:
        return raw_text

    head_chars = max_chars // 2
    mid_start = len(raw_text) * 2 // 5
    mid_chars = max_chars - head_chars
    return (
        raw_text[:head_chars]
        + "\n\n[... trích đoạn giữa tài liệu ...]\n\n"
        + raw_text[mid_start : mid_start + mid_chars]
    )


# ---------------------------------------------------------------------------
# Question Parser
# ---------------------------------------------------------------------------

def parse_exam_questions(text: str) -> dict[str, Any]:
    """Parse Markdown/LaTeX thành cấu trúc đề thi có phân cấp."""
    text_clean = auto_format_math_latex(text)
    lines = text_clean.split("\n")
    header_lines: list[str] = []
    questions: list[dict] = []

    question_pattern = re.compile(
        r"^(Câu|Bài)\s+([IVXLCDM0-9]+)[:\.]?\s*(?:\(([^)]+)\))?",
        re.IGNORECASE,
    )
    points_pattern = re.compile(
        r"\(?\s*([0-9]+[,\.][0-9]+\s*điểm|[0-9]+\s*đ(?:iểm)?)\s*\)?",
        re.IGNORECASE,
    )

    current_q: dict | None = None
    for line in lines:
        raw_stripped = line.strip()
        clean_line = re.sub(r"[#*_]", "", raw_stripped).strip()
        match = question_pattern.search(clean_line)
        if match:
            if current_q:
                current_q["content"] = current_q["content"].strip()
                questions.append(current_q)
            q_prefix = match.group(1).capitalize()
            q_num = match.group(2).upper()
            q_points = match.group(3).strip() if match.group(3) else ""
            if not q_points:
                pts = points_pattern.search(clean_line)
                if pts:
                    q_points = pts.group(1)
            current_q = {
                "id": f"{q_prefix} {q_num}",
                "title": clean_line,
                "points": q_points,
                "content": "",
                "sub_questions": [],
            }
        else:
            if current_q is None:
                header_lines.append(line)
            else:
                current_q["content"] += line + "\n"

    if current_q:
        current_q["content"] = current_q["content"].strip()
        questions.append(current_q)

    if not questions and text_clean.strip():
        questions = [{
            "id": "Nội dung",
            "title": "Nội dung tài liệu",
            "points": "",
            "content": text_clean.strip(),
            "sub_questions": [],
        }]

    sub_pattern = re.compile(r"^\s*([1-9]\d*|[a-z])[)\.][ \t]+(.*)", re.MULTILINE)
    for q in questions:
        sub_matches = sub_pattern.findall(q["content"])
        if sub_matches:
            q["sub_questions"] = [{"label": m[0], "text": m[1].strip()} for m in sub_matches]

    math_formulas = re.findall(r"\$\$[\s\S]*?\$\$|\$[^$\n]+?\$", text_clean)

    return {
        "header": "\n".join(header_lines).strip(),
        "question_count": len(questions),
        "formula_count": len(math_formulas),
        "questions": questions,
        "raw_markdown": text_clean,
    }


# ---------------------------------------------------------------------------
# Gemini OCR (vision — dùng cho ảnh và PDF)
# ---------------------------------------------------------------------------

async def run_gemini_ocr(file_bytes: bytes, suffix: str, api_key: str) -> str:
    """Gọi Gemini API để OCR file ảnh/PDF."""
    from google import genai  # type: ignore[import]
    from google.genai import errors  # type: ignore[import]

    client = genai.Client(api_key=api_key)
    mime_map = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    mime = mime_map.get(suffix, "image/jpeg")

    last_err: Exception | None = None
    for model_name in ("gemini-3.1-flash-lite",):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    genai.types.Part.from_bytes(data=file_bytes, mime_type=mime),
                    _GEMINI_OCR_PROMPT,
                ],
                config=genai.types.GenerateContentConfig(response_mime_type="application/json"),
            )
            if response and response.text:
                return response.text
        except errors.APIError as e:  # type: ignore[attr-defined]
            msg = str(e)
            if "API_KEY_INVALID" in msg or "API key not valid" in msg:
                raise ValueError(f"GEMINI_API_KEY không hợp lệ: {msg[:100]}")
            logger.warning(f"Gemini OCR model '{model_name}' lỗi ({msg[:80]}), thử model dự phòng...")
            last_err = e
        except Exception as e:
            logger.warning(f"Gemini OCR model '{model_name}' lỗi ({str(e)[:80]}), thử model dự phòng...")
            last_err = e
    if last_err:
        raise last_err
    raise RuntimeError("Không nhận được phản hồi từ Gemini API.")


def read_text_document(file_bytes: bytes, suffix: str) -> str:
    """Đọc tệp văn bản đơn giản (.txt, .html, .docx)."""
    if suffix in (".txt", ".html", ".htm"):
        return file_bytes.decode("utf-8", errors="ignore")
    if suffix in (".docx", ".doc"):
        try:
            import docx  # type: ignore[import]
            import io
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return "Vui lòng cài đặt python-docx để đọc tệp .docx."
    return ""


async def extract_text_from_file(
    file_bytes: bytes,
    filename: str,
    gemini_api_keys: list[str],
) -> tuple[str, str]:
    """
    Trích xuất text từ file bất kỳ.
    Returns: (raw_text, ocr_engine_used)
    """
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in ALL_SUPPORTED_EXTS:
        raise ValueError(f"Định dạng '{suffix}' không được hỗ trợ. Chấp nhận: JPG, PNG, PDF, DOCX, TXT.")

    # Text documents — đọc trực tiếp
    if suffix in _DOC_EXTS:
        raw_text = read_text_document(file_bytes, suffix)
        return raw_text, "text_reader"

    # 1. Nếu là PDF, thử dùng PyMuPDF trước để tiết kiệm token
    if suffix == ".pdf":
        try:
            import fitz  # type: ignore[import]
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
            # Nếu trích xuất được lượng text hợp lý (không phải PDF scan toàn ảnh)
            if len(text.strip()) > 500:
                logger.info("PyMuPDF trích xuất text thành công, bỏ qua Gemini OCR để tiết kiệm token.")
                return text, "pymupdf_first"
        except Exception as e:
            logger.warning(f"PyMuPDF lỗi ({e}), chuyển sang Gemini OCR...")

    # 2. Image hoặc PDF scan — dùng Gemini OCR
    batches = _split_pdf_into_batches(file_bytes) if suffix == ".pdf" else [file_bytes]

    if len(batches) == 1:
        return await _run_gemini_ocr_with_key_fallback(batches[0], suffix, gemini_api_keys), "gemini"

    # Tài liệu nhiều trang: OCR từng phần (đồng thời, giới hạn số lượng) rồi nối lại theo thứ tự.
    # Nếu bắt Gemini trích xuất TOÀN BỘ nội dung của tài liệu rất dài trong 1 lần gọi duy nhất, model
    # có xu hướng "lười" — chỉ tóm tắt qua mục lục rồi dừng thay vì chép hết nội dung từng bài học.
    semaphore = asyncio.Semaphore(4)

    async def _ocr_one_batch(batch_bytes: bytes) -> str:
        async with semaphore:
            return await _run_gemini_ocr_with_key_fallback(batch_bytes, suffix, gemini_api_keys)

    results = await asyncio.gather(
        *(_ocr_one_batch(b) for b in batches), return_exceptions=True
    )

    for result in results:
        if isinstance(result, ValueError):
            raise result  # Key không hợp lệ → raise ngay

    texts = [r for r in results if isinstance(r, str) and r.strip()]
    if not texts:
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            raise RuntimeError(f"Lỗi OCR (Quota/Network): {errors[0]}")
        raise RuntimeError("Không thể trích xuất nội dung từ file.")

    return "\n\n".join(texts), "gemini"


def _split_pdf_into_batches(file_bytes: bytes, pages_per_batch: int = 15) -> list[bytes]:
    """Chia PDF nhiều trang thành các batch nhỏ (mỗi batch là 1 PDF con) để Gemini OCR đầy đủ
    từng phần, thay vì phải xử lý toàn bộ tài liệu lớn trong một lần gọi duy nhất."""
    import fitz  # type: ignore[import]

    src = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        page_count = src.page_count
        if page_count <= pages_per_batch:
            return [file_bytes]

        batches: list[bytes] = []
        for start in range(0, page_count, pages_per_batch):
            end = min(start + pages_per_batch, page_count) - 1
            sub = fitz.open()
            try:
                sub.insert_pdf(src, from_page=start, to_page=end)
                batches.append(sub.tobytes())
            finally:
                sub.close()
        return batches
    finally:
        src.close()


async def _run_gemini_ocr_with_key_fallback(
    file_bytes: bytes, suffix: str, gemini_api_keys: list[str]
) -> str:
    """OCR một phần tài liệu (batch), xoay qua các key nếu lỗi. Trả về raw_text đã trích xuất."""
    last_err: Exception | None = None
    for key in gemini_api_keys:
        if not key or not key.strip():
            continue
        try:
            ocr_json = await run_gemini_ocr(file_bytes, suffix, key)
            data = _parse_json_safely(ocr_json)
            raw_text = data.get("exam_content", "")
            if raw_text.strip():
                return raw_text
        except ValueError:
            raise  # Key không hợp lệ → raise ngay
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise RuntimeError(f"Lỗi OCR (Quota/Network): {last_err}")
    raise RuntimeError("Không thể trích xuất nội dung từ file.")


# ---------------------------------------------------------------------------
# LLM calls — ủy quyền cho app.core.llm_client.LLMClient (client hợp nhất, dùng chung
# cho toàn backend thay vì mỗi service tự viết lại logic Gemini/Groq fallback).
# ---------------------------------------------------------------------------

async def _call_llm_with_fallback(
    prompt: str,
    gemini_keys: list[str],
    groq_keys: list[str],
    groq_base_url: str,
    groq_model: str,
    timeout: float = 60.0,
    expect_json: bool = True,
) -> str:
    """Ưu tiên Gemini (xoay key) → fallback Groq (xoay key). Giữ chữ ký cũ để không phải sửa
    hàng chục call site trong file này; phần triển khai nằm ở `LLMClient`."""
    from app.core.llm_client import LLMClient

    client = LLMClient(
        gemini_api_keys=gemini_keys,
        groq_api_keys=groq_keys,
        groq_base_url=groq_base_url,
        groq_model=groq_model,
        timeout_seconds=timeout,
    )
    return await client.complete_text(prompt, expect_json=expect_json)


def _detect_code_related(text: str) -> bool:
    """Kiểm tra xem nội dung có liên quan đến lập trình không."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in _CODE_KEYWORDS)


# ---------------------------------------------------------------------------
# Document Analysis (Luồng 1 — Bước 1+2)
# ---------------------------------------------------------------------------

async def analyze_document_for_learning(
    file_bytes: bytes,
    filename: str,
    gemini_api_keys: list[str],
    llm_api_keys: list[str],
    llm_base_url: str,
    llm_model: str | None,
) -> dict[str, Any]:
    """
    Phân tích tài liệu để xác định môn học, chủ đề, gợi ý mục tiêu.

    Returns:
        {
            is_learning_doc: bool,
            subject: str,
            topics: list[str],
            suggested_goals: list[str],
            content_summary: str,
            is_code_related: bool,
            raw_text: str,
            ocr_engine: str,
            not_learning_message: str | None,  # khi is_learning_doc=False
        }
    """
    # Bước 1: Trích xuất text từ file
    try:
        raw_text, ocr_engine = await extract_text_from_file(
            file_bytes, filename, gemini_api_keys
        )
    except (ValueError, RuntimeError) as e:
        return {
            "is_learning_doc": False,
            "subject": "Không xác định",
            "topics": [],
            "suggested_goals": [],
            "content_summary": str(e),
            "is_code_related": False,
            "raw_text": "",
            "ocr_engine": "error",
            "not_learning_message": f"Không thể đọc file: {e}",
            "document_level": None,
            "has_clear_structure": False,
            "structure_reason": None,
            "reading_time": estimate_reading_time(""),
        }

    if not raw_text or len(raw_text.strip()) < 30:
        return {
            "is_learning_doc": False,
            "subject": "Không xác định",
            "topics": [],
            "suggested_goals": [],
            "content_summary": "File không có nội dung đọc được.",
            "is_code_related": False,
            "raw_text": "",
            "ocr_engine": ocr_engine,
            "not_learning_message": "Tài liệu trống hoặc không thể đọc. Hãy thử file khác (PDF, DOCX, TXT, ảnh rõ nét).",
            "document_level": None,
            "has_clear_structure": False,
            "structure_reason": None,
            "reading_time": estimate_reading_time(""),
        }

    # Bước 2: AI phân tích nội dung
    is_code_related_quick = _detect_code_related(raw_text[:2000])

    if not llm_api_keys or not llm_model:
        # Fallback không có AI: trả về thông tin cơ bản
        return {
            "is_learning_doc": True,
            "subject": "Tài liệu học tập",
            "topics": [],
            "suggested_goals": [
                "Nắm vững kiến thức cơ bản",
                "Ôn tập và hệ thống hóa kiến thức",
                "Chuẩn bị cho kỳ thi",
            ],
            "content_summary": raw_text[:300] + "...",
            "is_code_related": is_code_related_quick,
            "raw_text": raw_text,
            "ocr_engine": ocr_engine,
            "not_learning_message": None,
            "document_level": None,
            "has_clear_structure": True,
            "structure_reason": None,
            "reading_time": estimate_reading_time(raw_text),
        }

    classification_sample = _sample_text_for_classification(raw_text)

    prompt = f"""Bạn là chuyên gia giáo dục. Hãy phân tích đoạn tài liệu sau và trả về JSON.

NỘI DUNG TÀI LIỆU (trích từ đầu và từ giữa tài liệu để tránh chỉ thấy trang bìa/mục lục):
---
{classification_sample}
---

Trả về JSON với đúng cấu trúc sau (chỉ JSON, không có text ngoài):
{{
  "is_learning_doc": true hoặc false — xem tiêu chí chi tiết bên dưới,
  "not_learning_reason": "Lý do ngắn gọn nếu is_learning_doc=false, để trống nếu true",
  "has_clear_structure": true hoặc false — xem tiêu chí chi tiết bên dưới,
  "structure_reason": "Nếu has_clear_structure=false, giải thích ngắn gọn tại sao, để trống nếu true",
  "subject": "Tên môn học/chủ đề cụ thể (VD: Giải tích 1, Lập trình Python, Ngữ văn 12...)",
  "topics": ["Phần 1", "Phần 2", "Phần 3"] (các đơn vị nội dung theo ĐÚNG thứ tự xuất hiện trong tài liệu — đây sẽ dùng làm mục lục lộ trình; đặt tên theo đúng cách tài liệu tự gọi, xem hướng dẫn bên dưới),
  "suggested_goals": [
    "Mục tiêu cụ thể 1 (VD: Nắm vững lý thuyết giới hạn và đạo hàm)",
    "Mục tiêu cụ thể 2 (VD: Luyện thi cuối kỳ đạt ≥ 7.0 điểm)",
    "Mục tiêu cụ thể 3 (VD: Hiểu sâu để áp dụng vào bài tập nâng cao)",
    "Mục tiêu cụ thể 4 (VD: Ôn tập và hệ thống hóa toàn bộ chương)"
  ],
  "content_summary": "Tóm tắt 2-3 câu về nội dung tài liệu",
  "is_code_related": true hoặc false (true nếu nội dung liên quan đến lập trình/CNTT),
  "document_level": số_nguyên (Dự đoán trình độ học vấn của tài liệu này trên thang điểm 1-19. Cấp 1-12 tương ứng lớp 1-12. Đại học năm 1-7 tương ứng 13-19. Nếu không rõ, trả về null)
}}

TIÊU CHÍ "is_learning_doc" (đánh giá NGHIÊM TÚC — đây là cổng chặn quan trọng nhất, chỉ true khi
người học THỰC SỰ có thể ĐỌC và HỌC ĐƯỢC KIẾN THỨC MỚI từ chính nội dung tài liệu):
- true CHỈ KHI đây là tài liệu giảng dạy/truyền đạt kiến thức thực sự — giáo trình, sách, slide bài
  giảng, ghi chú bài học, tài liệu tổng hợp lý thuyết... — có nội dung GIẢNG GIẢI kiến thức, không chỉ
  liệt kê tiêu đề.
- false nếu rơi vào BẤT KỲ trường hợp nào sau (ghi rõ trường hợp nào trong "not_learning_reason"):
  (a) Đây là ĐỀ THI / BÀI KIỂM TRA / bộ câu hỏi trắc nghiệm hoặc tự luận — kể cả khi được chia theo
      chủ đề/chương rõ ràng. Đề thi dùng để KIỂM TRA kiến thức đã có, không phải tài liệu để HỌC kiến
      thức mới; nó thuộc bước "Minh chứng năng lực" ở giai đoạn sau của quy trình, KHÔNG phải tài liệu
      học tập ở bước này.
  (b) Tài liệu chỉ là khung/mục lục/danh sách tiêu đề chương-bài mà KHÔNG có nội dung giảng dạy thực
      chất bên trong (VD: chỉ có "Chương 1: Giới hạn", "Chương 2: Đạo hàm"... mà không có đoạn văn nào
      giải thích kiến thức) — có cấu trúc nhưng không có gì để học được, vẫn phải false.
  (c) Nội dung không liên quan đến giáo dục (ảnh cá nhân, văn bản ngẫu nhiên, thiên nhiên...).
  (d) Tài liệu trống hoặc gần như trống.

HƯỚNG DẪN XÁC ĐỊNH "topics" (KHÔNG chỉ giới hạn ở "chương"):
Tài liệu có thể tự tổ chức nội dung theo nhiều cách khác nhau — chương ("Chương 1"), bài ("Bài 2"),
phần ("Phần III"), giai đoạn, chủ đề theo thứ tự trình bày, mục đánh số... Hãy nhận diện ĐÚNG theo
cách tài liệu này thực sự tổ chức (không cố ép về "chương" nếu tài liệu không dùng từ đó), và đặt tên
"topics" theo đúng nhãn/thứ tự đó.

TIÊU CHÍ "has_clear_structure" (chỉ đánh giá khi is_learning_doc=true; đây là điều kiện thứ hai, BẮT
BUỘC để tạo lộ trình học chia giai đoạn):
- true: các đơn vị nội dung giảng dạy trong tài liệu xuất hiện theo một TRÌNH TỰ / TUẦN TỰ hợp lý (dù
  không nhất thiết gắn nhãn "chương" — có thể là bài, phần, giai đoạn, mục đánh số, hoặc chuỗi chủ đề
  được trình bày lần lượt theo mạch logic rõ ràng).
- false: tài liệu học được (is_learning_doc=true) nhưng nội dung viết liền mạch không tách được thành
  các phần độc lập có thứ tự rõ ràng (VD: một bài luận/ghi chú dài không chia đoạn).
- Không đánh giá dựa trên việc tài liệu CÓ dùng từ "chương" hay không — chỉ đánh giá dựa trên việc nó
  CÓ hay KHÔNG có một trình tự nội dung rõ ràng, tuần tự, có thể chia giai đoạn học được.

Lưu ý quan trọng:
- suggested_goals phải đặc trưng cho môn học này, KHÔNG phải câu chung chung"""

    try:
        raw = await _call_llm_with_fallback(
            prompt, gemini_api_keys, llm_api_keys, llm_base_url, llm_model, timeout=45.0
        )
        data = _parse_json_safely(raw)

        is_learning = bool(data.get("is_learning_doc", True))
        not_learning_reason = data.get("not_learning_reason", "")
        is_code_related = bool(data.get("is_code_related", False)) or is_code_related_quick
        has_clear_structure = bool(data.get("has_clear_structure", False))

        return {
            "is_learning_doc": is_learning,
            "subject": data.get("subject", "Tài liệu học tập"),
            "topics": data.get("topics", []),
            "suggested_goals": data.get("suggested_goals", [
                "Nắm vững kiến thức cơ bản",
                "Ôn tập và hệ thống hóa",
                "Chuẩn bị cho kỳ thi",
            ]),
            "content_summary": data.get("content_summary", ""),
            "is_code_related": is_code_related,
            "raw_text": raw_text,
            "ocr_engine": ocr_engine,
            "not_learning_message": (
                not_learning_reason
                if not is_learning
                else None
            ),
            "document_level": data.get("document_level"),
            "has_clear_structure": has_clear_structure,
            "structure_reason": data.get("structure_reason") or None,
            "reading_time": estimate_reading_time(raw_text),
        }
    except Exception as e:
        logger.warning(f"Document analysis AI failed: {e}, using fallback")
        return {
            "is_learning_doc": True,
            "subject": "Tài liệu học tập",
            "topics": [],
            "suggested_goals": [
                "Nắm vững kiến thức cơ bản",
                "Ôn tập và hệ thống hóa kiến thức",
                "Chuẩn bị cho kỳ thi",
                "Luyện tập nâng cao",
            ],
            "content_summary": raw_text[:200] + "...",
            "is_code_related": is_code_related_quick,
            "raw_text": raw_text,
            "ocr_engine": ocr_engine,
            "not_learning_message": None,
            "document_level": None,
            "has_clear_structure": True,
            "structure_reason": None,
            "reading_time": estimate_reading_time(raw_text),
        }


# ---------------------------------------------------------------------------
# Quiz Generation (Luồng 1 — Bước 3)
# ---------------------------------------------------------------------------

async def generate_diagnostic_quiz(
    subject: str,
    document_text: str,
    selected_goal: str,
    user_level_info: str,
    gemini_api_keys: list[str],
    llm_api_keys: list[str],
    llm_base_url: str,
    llm_model: str,
) -> dict[str, Any]:
    """
    Sinh 7 câu hỏi trắc nghiệm diagnostic: 3 câu tiên quyết, 4 câu trọng tâm tài liệu.
    """
    prompt = f"""Bạn là giáo viên chuyên nghiệp môn {subject}.

TRÌNH ĐỘ HỌC VIÊN: {user_level_info}
MỤC TIÊU HỌC TẬP CỦA HỌC VIÊN: {selected_goal}

NỘI DUNG TÀI LIỆU (trích xuất từ file người dùng upload):
---
{document_text[:6000]}
---

NHIỆM VỤ: Tạo CHÍNH XÁC 7 câu hỏi trắc nghiệm để kiểm tra năng lực, chia làm 2 phần:
- 3 câu đầu tiên: Kiểm tra KIẾN THỨC NỀN TẢNG cần có để hiểu tài liệu này. Nó là nhóm kiến thức tiên quyết, muốn học được tài liệu này trước tiên phải biết đến nó đã.
- 4 câu tiếp theo: Kiểm tra NỘI DUNG TRỌNG TÂM cụ thể của tài liệu trên. Mức độ khó tăng dần từ cơ bản đến vận dụng cao.

YÊU CẦU BẮT BUỘC:
- Tất cả 7 câu đều PHẢI xoay quanh nội dung cụ thể trong tài liệu đã cung cấp bên trên. Không được tự đặt ra câu hỏi không có liên quan đến tài liệu.
- Giải thích câu trả lời PHẢI dẫn chiếu trực tiếp vào nội dung tài liệu (trích dẫn đoạn cụ thể nếu là tài liệu dạng lý thuyết).
- Phân bố độ khó: 40% dễ, 40% trung bình, 20% khó
- Mỗi câu có 4 đáp án A/B/C/D, chỉ 1 đúng
- Giải thích ngắn gọn tại sao đáp án đúng
- QUAN TRỌNG: Mọi công thức Toán học, Vật lý, Hóa học hoặc các ký hiệu đặc biệt (phân số, số mũ, căn bậc, hệ phương trình...) ĐỀU PHẢI được định dạng theo chuẩn LaTeX, bọc trong cặp dấu $...$ (inline) hoặc $$...$$ (block).
- RẤT QUAN TRỌNG VỀ JSON: Vì kết quả trả về là JSON, bạn PHẢI sử dụng HAI DẤU GẠCH CHÉO cho các lệnh LaTeX để tránh lỗi parse JSON. (Ví dụ: Dùng `\\\\frac` thay vì `\\frac`, dùng `\\\\sqrt` thay vì `\\sqrt`, dùng `a^2` thì không cần gạch chéo). Lỗi JSON escape sẽ làm hỏng toàn bộ hệ thống!

Trả về JSON (chỉ JSON):
{{
  "topic_summary": "Tóm tắt 1 câu về phạm vi kiến thức được kiểm tra",
  "quiz": [
    {{
      "id": 1,
      "question": "Câu hỏi cụ thể dựa trên nội dung tài liệu?",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct": "A",
      "explanation": "Vì... (dẫn chiếu vào nội dung tài liệu)",
      "difficulty": "easy|medium|hard",
      "topic": "Tên khái niệm/phần trong tài liệu câu hỏi này thuộc về"
    }}
  ]
}}"""

    try:
        raw = await _call_llm_with_fallback(
            prompt, gemini_api_keys, llm_api_keys, llm_base_url, llm_model, timeout=60.0
        )
        return _parse_json_safely(raw)
    except Exception as e:
        logger.warning(f"Quiz generation failed: {e}")
        return {"quiz": [], "topic_summary": ""}


# ---------------------------------------------------------------------------
# AI Recommendation cho đề thi (Luồng 2)
# ---------------------------------------------------------------------------

async def get_ai_recommendation_groq(
    questions: list[Any],
    score_ratio: float | None,
    weak_areas: str | None,
    gemini_api_keys: list[str],
    llm_api_keys: list[str],
    base_url: str,
    model: str,
) -> dict[str, Any]:
    """Phân tích câu hỏi đề thi + điểm số bằng Groq LLM."""
    score_context = ""
    if score_ratio is not None:
        pct = int(score_ratio * 100)
        note = "" if score_ratio >= 0.7 else " — THẤP, cần chú ý đặc biệt"
        score_context = f"\nĐIỂM SỐ: Học sinh đạt {pct}%{note}."
    if weak_areas:
        score_context += f"\nHỌC SINH TỰ NHẬN XÉT ĐIỂM YẾU: {weak_areas}"

    # Determine mode based on question format
    is_post_exam = len(questions) > 0 and isinstance(questions[0], dict)
    
    questions_text = ""
    if is_post_exam:
        for q in questions[:20]:
            q_id = q.get("id", "Câu")
            q_content = q.get("content", "")[:300]
            q_level = q.get("level", "")
            questions_text += f"- [{q_id}] (Mức độ hỗ trợ: {q_level}): {q_content}\n"
    else:
        questions_text = "\n".join(f"- {q}" for q in questions[:20])

    if is_post_exam:
        prompt = f"""Bạn là chuyên gia phân tích năng lực học tập.{score_context}

NHIỆM VỤ: Phân loại các câu hỏi dưới đây theo 3 nhóm mức độ (cơ bản, vận dụng, vận dụng cao) và đưa ra lời khuyên cá nhân hóa dựa trên mức độ hỗ trợ mà học sinh yêu cầu.
Chú ý KHÔNG giải bài, KHÔNG cho đáp án trực tiếp.

QUY TẮC XỬ LÝ MỨC ĐỘ HỖ TRỢ (RẤT QUAN TRỌNG):
Học sinh đã chọn 1 trong 3 mức độ cho từng câu:
1. "Không biết làm": Nếu là câu dễ, hãy hướng dẫn chi tiết cách tiếp cận. Nếu là câu khó, hãy thẳng thắn báo rằng câu này cần tích lũy lâu dài, đưa ra cách giải sơ sài, và sinh ra một phần "mini_test_and_roadmap" (gồm 2-3 câu hỏi siêu nền tảng + lộ trình ngắn) để test xem họ có lủng kiến thức cơ bản không. CHÚ Ý: Nếu học sinh chọn "Không biết làm" cho câu dễ nhưng "Sắp làm được" cho câu khó, đây là mâu thuẫn, hãy tự động coi câu dễ đó như ở mức 2.
2. "Hiểu đề nhưng không biết bắt đầu từ đâu": Đưa ra mức độ câu hỏi, nhóm kiến thức, mẹo giải, nên chú ý điểm nào, khai thác từ đâu, lỗi cần tránh.
3. "Sắp làm được rồi nhưng vẫn còn thiếu một chút": Đưa ra mức độ, nhóm kiến thức, cách giải/điểm chốt hạ, và bẫy khiến thí sinh làm sai.

Câu hỏi và mức độ yêu cầu:
{questions_text}

Trả về JSON đúng cấu trúc sau (chỉ JSON):
{{
  "nhom_co_ban": {{
    "loi_khuyen_chung": "Nhận xét tổng quan nhóm câu",
    "chi_tiet_tung_cau": [
      {{
        "id_cau": "Câu I",
        "kien_thuc_can_hoc": "Tên kiến thức",
        "loi_khuyen_ngan": "Phân tích, Mẹo, Điểm chốt hoặc Bẫy (tùy mức độ hỗ trợ)",
        "mini_test_and_roadmap": "Chỉ có nếu rơi vào trường hợp (Không biết làm + Câu khó). Nêu 2-3 câu hỏi nền tảng và cách ôn tập. Nếu không, để trống chuỗi này."
      }}
    ]
  }},
  "nhom_van_dung": {{
    "loi_khuyen_chung": "...",
    "chi_tiet_tung_cau": []
  }},
  "nhom_van_dung_cao": {{
    "loi_khuyen_chung": "...",
    "chi_tiet_tung_cau": []
  }},
  "tom_tat_tong_quat": "2-3 câu nhận xét tổng thể",
  "_goal": "Tên môn học (Ví dụ: Toán, Vật Lý, Hóa Học, Sinh Học...)"
}}"""
    else:
        prompt = f"""Bạn là chuyên gia phân tích năng lực học tập.{score_context}

NHIỆM VỤ: Phân loại các câu hỏi dưới đây theo 3 nhóm mức độ và đưa ra lời khuyên. KHÔNG giải bài, KHÔNG cho đáp án.

Câu hỏi:
{questions_text}

Trả về JSON đúng cấu trúc sau (chỉ JSON):
{{
  "nhom_co_ban": {{
    "loi_khuyen_chung": "Nhận xét tổng quan nhóm câu mức nhận biết/thông hiểu và hướng dẫn ôn tập",
    "chi_tiet_tung_cau": [
      {{"id_cau": "Câu I", "kien_thuc_can_hoc": "Tên kiến thức cần nắm", "loi_khuyen_ngan": "Cách tiếp cận và gợi ý học"}}
    ]
  }},
  "nhom_van_dung": {{
    "loi_khuyen_chung": "...",
    "chi_tiet_tung_cau": []
  }},
  "nhom_van_dung_cao": {{
    "loi_khuyen_chung": "...",
    "chi_tiet_tung_cau": []
  }},
  "tom_tat_tong_quat": "2-3 câu nhận xét tổng thể và ưu tiên ôn tập"
}}"""

    try:
        raw = await _call_llm_with_fallback(
            prompt, gemini_api_keys, llm_api_keys, base_url, model, timeout=60.0
        )
        return _parse_json_safely(raw)
    except Exception as e:
        logger.warning(f"AI recommendation failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Exam OCR + Parse pipeline (Luồng 2)
# ---------------------------------------------------------------------------

async def ocr_and_parse(
    file_bytes: bytes,
    filename: str,
    gemini_api_keys: list[str],
) -> dict[str, Any]:
    """OCR + parse đề thi. Trả về kết quả parse."""
    raw_text, ocr_engine = await extract_text_from_file(
        file_bytes, filename, gemini_api_keys
    )
    result = parse_exam_questions(raw_text)
    result["ocr_engine"] = ocr_engine
    result["filename"] = filename
    return result


# ---------------------------------------------------------------------------
# Resource Crawlers (Smart version)
# ---------------------------------------------------------------------------

def _extract_search_terms(text: str) -> str:
    clean = re.sub(r"\$\$[\s\S]*?\$\$", "", text)
    clean = re.sub(r"\$[^$\n]+?\$", "", clean)
    clean = re.sub(r"^(Câu|Bài)\s+[IVXLCDM0-9]+[:\.]?", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^[0-9]+[\.]?\s*", "", clean)
    clean = re.sub(r"[#\*_\`]", " ", clean)
    lines = [l.strip() for l in clean.split("\n") if l.strip()]
    result = re.sub(r"\s+", " ", " ".join(lines)).strip()
    return result[:120] if result else text[:120]


def _search_youtube(query: str, limit: int = 3) -> list:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if api_key:
        try:
            params = urllib.parse.urlencode({
                "part": "snippet", "q": query + " học tập giảng dạy",
                "type": "video", "maxResults": limit,
                "order": "relevance", "key": api_key,
                "relevanceLanguage": "vi",
            })
            req = urllib.request.Request(
                f"https://www.googleapis.com/youtube/v3/search?{params}",
                headers={"User-Agent": "PLSystem/1.0", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return [
                {
                    "title": item["snippet"].get("title", ""),
                    "video_id": item["id"].get("videoId", ""),
                    "thumbnail_url": item["snippet"].get("thumbnails", {}).get("medium", {}).get("url", ""),
                    "channel_title": item["snippet"].get("channelTitle", ""),
                    "watch_url": f"https://www.youtube.com/watch?v={item['id'].get('videoId', '')}",
                }
                for item in data.get("items", [])[:limit]
                if item.get("id", {}).get("videoId")
            ]
        except Exception:
            pass

    # Scraper fallback
    try:
        encoded = urllib.parse.quote_plus(query + " bài giảng học")
        req = urllib.request.Request(
            f"https://www.youtube.com/results?search_query={encoded}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "vi,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
        match = re.search(r"var ytInitialData = ({.+?});</script>", html, re.DOTALL)
        if not match:
            return []
        yt_data = json.loads(match.group(1))
        contents = (
            yt_data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )
        videos = []
        for section in contents:
            for item in section.get("itemSectionRenderer", {}).get("contents", []):
                vr = item.get("videoRenderer")
                if not vr:
                    continue
                video_id = vr.get("videoId", "")
                if not video_id:
                    continue
                title_runs = vr.get("title", {}).get("runs", [])
                thumbnails = vr.get("thumbnail", {}).get("thumbnails", [])
                channel_runs = vr.get("ownerText", {}).get("runs", []) or vr.get("longBylineText", {}).get("runs", [])
                videos.append({
                    "title": title_runs[0].get("text", "") if title_runs else "",
                    "video_id": video_id,
                    "thumbnail_url": thumbnails[-1].get("url", "") if thumbnails else "",
                    "channel_title": channel_runs[0].get("text", "") if channel_runs else "",
                    "watch_url": f"https://www.youtube.com/watch?v={video_id}",
                })
                if len(videos) >= limit:
                    break
            if len(videos) >= limit:
                break
        return videos
    except Exception:
        return []


def _search_web_exercises(query: str, limit: int = 4) -> list:
    """Tìm bài tập và tài liệu tham khảo qua DuckDuckGo."""
    try:
        from bs4 import BeautifulSoup  # type: ignore[import]
        search_query = query + " bài tập luyện tập bài giải"
        encoded = urllib.parse.quote_plus(search_query)
        req = urllib.request.Request(
            f"https://html.duckduckgo.com/html/?q={encoded}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "vi,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            soup = BeautifulSoup(resp.read().decode("utf-8"), "html.parser")
        results = []
        for result in soup.find_all("div", class_="result"):
            title_tag = result.find("h2", class_="result__title")
            snippet_tag = result.find("a", class_="result__snippet")
            url_tag = result.find("a", class_="result__url")
            if title_tag and url_tag:
                link = url_tag.get("href", "")
                if link.startswith("//duckduckgo.com/l/?uddg="):
                    link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                results.append({
                    "title": title_tag.get_text(separator=" ", strip=True),
                    "url": link,
                    "snippet": snippet_tag.get_text(separator=" ", strip=True) if snippet_tag else "",
                })
                if len(results) >= limit:
                    break
        return results
    except Exception:
        return []


def _search_github(query: str, limit: int = 3) -> list:
    """Chỉ gọi khi topic liên quan lập trình."""
    try:
        params = urllib.parse.urlencode({
            "q": query, "sort": "stars", "order": "desc", "per_page": min(limit, 5),
        })
        headers = {
            "User-Agent": "PLSystem/1.0",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.getenv("GITHUB_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(
            f"https://api.github.com/search/repositories?{params}", headers=headers
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [
            {
                "full_name": item.get("full_name", ""),
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language"),
                "description": (item.get("description") or "")[:200],
                "url": item.get("html_url", ""),
            }
            for item in data.get("items", [])[:limit]
        ]
    except Exception:
        return []


async def crawl_resources_smart(query: str, is_code_related: bool = False) -> dict[str, Any]:
    """
    Crawl tài nguyên thông minh:
    - Luôn crawl: YouTube + Web exercises
    - Chỉ crawl GitHub khi is_code_related=True
    """
    search_query = _extract_search_terms(query)
    loop = asyncio.get_running_loop()

    tasks = [
        loop.run_in_executor(_executor, _search_youtube, search_query, 3),
        loop.run_in_executor(_executor, _search_web_exercises, search_query, 4),
    ]
    if is_code_related:
        tasks.append(loop.run_in_executor(_executor, _search_github, search_query, 3))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    youtube_res = results[0] if isinstance(results[0], list) else []
    web_res = results[1] if isinstance(results[1], list) else []
    github_res = results[2] if len(results) > 2 and isinstance(results[2], list) else []

    return {
        "search_query": search_query,
        "youtube_tutorials": youtube_res,
        "quiz_exercises": web_res,
        "github_repos": github_res,
        "is_code_related": is_code_related,
    }


# Backward compat alias
async def crawl_resources(query: str) -> dict[str, Any]:
    return await crawl_resources_smart(query, is_code_related=False)


# ---------------------------------------------------------------------------
# Roadmap Generator (Inline Roadmap — sinh lộ trình học tập)
# ---------------------------------------------------------------------------

def _next_study_date(current: date, days_per_week: int) -> date:
    """Ngày học kế tiếp — quy ước: days_per_week=N nghĩa là N ngày đầu tuần (Thứ 2..) là ngày học,
    giống hệt quy ước đã dùng trong roadmap_planner.py để nhất quán trong toàn hệ thống."""
    allowed_weekdays = set(range(max(1, min(7, days_per_week))))
    candidate = current
    while candidate.weekday() not in allowed_weekdays:
        candidate += timedelta(days=1)
    return candidate


def _schedule_roadmap_days(
    phases: list[dict],
    minutes_per_day: int,
    days_per_week: int,
    start_date: date,
) -> tuple[list[dict], date]:
    """Xếp từng chủ đề (đã có estimated_minutes từ LLM) vào các ngày học cụ thể — xác định 100%
    bằng toán, KHÔNG dùng LLM để đoán tuần/ngày. Trả về (phases đã gắn "days", ngày kết thúc thực tế)."""
    current_date = _next_study_date(start_date, days_per_week)
    minutes_left_today = minutes_per_day
    day_number = 1
    scheduled_phases: list[dict] = []

    for phase in phases:
        raw_topics = phase.get("topics", [])
        days_map: dict[str, dict] = {}
        day_order: list[str] = []

        for raw_topic in raw_topics:
            if isinstance(raw_topic, dict):
                title = str(raw_topic.get("title", "")).strip()
                why = str(raw_topic.get("why", "")).strip()
                activities = str(raw_topic.get("activities", "")).strip()
                try:
                    remaining = max(10, int(raw_topic.get("estimated_minutes", 30)))
                except (TypeError, ValueError):
                    remaining = 30
            else:
                title, why, activities, remaining = str(raw_topic), "", "", 30
            if not title:
                continue

            while remaining > 0:
                if minutes_left_today <= 0:
                    day_number += 1
                    current_date = _next_study_date(current_date + timedelta(days=1), days_per_week)
                    minutes_left_today = minutes_per_day

                date_iso = current_date.isoformat()
                if date_iso not in days_map:
                    days_map[date_iso] = {"day_number": day_number, "date": date_iso, "topics": [], "total_minutes": 0}
                    day_order.append(date_iso)

                chunk = min(remaining, minutes_left_today)
                days_map[date_iso]["topics"].append({"title": title, "why": why, "activities": activities, "minutes": chunk})
                days_map[date_iso]["total_minutes"] += chunk
                remaining -= chunk
                minutes_left_today -= chunk

        scheduled_phases.append({
            **{k: v for k, v in phase.items() if k != "topics"},
            "days": [days_map[d] for d in day_order],
        })

    return scheduled_phases, current_date


def _candidate_study_dates(start_date: date, days_per_week: int, count: int) -> list[date]:
    """Danh sách N ngày học hợp lệ kế tiếp — thuần cơ học lịch (ngày nào là ngày học theo
    days_per_week), KHÔNG mang tính cá nhân hóa nên tính bằng code; LLM chỉ chọn xếp nội dung gì
    vào ngày nào trong số ứng viên này, không tự tính lịch (tránh LLM tính sai ngày tháng)."""
    dates: list[date] = []
    current = _next_study_date(start_date, days_per_week)
    while len(dates) < count:
        dates.append(current)
        current = _next_study_date(current + timedelta(days=1), days_per_week)
    return dates


_WEEKDAY_NAMES_VI = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


async def _schedule_phase_days_llm(
    phase: dict,
    subject: str,
    candidate_dates: list[date],
    minutes_per_day: int,
    reading_time: dict | None,
    gemini_api_keys: list[str],
    llm_api_keys: list[str],
    llm_base_url: str,
    llm_model: str,
) -> list[dict] | None:
    """Lớp 2: để CHÍNH LLM quyết định lịch học từng ngày cho MỘT giai đoạn — không xếp cứng bằng
    thuật toán bin-packing vì như vậy sẽ mất tính cá nhân hóa (thời gian mỗi ngày co giãn theo độ
    khó, không cố định bằng đúng minutes_per_day). Trả về None nếu LLM lỗi/không parse được, để
    hàm gọi tự chuyển sang xếp lịch dự phòng bằng thuật toán cho riêng giai đoạn đó."""
    topics = phase.get("topics", [])
    if not topics:
        return []

    topics_str = "\n".join(
        f"- {t.get('title', '')}: {t.get('why', '')} (ước lượng tổng ~{t.get('estimated_minutes', 30)} phút, gợi ý hoạt động: {t.get('activities', '')})"
        for t in topics if isinstance(t, dict) and t.get("title")
    )
    candidates_str = "\n".join(
        f"{i + 1}. {d.isoformat()} ({_WEEKDAY_NAMES_VI[d.weekday()]})"
        for i, d in enumerate(candidate_dates)
    )
    reading_context = ""
    if reading_time:
        lo = reading_time.get("deep_study_minutes_min", 0)
        hi = reading_time.get("deep_study_minutes_max", 0)
        if lo or hi:
            reading_context = (
                f"\nTHAM KHẢO CHUNG (số liệu thống kê trung bình, CHƯA cá nhân hóa): trung bình một "
                f"người cần khoảng {lo}-{hi} phút để học sâu (đọc + ghi chú + làm bài tập) toàn bộ tài "
                f"liệu gốc. Đây chỉ là mốc tham chiếu — hãy CÂN NHẮC thực tế của giai đoạn này (có phần "
                f"khó/dễ khác nhau, người học có thể đang hổng kiến thức ở đây) để phân bổ hợp lý, KHÔNG "
                f"áp dụng máy móc.\n"
            )

    prompt = f"""Bạn là chuyên gia giáo dục AI, lên lịch học CHI TIẾT TỪNG NGÀY cho MỘT giai đoạn
trong lộ trình học tập cá nhân hóa. Đây là bước quan trọng nhất để lộ trình thực sự "cá nhân hóa
đến cực điểm" — đừng làm qua loa, đừng lặp lại công thức giống nhau giữa các ngày.

MÔN HỌC: {subject}
GIAI ĐOẠN: {phase.get('title', '')}
VÌ SAO GIAI ĐOẠN NÀY: {phase.get('why', '')}
{reading_context}
CÁC CHỦ ĐỀ CẦN XẾP LỊCH (theo đúng thứ tự; ước lượng phút TỔNG CỘNG và gợi ý hoạt động chỉ là điểm
khởi đầu, bạn có thể điều chỉnh theo đánh giá thực tế của bạn về độ khó):
{topics_str}

NHỊP HỌC TRUNG BÌNH NGƯỜI DÙNG ĐẶT: {minutes_per_day} phút/ngày — đây là con số TRUNG BÌNH THAM
KHẢO, KHÔNG PHẢI giới hạn cứng cho từng ngày riêng lẻ. Ngày học nội dung khó/nặng, cần tập trung cao
độ, HÃY DÀNH NHIỀU THỜI GIAN HƠN mức trung bình (có thể vượt, nhưng đừng vượt quá lố — khoảng tối đa
~1.5 lần); ngày học nội dung nhẹ/ôn tập thì có thể ÍT HƠN. Tổng thể xoay vòng quanh mức trung bình
trong cả giai đoạn, không áp cứng đúng con số đó cho mọi ngày.

DANH SÁCH NGÀY HỌC HỢP LỆ (CHỈ được dùng các ngày có trong danh sách này, theo ĐÚNG THỨ TỰ xuất
hiện, không bắt buộc dùng hết — dừng lại ngay khi đã xếp xong toàn bộ nội dung giai đoạn):
{candidates_str}

YÊU CẦU BẮT BUỘC:
1. Mỗi ngày PHẢI có "note" — nhận xét/ghi chú NGẮN GỌN, RIÊNG BIỆT cho đúng ngày đó (nhịp học, độ
   khó, tâm lý cần chuẩn bị, mối liên hệ với ngày trước...). TUYỆT ĐỐI không lặp lại y nguyên một
   câu note ở nhiều ngày khác nhau.
2. Mỗi chủ đề trong ngày PHẢI có "location_hint": vị trí ước lượng của nội dung này trong tài liệu
   gốc (VD: "đầu tài liệu", "khoảng giữa, ngay sau phần X", "gần cuối tài liệu") để người học mở
   đúng chỗ trong tài liệu ra xem lại.
3. Mỗi chủ đề PHẢI có "resource_type": "video" (nên tìm video bài giảng ngoài), "exercise" (ngày
   luyện bài tập, nên tìm thêm bài tập), "reading" (chỉ cần đọc tài liệu, không cần tài nguyên
   ngoài), hoặc "mixed".
4. Một chủ đề có thể trải dài nhiều ngày liên tiếp nếu nội dung nhiều — mỗi ngày ghi rõ phần nào
   của chủ đề đó đang được học (VD ngày 1: khái niệm cơ bản; ngày 2: bài tập vận dụng).

Trả về JSON (chỉ JSON, không markdown):
{{
  "days": [
    {{
      "date": "YYYY-MM-DD (CHỈ phần ngày tháng năm, KHÔNG kèm tên thứ hay chữ nào khác — lấy đúng 10 ký tự từ danh sách ngày hợp lệ ở trên)",
      "note": "Nhận xét riêng cho ngày này",
      "topics": [
        {{"title": "...", "why": "...", "activities": "...", "minutes": 60, "resource_type": "video", "location_hint": "..."}}
      ]
    }}
  ]
}}"""

    raw = await _call_llm_with_fallback(
        prompt, gemini_api_keys, llm_api_keys, llm_base_url, llm_model, timeout=75.0
    )
    result = _parse_json_safely(raw)
    raw_days = result.get("days")
    if not raw_days:
        return None

    candidate_set = {d.isoformat() for d in candidate_dates}
    seen_dates: set[str] = set()
    cleaned_days: list[dict] = []
    for d in raw_days:
        if not isinstance(d, dict):
            continue
        # LLM đôi khi kèm thêm thứ trong ngày (VD "2026-08-19 (Thứ Tư)") dù đã dặn chỉ lấy nguyên
        # văn ngày — trích riêng phần YYYY-MM-DD cho khoan dung thay vì so khớp chuỗi tuyệt đối.
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", str(d.get("date", "")))
        date_str = date_match.group(0) if date_match else ""
        if date_str not in candidate_set or date_str in seen_dates:
            continue
        seen_dates.add(date_str)

        day_topics = []
        for t in d.get("topics", []):
            if not isinstance(t, dict) or not str(t.get("title", "")).strip():
                continue
            try:
                minutes = max(5, int(t.get("minutes", 30)))
            except (TypeError, ValueError):
                minutes = 30
            resource_type = t.get("resource_type")
            if resource_type not in ("video", "exercise", "reading", "mixed"):
                resource_type = "mixed"
            day_topics.append({
                "title": str(t.get("title", "")).strip(),
                "why": str(t.get("why", "")).strip(),
                "activities": str(t.get("activities", "")).strip(),
                "minutes": minutes,
                "resource_type": resource_type,
                "location_hint": str(t.get("location_hint", "")).strip(),
            })
        if not day_topics:
            continue
        cleaned_days.append({
            "date": date_str,
            "note": str(d.get("note", "")).strip(),
            "topics": day_topics,
            "total_minutes": sum(t["minutes"] for t in day_topics),
        })

    cleaned_days.sort(key=lambda x: x["date"])
    return cleaned_days or None


async def generate_learning_roadmap(
    subject: str,
    weak_topics: list[str],
    selected_goal: str,
    score_ratio: float | None,
    minutes_per_day: int,
    quick_quiz_results_str: str | None,
    gemini_api_keys: list[str],
    llm_api_keys: list[str],
    llm_base_url: str,
    llm_model: str,
    learned_topics: list[str] | None = None,
    days_per_week: int = 7,
    evidence_summary: str | None = None,
    curriculum_position: dict | None = None,  # {"topic": str, "on_track": bool}
    deadline: str | None = None,  # ISO date YYYY-MM-DD
    start_date: str | None = None,  # ISO date YYYY-MM-DD — mặc định hôm nay nếu không cung cấp
    reading_time: dict | None = None,  # Kết quả estimate_reading_time() ở bước phân tích tài liệu
) -> dict[str, Any]:
    """
    Sinh lộ trình học tập theo 2 lớp, cả 2 đều do LLM quyết định nội dung cá nhân hóa:
      1. LLM lên KHUNG (giai đoạn → chủ đề, kèm lý do/tiên quyết + ước lượng phút cần cho mỗi chủ
         đề). Giữ output gọn (không liệt kê từng ngày ở bước này) để tránh context quá dài khiến
         LLM trả lời qua loa.
      2. Với TỪNG giai đoạn, gọi riêng LLM một lần nữa để lên lịch CHI TIẾT TỪNG NGÀY — thời gian
         mỗi ngày co giãn theo độ khó thực tế (không xếp cứng bằng thuật toán, vì như vậy sẽ mất
         tính cá nhân hóa). Ngày tháng cụ thể vẫn được tính bằng code (thuần cơ học lịch, không
         mang tính cá nhân hóa) để tránh LLM tính sai ngày — LLM chỉ quyết định NỘI DUNG của từng
         ngày trong số các ngày hợp lệ được cung cấp.
    Nếu bước lên lịch chi tiết của một giai đoạn bị lỗi, giai đoạn đó (và chỉ giai đoạn đó) sẽ dùng
    lịch dự phòng xếp bằng thuật toán, để không làm hỏng toàn bộ lộ trình.
    """
    level_hint = ""
    if score_ratio is not None:
        if score_ratio >= 0.8:
            level_hint = "Học sinh có nền tảng tốt, cần nâng cao và mở rộng."
        elif score_ratio >= 0.5:
            level_hint = "Học sinh cần củng cố một số phần còn yếu."
        else:
            level_hint = "Học sinh cần xây dựng lại từ nền tảng."
    else:
        level_hint = "Học sinh mới bắt đầu tiếp cận môn học."

    weak_topics_str = ", ".join(weak_topics[:15]) if weak_topics else "các kiến thức cơ bản"
    learned_topics_str = ", ".join(learned_topics[:15]) if learned_topics else "Chưa có"

    quiz_context = ""
    if quick_quiz_results_str:
        quiz_context = f"KẾT QUẢ QUICK TEST GẦN NHẤT:\n{quick_quiz_results_str}\n(Lưu ý: Nếu kết quả báo sai nhiều ở các câu tiên quyết/cơ bản, HÃY thêm ngay giai đoạn ôn tập kiến thức nền tảng trước. Nếu đúng gần hết, có thể rút ngắn thời gian các chủ đề đó.)\n"

    evidence_context = f"MINH CHỨNG NĂNG LỰC BỔ SUNG: {evidence_summary}\n" if evidence_summary else ""

    position_context = ""
    if curriculum_position and curriculum_position.get("topic"):
        pos_topic = curriculum_position["topic"]
        on_track = curriculum_position.get("on_track", True)
        if on_track:
            position_context = (
                f"VỊ TRÍ HIỆN TẠI TRONG CHƯƠNG TRÌNH: Người học tự xác nhận đã học vững đến "
                f"'{pos_topic}' (đúng theo tiến độ).\n"
            )
        else:
            position_context = (
                f"VỊ TRÍ HIỆN TẠI TRONG CHƯƠNG TRÌNH: Trường/chương trình đã dạy đến '{pos_topic}', "
                f"nhưng người học tự nhận là CHƯA nắm vững / có thể bị mất gốc ở khúc này. "
                f"PHẢI ưu tiên ôn lại từ trước mốc '{pos_topic}' trước khi học tiếp phần sau.\n"
            )

    days_available: int | None = None
    deadline_date: date | None = None
    if deadline:
        try:
            deadline_date = date.fromisoformat(deadline.strip())
            days_available = max(1, (deadline_date - date.today()).days)
        except Exception:
            days_available = None
    budget_minutes = (
        (days_available // 7 * days_per_week + min(days_per_week, days_available % 7)) * minutes_per_day
        if days_available is not None
        else None
    )
    deadline_context = (
        f"THỜI HẠN MỤC TIÊU: {deadline} (còn khoảng {days_available} ngày, ước tính tổng quỹ thời "
        f"gian khả dụng ~{budget_minutes} phút với nhịp học {minutes_per_day} phút/ngày, "
        f"{days_per_week} ngày/tuần)\n"
        if days_available is not None
        else ""
    )

    reading_time_context = ""
    if reading_time:
        lo = reading_time.get("deep_study_minutes_min", 0)
        hi = reading_time.get("deep_study_minutes_max", 0)
        if lo or hi:
            reading_time_context = (
                f"THAM KHẢO CHUNG (thống kê trung bình, CHƯA cá nhân hóa): tài liệu này có khoảng "
                f"{reading_time.get('word_count', 0)} từ; một người trung bình cần khoảng {lo}-{hi} "
                f"phút (~{round(lo / 60, 1)}-{round(hi / 60, 1)} giờ) để HỌC SÂU (đọc + ghi chú + làm "
                f"bài tập) toàn bộ tài liệu gốc. Đây chỉ là mốc tham chiếu khởi điểm — hãy dùng nó để "
                f"PHÁT HIỆN LỆCH PHA: nếu quỹ thời gian người dùng cho lớn hơn NHIỀU so với mốc này, "
                f"tài liệu có thể khá ngắn so với thời gian họ dành ra — hãy đặt \"pacing_note\" gợi ý "
                f"dùng thời gian dư để đào sâu/mở rộng/luyện tập thêm thay vì để trống lãng phí; nếu quỹ "
                f"thời gian nhỏ hơn nhiều, đây là dấu hiệu cảnh báo về tính khả thi.\n"
            )

    prompt = f"""Bạn là chuyên gia giáo dục AI, thiết kế khung lộ trình học tập CÁ NHÂN HÓA ĐẾN CỰC
ĐIỂM — không đưa ra lộ trình chung chung mà phải phản ánh đúng tình trạng riêng của người học này.

MÔN HỌC: {subject}
MỤC TIÊU CỦA NGƯỜI HỌC: {selected_goal}
ĐÁNH GIÁ NĂNG LỰC: {level_hint}
{quiz_context}{evidence_context}{position_context}{deadline_context}{reading_time_context}CHƯƠNG/CHỦ ĐỀ ĐÃ HỌC (KHÔNG đưa vào lộ trình): {learned_topics_str}
CHƯƠNG/CHỦ ĐỀ CẦN HỌC (theo đúng thứ tự trong tài liệu): {weak_topics_str}
NHỊP HỌC: {minutes_per_day} phút/ngày (trung bình tham khảo), {days_per_week} ngày/tuần

NHIỆM VỤ: Lên KHUNG lộ trình chia thành các giai đoạn (KHÔNG cố định số lượng — có thể 1, 2, 5,
hay bao nhiêu giai đoạn tùy nội dung thực tế, đừng gò ép về đúng 3 giai đoạn). Với mỗi giai đoạn,
liệt kê các chủ đề con theo ĐÚNG thứ tự cần học. Với mỗi chủ đề, PHẢI có:
- "why": giải thích NGẮN GỌN, CỤ THỂ vì sao cần học chủ đề này ở đây — nếu nó là kiến thức tiên
  quyết cho chủ đề khác, hãy nói rõ "cần nắm vững X thì mới học được Y vì...". Nếu đây là phần
  người học đang bị hổng (theo quick test / vị trí đã tick / minh chứng), hãy nói rõ lý do đó — còn
  phần nào người học đã thể hiện tốt (VD: quick test đúng, minh chứng điểm cao) thì rút ngắn/lướt
  nhanh, đừng phân bổ thời gian dàn đều một cách máy móc cho mọi chủ đề.
- "estimated_minutes": số phút ước lượng CẦN THIẾT để CHÍNH người học này (không phải người trung
  bình) học vững chủ đề này — dựa trên độ khó/độ rộng thực tế của chủ đề VÀ tình trạng riêng (hổng ở
  đâu, vững ở đâu) đã mô tả bên trên. Bước lên lịch chi tiết từng ngày ở giai đoạn sau sẽ dựa vào
  ước lượng này, bạn KHÔNG cần tự chia ngày/tuần ở bước này.
- "activities": gợi ý ngắn hoạt động học cho chủ đề này (đọc lý thuyết, làm bài tập, ví dụ...).

QUAN TRỌNG VỀ TÍNH KHẢ THI: Thông tin thời hạn/nhịp học ở trên là NGỮ CẢNH tham khảo, KHÔNG PHẢI
mệnh lệnh tuyệt đối. Nếu tổng khối lượng kiến thức thực sự cần nhiều thời gian hơn quỹ thời gian
cho phép (ví dụ người dùng muốn học hết một quyển sách trong 1 ngày — điều này VÔ LÝ), bạn CÓ QUYỀN
từ chối tuân theo mù quáng: cứ ước lượng "estimated_minutes" trung thực theo đúng khối lượng kiến
thức thực tế, đặt "feasible": false, và trong "feasibility_note" giải thích rõ ràng, thẳng thắn tại
sao không khả thi và nên điều chỉnh gì (rút gọn nội dung nào, hoặc cần thêm bao nhiêu thời gian).
KHÔNG được cắt xén ước lượng thời gian một cách giả tạo chỉ để vừa khít thời hạn.

Trả về JSON (chỉ JSON, không markdown):
{{
  "overview": "Nhận xét thẳng thắn 2-3 câu về tình hình hiện tại và tổng quan lộ trình",
  "pacing_note": "Nếu phát hiện lệch pha giữa khối lượng tài liệu và quỹ thời gian (quá dư hoặc quá thiếu so với THAM KHẢO CHUNG), giải thích ở đây và đề xuất điều chỉnh. Để trống nếu nhịp độ hợp lý.",
  "feasible": true,
  "feasibility_note": "Chỉ điền khi feasible=false — giải thích cụ thể tại sao và nên làm gì",
  "phases": [
    {{
      "phase_number": 1,
      "title": "Tên giai đoạn (mô tả nội dung, KHÔNG phải chỉ 'Giai đoạn 1')",
      "why": "Vì sao giai đoạn này cần đứng ở vị trí này trong lộ trình",
      "topics": [
        {{"title": "Tên chủ đề", "why": "...", "estimated_minutes": 90, "activities": "..."}}
      ],
      "milestone": "Cột mốc/cách tự kiểm tra cuối giai đoạn",
      "search_query": "Cụm từ khóa tiếng Việt ngắn gọn, chính xác nhất để tìm video bài giảng/bài tập liên quan trực tiếp đến nội dung giai đoạn này (KHÔNG chung chung)"
    }}
  ]
}}"""

    start_date_obj = date.today()
    if start_date:
        try:
            start_date_obj = date.fromisoformat(start_date.strip())
        except Exception:
            start_date_obj = date.today()

    try:
        raw = await _call_llm_with_fallback(
            prompt, gemini_api_keys, llm_api_keys, llm_base_url, llm_model, timeout=75.0
        )
        result = _parse_json_safely(raw)
        phases = result.get("phases")
        if phases:
            # Lớp 2: với TỪNG giai đoạn, gọi riêng LLM lên lịch chi tiết từng ngày (tuần tự, vì
            # ngày bắt đầu của giai đoạn sau phụ thuộc ngày kết thúc thực tế của giai đoạn trước).
            cursor = _next_study_date(start_date_obj, days_per_week)
            assembled_phases: list[dict] = []
            global_day_counter = 0
            any_fallback_used = False

            for phase in phases:
                topics = phase.get("topics", [])
                total_minutes = sum(
                    (int(t.get("estimated_minutes", 30)) if isinstance(t, dict) else 30)
                    for t in topics
                ) if topics else 0
                # Đủ ngày ứng viên rộng rãi để LLM có không gian co giãn thời gian mỗi ngày
                candidate_count = max(15, min(60, int(total_minutes / max(10, minutes_per_day) * 1.6) + 5))
                candidate_dates = _candidate_study_dates(cursor, days_per_week, candidate_count)

                days: list[dict] | None = None
                try:
                    days = await _schedule_phase_days_llm(
                        phase, subject, candidate_dates, minutes_per_day, reading_time,
                        gemini_api_keys, llm_api_keys, llm_base_url, llm_model,
                    )
                except Exception as e:
                    logger.warning(f"Lớp 2 (lên lịch ngày) lỗi cho giai đoạn '{phase.get('title')}': {e}")

                if not days:
                    any_fallback_used = True
                    fb_phases, _ = _schedule_roadmap_days([phase], minutes_per_day, days_per_week, cursor)
                    days = fb_phases[0]["days"] if fb_phases else []

                for d in days:
                    global_day_counter += 1
                    d["day_number"] = global_day_counter

                assembled_phases.append({
                    **{k: v for k, v in phase.items() if k != "topics"},
                    "days": days,
                })

                if days:
                    last_date = date.fromisoformat(days[-1]["date"])
                    cursor = _next_study_date(last_date + timedelta(days=1), days_per_week)

            end_date = start_date_obj
            for p in reversed(assembled_phases):
                if p["days"]:
                    end_date = date.fromisoformat(p["days"][-1]["date"])
                    break

            feasible = bool(result.get("feasible", True))
            feasibility_note = str(result.get("feasibility_note") or "")
            pacing_note = str(result.get("pacing_note") or "")
            # Kiểm tra khả thi bằng toán thật, không chỉ tin lời LLM — nếu lịch xếp thực tế vượt hạn,
            # ép feasible=false và giải thích rõ bằng số liệu cụ thể (không im lặng cắt xén nội dung).
            if deadline_date and end_date > deadline_date:
                feasible = False
                overdue_days = (end_date - deadline_date).days
                feasibility_note = (
                    f"Với nhịp học {minutes_per_day} phút/ngày, {days_per_week} ngày/tuần, lộ trình cần "
                    f"đến {end_date.strftime('%d/%m/%Y')} mới học xong — trễ khoảng {overdue_days} ngày so "
                    f"với hạn {deadline_date.strftime('%d/%m/%Y')} bạn đặt ra. "
                    + (feasibility_note or "Bạn có thể tăng thời gian học mỗi ngày/số ngày mỗi tuần, hoặc gia hạn mục tiêu.")
                )
            if any_fallback_used:
                feasibility_note = (
                    (feasibility_note + " " if feasibility_note else "")
                    + "(Một vài giai đoạn dùng lịch mẫu do bước lên lịch chi tiết bằng AI tạm thời lỗi.)"
                )
            return {
                "overview": result.get("overview", f"Lộ trình học {subject} theo mục tiêu: {selected_goal}"),
                "pacing_note": pacing_note,
                "feasible": feasible,
                "feasibility_note": feasibility_note,
                "total_days": global_day_counter,
                "end_date": end_date.isoformat(),
                "phases": assembled_phases,
            }
    except Exception as e:
        logger.warning(f"Roadmap generation failed: {e}")

    # Fallback roadmap (khi LLM lỗi hoàn toàn) — xếp theo ngày thật bằng thuật toán
    fallback_source = weak_topics if weak_topics else ["Kiến thức cơ bản"]
    fallback_phases_input = [{
        "phase_number": 1,
        "title": f"Lộ trình {subject}",
        "why": "Học tuần tự theo đúng thứ tự chủ đề trong tài liệu.",
        "topics": [{"title": t, "why": "", "estimated_minutes": 60, "activities": "Đọc lý thuyết + làm bài tập cơ bản"} for t in fallback_source],
        "milestone": "Tự kiểm tra lại sau khi hoàn thành",
        "search_query": subject,
    }]
    scheduled_phases, end_date = _schedule_roadmap_days(fallback_phases_input, minutes_per_day, days_per_week, start_date_obj)
    feasible = not (deadline_date and end_date > deadline_date)
    return {
        "overview": f"Lộ trình học {subject} theo mục tiêu: {selected_goal} (sinh bằng mẫu dự phòng do lỗi AI)",
        "pacing_note": "",
        "feasible": feasible,
        "feasibility_note": "" if feasible else f"Lộ trình cần đến {end_date.isoformat()}, trễ hơn hạn {deadline}.",
        "total_days": scheduled_phases[-1]["days"][-1]["day_number"] if scheduled_phases and scheduled_phases[-1]["days"] else 0,
        "end_date": end_date.isoformat(),
        "phases": scheduled_phases,
    }


async def crawl_resources_per_phase(
    phases: list[dict],
    subject: str,
    is_code_related: bool = False,
) -> dict[str, Any]:
    """
    Crawl tài nguyên riêng cho từng giai đoạn lộ trình.
    Trả về dict: { "phase_1": {youtube, web}, "phase_2": {...}, ... }
    """
    phase_resources: dict[str, Any] = {}
    loop = asyncio.get_running_loop()

    for phase in phases:
        phase_key = f"phase_{phase.get('phase_number', 1)}"
        # Chủ đề giờ nằm trong "days" (đã xếp lịch) thay vì "topics" phẳng như trước — gom lại
        # danh sách tên chủ đề duy nhất theo đúng thứ tự xuất hiện để phục vụ tạo search_query.
        topic_titles: list[str] = []
        for day in phase.get("days", []):
            for t in day.get("topics", []):
                title = t.get("title", "") if isinstance(t, dict) else str(t)
                if title and title not in topic_titles:
                    topic_titles.append(title)
        if not topic_titles and phase.get("topics"):
            # Tương thích ngược nếu phase vẫn ở dạng cũ (chưa qua bước xếp lịch)
            topic_titles = [t.get("title", "") if isinstance(t, dict) else str(t) for t in phase["topics"]]
        if not topic_titles:
            continue

        # Ưu tiên search_query do LLM sinh riêng cho giai đoạn này (chính xác hơn) — nếu
        # không có (fallback roadmap không dùng LLM), ghép chủ đề + môn học như cũ.
        llm_query = (phase.get("search_query") or "").strip()
        if llm_query:
            search_query = _extract_search_terms(f"{subject} {llm_query}")
        else:
            topic_str = " ".join(topic_titles[:3])
            search_query = _extract_search_terms(f"{subject} {topic_str}")

        try:
            tasks = [
                loop.run_in_executor(_executor, _search_youtube, search_query, 2),
                loop.run_in_executor(_executor, _search_web_exercises, search_query, 3),
            ]
            if is_code_related:
                tasks.append(loop.run_in_executor(_executor, _search_github, search_query, 2))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            phase_resources[phase_key] = {
                "phase_title": phase.get("title", ""),
                "search_query": search_query,
                "youtube_tutorials": results[0] if isinstance(results[0], list) else [],
                "web_exercises": results[1] if isinstance(results[1], list) else [],
                "github_repos": results[2] if len(results) > 2 and isinstance(results[2], list) else [],
            }
        except Exception as e:
            logger.warning(f"Resource crawl for phase {phase_key} failed: {e}")
            phase_resources[phase_key] = {
                "phase_title": phase.get("title", ""),
                "youtube_tutorials": [],
                "web_exercises": [],
                "github_repos": [],
            }

    return phase_resources


# ---------------------------------------------------------------------------
# Crawl lời giải theo từng câu hỏi cụ thể (Luồng 2 — Phương án 1 & 2)
# ---------------------------------------------------------------------------

def _search_solution_for_question(question_content: str, limit: int = 3) -> list:
    """Crawl DuckDuckGo tìm lời giải cho 1 câu hỏi cụ thể."""
    try:
        from bs4 import BeautifulSoup  # type: ignore[import]
        # Lấy 150 ký tự đầu của câu hỏi, bỏ LaTeX
        clean_q = re.sub(r"\$\$[\s\S]*?\$\$", "", question_content)
        clean_q = re.sub(r"\$[^$\n]+?\$", "", clean_q)
        clean_q = re.sub(r"[#\*_\`\\{}\[\]]", " ", clean_q)
        clean_q = re.sub(r"\s+", " ", clean_q).strip()[:150]

        search_query = f"lời giải bài toán: {clean_q}"
        encoded = urllib.parse.quote_plus(search_query)
        req = urllib.request.Request(
            f"https://html.duckduckgo.com/html/?q={encoded}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "vi,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            soup = BeautifulSoup(resp.read().decode("utf-8"), "html.parser")
        results = []
        for result in soup.find_all("div", class_="result"):
            title_tag = result.find("h2", class_="result__title")
            snippet_tag = result.find("a", class_="result__snippet")
            url_tag = result.find("a", class_="result__url")
            if title_tag and url_tag:
                link = url_tag.get("href", "")
                if link.startswith("//duckduckgo.com/l/?uddg="):
                    link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                results.append({
                    "title": title_tag.get_text(separator=" ", strip=True),
                    "url": link,
                    "snippet": snippet_tag.get_text(separator=" ", strip=True) if snippet_tag else "",
                })
                if len(results) >= limit:
                    break
        return results
    except Exception:
        return []


async def crawl_solution_for_question(question_content: str) -> list[dict]:
    """Async wrapper: crawl lời giải cho 1 câu hỏi cụ thể qua DuckDuckGo."""
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(_executor, _search_solution_for_question, question_content, 3)
    return result if isinstance(result, list) else []


async def generate_solution_hint(
    question_content: str,
    support_level: str,
    gemini_api_keys: list[str],
    llm_api_keys: list[str],
    llm_base_url: str,
    llm_model: str,
) -> dict[str, Any]:
    """
    Sinh gợi ý giải quyết theo mức độ hỗ trợ:
    - "Hiểu đề nhưng không biết bắt đầu từ đâu": hướng giải quyết
    - "Sắp làm được rồi nhưng vẫn còn thiếu một chút": hướng + bẫy + mẹo
    Trả về: { hint: str, traps: str, tips: str }
    """
    if support_level == "Hiểu đề nhưng không biết bắt đầu từ đâu":
        prompt = f"""Bạn là gia sư môn học. Học sinh hiểu đề bài dưới đây nhưng không biết bắt đầu giải từ đâu.
Hãy đưa ra hướng giải quyết vấn đề: xác định phương pháp, bước đầu tiên cần làm, kiến thức liên quan cần dùng.
KHÔNG giải thẳng ra đáp án. Chỉ gợi ý hướng đi.

CÂU HỎI:
{question_content[:500]}

Trả về JSON:
{{
  "hint": "Hướng giải quyết vấn đề (3-5 câu, chỉ gợi ý cách tiếp cận không phải lời giải)",
  "traps": "",
  "tips": "Lời khuyên ngắn để bắt đầu"
}}"""
    else:  # "Sắp làm được rồi nhưng vẫn còn thiếu một chút"
        prompt = f"""Bạn là gia sư môn học. Học sinh gần làm được bài dưới đây nhưng vẫn chưa giải được hoàn toàn.
Hãy trình bày: (1) Hướng giải quyết chi tiết hơn, (2) Các bẫy thường gặp trong bài này, (3) Mẹo để giải đúng.
KHÔNG giải thẳng ra đáp án cuối cùng.

CÂU HỎI:
{question_content[:500]}

Trả về JSON:
{{
  "hint": "Hướng giải quyết chi tiết (3-5 câu)",
  "traps": "Các bẫy cần tránh trong bài này (gạch đầu dòng)",
  "tips": "Mẹo để giải bài này nhanh và chính xác"
}}"""

    try:
        raw = await _call_llm_with_fallback(
            prompt, gemini_api_keys, llm_api_keys, llm_base_url, llm_model, timeout=30.0
        )
        return _parse_json_safely(raw)
    except Exception as e:
        logger.warning(f"generate_solution_hint failed: {e}")
        return {"hint": "", "traps": "", "tips": ""}


# ---------------------------------------------------------------------------
# Multi-document analysis (Luồng 1 — Upload nhiều file)
# ---------------------------------------------------------------------------

async def analyze_multiple_documents(
    files: list[tuple[bytes, str]],  # list of (file_bytes, filename)
    gemini_api_keys: list[str],
    llm_api_keys: list[str],
    llm_base_url: str,
    llm_model: str | None,
) -> dict[str, Any]:
    """
    Phân tích nhiều file cùng lúc.
    Trả về:
    {
        results: list[dict],  # kết quả analyze cho từng file
        merged_subject: str,  # môn học chung nếu cùng môn
        subjects: list[str],  # danh sách các môn phát hiện được
        multi_subject_detected: bool,  # True nếu phát hiện > 1 môn khác nhau
        merged_raw_text: str,  # raw text gộp để sinh quiz
        merged_topics: list[str],
        merged_goals: list[str],
        is_code_related: bool,
        ocr_engine: str,
    }
    """
    tasks = [
        analyze_document_for_learning(fb, fn, gemini_api_keys, llm_api_keys, llm_base_url, llm_model)
        for fb, fn in files
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid = [r for r in results if isinstance(r, dict) and r.get("is_learning_doc")]
    subjects = list(dict.fromkeys(r.get("subject", "") for r in valid if r.get("subject")))

    # Phát hiện đa môn: so sánh từ đầu tiên (bỏ số, ký tự đặc biệt)
    def normalize_subject(s: str) -> str:
        return re.sub(r"[\d\s\W]+", "", s.lower())[:10]

    normalized = [normalize_subject(s) for s in subjects]
    unique_normalized = list(dict.fromkeys(normalized))
    multi_subject = len(unique_normalized) > 1

    full_raw = "\n\n---\n\n".join(r.get("raw_text", "") for r in valid)
    merged_raw = full_raw[:6000]
    # Chỉ gộp topics từ các tài liệu CÓ cấu trúc chương rõ ràng — tài liệu viết liền mạch
    # không đóng góp mục lục vì không thể xác định thứ tự chương của nó.
    structured_docs = [r for r in valid if r.get("has_clear_structure")]
    merged_topics = list(
        dict.fromkeys(t for r in structured_docs for t in r.get("topics", []))
    )[:20]
    merged_goals = valid[0].get("suggested_goals", []) if valid else []
    is_code = any(r.get("is_code_related") for r in valid)
    ocr_engine = valid[0].get("ocr_engine", "unknown") if valid else "unknown"
    merged_subject = subjects[0] if subjects else "Tài liệu học tập"
    has_clear_structure = len(structured_docs) > 0
    structure_reason = (
        None
        if has_clear_structure
        else next((r.get("structure_reason") for r in valid if r.get("structure_reason")), None)
    )

    return {
        "results": [r for r in results if isinstance(r, dict)],
        "merged_subject": merged_subject,
        "subjects": subjects,
        "multi_subject_detected": multi_subject,
        "merged_raw_text": merged_raw,
        "merged_topics": merged_topics,
        "merged_goals": merged_goals,
        "is_code_related": is_code,
        "ocr_engine": ocr_engine,
        "has_clear_structure": has_clear_structure,
        "structure_reason": structure_reason,
        "reading_time": estimate_reading_time(full_raw),
    }


# ---------------------------------------------------------------------------
# Competency Evidence Validation (Luồng 1 — Nhóm 2: năng lực hiện tại)
# ---------------------------------------------------------------------------

async def analyze_competency_evidence(
    file_bytes: bytes,
    filename: str,
    gemini_api_keys: list[str],
    llm_api_keys: list[str],
    llm_base_url: str,
    llm_model: str | None,
) -> dict[str, Any]:
    """
    Xác thực tài liệu minh chứng năng lực (bảng điểm/chứng chỉ/bài kiểm tra) do người
    dùng upload — chặn trường hợp upload nhầm ảnh/file không liên quan.

    Returns:
        {
            is_competency_evidence: bool,
            evidence_type: "transcript"|"certificate"|"exam"|"other",
            reason: str | None,  # lý do khi is_competency_evidence=False
            raw_text: str,
        }
    """
    try:
        raw_text, _ocr_engine = await extract_text_from_file(file_bytes, filename, gemini_api_keys)
    except (ValueError, RuntimeError) as e:
        return {
            "is_competency_evidence": False,
            "evidence_type": "other",
            "reason": f"Không thể đọc file: {e}",
            "raw_text": "",
        }

    if not raw_text or len(raw_text.strip()) < 10:
        return {
            "is_competency_evidence": False,
            "evidence_type": "other",
            "reason": "File trống hoặc không đọc được nội dung.",
            "raw_text": "",
        }

    if not llm_api_keys or not llm_model:
        # Không có AI để xác thực — chấp nhận có điều kiện, để người dùng tự chịu trách nhiệm.
        return {
            "is_competency_evidence": True,
            "evidence_type": "other",
            "reason": None,
            "raw_text": raw_text,
        }

    prompt = f"""Bạn là hệ thống xác thực tài liệu minh chứng năng lực học tập.

NỘI DUNG TÀI LIỆU (tối đa 2000 ký tự đầu):
---
{raw_text[:2000]}
---

NHIỆM VỤ: Xác định tài liệu này có phải là minh chứng năng lực học tập không — tức là bảng điểm,
chứng chỉ, hoặc bài kiểm tra/bài thi đã làm. KHÔNG phải minh chứng nếu đây là ảnh/văn bản không
liên quan (ảnh cá nhân, tài liệu khác môn, văn bản ngẫu nhiên...).

Trả về JSON (chỉ JSON):
{{
  "is_competency_evidence": true hoặc false,
  "evidence_type": "transcript" (bảng điểm) | "certificate" (chứng chỉ) | "exam" (bài kiểm tra/bài thi đã làm) | "other",
  "reason": "Lý do ngắn gọn nếu is_competency_evidence=false, để trống nếu true"
}}"""

    try:
        raw = await _call_llm_with_fallback(
            prompt, gemini_api_keys, llm_api_keys, llm_base_url, llm_model, timeout=30.0
        )
        data = _parse_json_safely(raw)
        return {
            "is_competency_evidence": bool(data.get("is_competency_evidence", False)),
            "evidence_type": data.get("evidence_type", "other"),
            "reason": data.get("reason") or None,
            "raw_text": raw_text,
        }
    except Exception as e:
        logger.warning(f"Competency evidence validation failed: {e}")
        return {
            "is_competency_evidence": True,
            "evidence_type": "other",
            "reason": None,
            "raw_text": raw_text,
        }


# ---------------------------------------------------------------------------
# File Storage Helper
# ---------------------------------------------------------------------------

def save_upload_file(
    file_bytes: bytes,
    filename: str,
    user_id: str,
    folder_type: str,  # "Doc" hoặc "Exam"
    subject_name: str,
    base_uploads_dir: str = "uploads",
) -> str:
    """
    Lưu file vào uploads/{user_id}/{folder_type}/{subject_name}/{filename}
    Trả về đường dẫn tương đối đã lưu.
    """
    import re as _re
    # Sanitize subject_name thành tên thư mục hợp lệ
    safe_subject = _re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', subject_name)
    safe_subject = safe_subject.strip(". ")[:80] or "Unknown"

    dir_path = os.path.join(base_uploads_dir, str(user_id), folder_type, safe_subject)
    os.makedirs(dir_path, exist_ok=True)

    # Tránh trùng tên file: thêm timestamp nếu trùng
    base, ext = os.path.splitext(filename)
    target = os.path.join(dir_path, filename)
    if os.path.exists(target):
        from datetime import datetime as _dt
        ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        target = os.path.join(dir_path, f"{base}_{ts}{ext}")

    with open(target, "wb") as f:
        f.write(file_bytes)

    # Trả về đường dẫn tương đối (dùng / thay \)
    return target.replace("\\", "/")


# ---------------------------------------------------------------------------
# Full Exam Pipeline (Luồng 2 — Post-Exam)
# ---------------------------------------------------------------------------

async def run_full_exam_pipeline(
    file_bytes: bytes,
    filename: str,
    gemini_api_keys: list[str],
) -> dict[str, Any]:
    """
    Pipeline đầy đủ cho Luồng 2: OCR → Parse → (AI Recommend) → Crawl.
    AI Recommendation được gọi riêng từ route để dùng Groq.
    """
    parsed = await ocr_and_parse(file_bytes, filename, gemini_api_keys)

    # Crawl resources (tự detect code-related từ nội dung)
    search_seed = parsed.get("raw_markdown", "")[:500]
    is_code = _detect_code_related(search_seed)
    resources: dict = {}
    if search_seed.strip():
        try:
            resources = await crawl_resources_smart(search_seed, is_code_related=is_code)
        except Exception as e:
            logger.warning(f"Resource crawl failed: {e}")

    return {
        "parsed": parsed,
        "resources": resources,
        "is_code_related": is_code,
    }
