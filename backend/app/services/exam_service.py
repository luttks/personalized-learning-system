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
from typing import Any

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10)

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
    '{"exam_content": "Trích xuất TOÀN BỘ nội dung thành Markdown kết hợp LaTeX. '
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

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
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
        raise
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
    last_err: Exception | None = None
    for key in gemini_api_keys:
        if not key or not key.strip():
            continue
        try:
            ocr_json = await run_gemini_ocr(file_bytes, suffix, key)
            data = _parse_json_safely(ocr_json)
            raw_text = data.get("exam_content", "")
            if raw_text.strip():
                return raw_text, "gemini"
        except ValueError:
            raise  # Key không hợp lệ → raise ngay
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise RuntimeError(f"Lỗi OCR (Quota/Network): {last_err}")
    raise RuntimeError("Không thể trích xuất nội dung từ file.")


# ---------------------------------------------------------------------------
# Groq / OpenAI-compatible AI calls
# ---------------------------------------------------------------------------

async def _call_groq(
    prompt: str,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float = 60.0,
    expect_json: bool = True,
) -> str:
    """Gọi Groq (OpenAI-compatible) với 1 key cụ thể."""
    import httpx

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Bạn là chuyên gia giáo dục AI. "
                    + ("Trả về JSON hợp lệ, KHÔNG có markdown code block, KHÔNG có text thừa." if expect_json else "")
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4000,
    }
    if expect_json:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_gemini_text(
    prompt: str,
    api_key: str,
    expect_json: bool = True,
) -> str:
    """Gọi Gemini (Google) để phân tích text."""
    from google import genai  # type: ignore[import]
    from google.genai import errors  # type: ignore[import]

    client = genai.Client(api_key=api_key)
    
    sys_instruction = (
        "Bạn là chuyên gia giáo dục AI. "
        + ("Trả về JSON hợp lệ, KHÔNG có markdown code block, KHÔNG có text thừa." if expect_json else "")
    )
    
    config = genai.types.GenerateContentConfig(
        system_instruction=sys_instruction,
        temperature=0.3,
    )
    if expect_json:
        config.response_mime_type = "application/json"

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=config,
        )
        if response and response.text:
            return response.text
        raise RuntimeError("Phản hồi từ Gemini rỗng.")
    except errors.APIError as e:  # type: ignore[attr-defined]
        msg = str(e)
        if "API_KEY_INVALID" in msg or "API key not valid" in msg:
            raise ValueError(f"GEMINI_API_KEY không hợp lệ: {msg[:100]}")
        raise


async def _call_llm_with_fallback(
    prompt: str,
    gemini_keys: list[str],
    groq_keys: list[str],
    groq_base_url: str,
    groq_model: str,
    timeout: float = 60.0,
    expect_json: bool = True,
) -> str:
    """
    Ưu tiên dùng Gemini (nếu có key).
    Nếu Gemini fail, fallback sang Groq (với danh sách key).
    """
    last_err: Exception | None = None
    
    # 1. Thử Gemini trước
    for i, key in enumerate(gemini_keys):
        try:
            result = await _call_gemini_text(prompt, key, expect_json)
            logger.info(f"LLM rotation: thành công với Gemini key #{i+1}")
            return result
        except Exception as e:
            err_str = str(e)
            logger.warning(f"Gemini key #{i+1} lỗi: {err_str[:80]}, thử tiếp...")
            last_err = e
            continue

    # 2. Nếu Gemini fail hết, thử Groq
    for i, key in enumerate(groq_keys):
        try:
            result = await _call_groq(prompt, key, groq_base_url, groq_model, timeout, expect_json)
            logger.info(f"LLM rotation: thành công với Groq key #{i+1}")
            return result
        except Exception as e:
            err_str = str(e)
            logger.warning(f"Groq key #{i+1} lỗi: {err_str[:80]}, thử tiếp...")
            last_err = e
            continue

    raise RuntimeError(f"Tất cả Gemini và Groq keys đều thất bại. Lỗi cuối: {last_err}")


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
        }

    prompt = f"""Bạn là chuyên gia giáo dục. Hãy phân tích đoạn tài liệu sau và trả về JSON.

NỘI DUNG TÀI LIỆU (tối đa 3000 ký tự đầu):
---
{raw_text[:3000]}
---

Trả về JSON với đúng cấu trúc sau (chỉ JSON, không có text ngoài):
{{
  "is_learning_doc": true hoặc false (true nếu đây là tài liệu giáo dục/học tập),
  "not_learning_reason": "Lý do ngắn gọn nếu không phải tài liệu học, để trống nếu là tài liệu học",
  "subject": "Tên môn học/chủ đề cụ thể (VD: Giải tích 1, Lập trình Python, Ngữ văn 12...)",
  "topics": ["Chủ đề 1", "Chủ đề 2", "Chủ đề 3"],
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

Lưu ý quan trọng:
- suggested_goals phải đặc trưng cho môn học này, KHÔNG phải câu chung chung
- Nếu là đề thi thì is_learning_doc=true, gợi ý mục tiêu ôn luyện
- Nếu là ảnh không liên quan học tập (ảnh cá nhân, thiên nhiên...) thì is_learning_doc=false"""

    try:
        raw = await _call_llm_with_fallback(
            prompt, gemini_api_keys, llm_api_keys, llm_base_url, llm_model, timeout=45.0
        )
        data = _parse_json_safely(raw)

        is_learning = bool(data.get("is_learning_doc", True))
        not_learning_reason = data.get("not_learning_reason", "")
        is_code_related = bool(data.get("is_code_related", False)) or is_code_related_quick

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
) -> dict[str, Any]:
    """
    Sinh lộ trình học tập chia giai đoạn từ kết quả quiz/đề thi.
    Mỗi giai đoạn có: tên, thời gian, topics, kế hoạch hàng ngày.
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

    weak_topics_str = ", ".join(weak_topics[:10]) if weak_topics else "các kiến thức cơ bản"

    quiz_context = ""
    if quick_quiz_results_str:
        quiz_context = f"KẾT QUẢ QUICK TEST GẦN NHẤT:\n{quick_quiz_results_str}\n(Lưu ý: Nếu kết quả báo sai nhiều ở các câu tiên quyết/cơ bản, HÃY thêm ngay Giai đoạn 0: Ôn tập kiến thức nền tảng. Nếu đúng gần hết, đề xuất Lộ trình tăng tốc rút ngắn thời gian.)\n"

    prompt = f"""Bạn là chuyên gia giáo dục AI, thiết kế lộ trình học tập cá nhân hóa sâu sắc.

MÔN HỌC: {subject}
MỤC TIÊU CỦA NGƯỜI HỌC: {selected_goal}
ĐÁNH GIÁ NĂNG LỰC: {level_hint}
{quiz_context}CÁC CHỦ ĐỀ CẦN ÔN TẬP: {weak_topics_str}
THỜI GIAN HỌC MỖI NGÀY: {minutes_per_day} phút

NHIỆM VỤ: Tạo lộ trình học tập chia thành các giai đoạn logic. Tùy theo KẾT QUẢ QUICK TEST hoặc năng lực, lộ trình có thể:
1. Chèn thêm "Giai đoạn 0: Bổ sung kiến thức nền tảng" nếu bị mất gốc (sai câu tiên quyết).
2. Lộ trình "Tăng tốc" nếu điểm cao và vững kiến thức.
3. Nhận xét thẳng thắn về tình hình hiện tại (Ví dụ: "Bạn chưa nắm vững nền tảng, học tài liệu này sẽ rất khó").

Trả về JSON (chỉ JSON, không markdown):
{{
  "total_weeks": 6,
  "overview": "Mô tả tổng quan 1-2 câu về toàn bộ lộ trình và nhận xét thẳng thắn",
  "phases": [
    {{
      "phase_number": 1,
      "title": "Tên giai đoạn",
      "duration_weeks": 2,
      "goal": "Mục tiêu cụ thể cần đạt sau giai đoạn này",
      "topics": ["Chủ đề 1", "Chủ đề 2", "Chủ đề 3"],
      "daily_plan": "Mô tả ngắn về việc học hàng ngày trong giai đoạn này",
      "milestone": "Cột mốc kiểm tra cuối giai đoạn"
    }}
  ]
}}"""

    try:
        raw = await _call_llm_with_fallback(
            prompt, gemini_api_keys, llm_api_keys, llm_base_url, llm_model, timeout=60.0
        )
        result = _parse_json_safely(raw)
        if result.get("phases"):
            return result
    except Exception as e:
        logger.warning(f"Roadmap generation failed: {e}")

    # Fallback roadmap
    return {
        "total_weeks": 6,
        "overview": f"Lộ trình học {subject} theo mục tiêu: {selected_goal}",
        "phases": [
            {
                "phase_number": 1,
                "title": "Nền tảng",
                "duration_weeks": 2,
                "goal": "Nắm vững các khái niệm cơ bản",
                "topics": weak_topics[:3] if weak_topics else ["Kiến thức cơ bản"],
                "daily_plan": f"Học {minutes_per_day} phút/ngày, tập trung lý thuyết và ví dụ mẫu.",
                "milestone": "Làm bài kiểm tra nhỏ cuối tuần 2",
            },
            {
                "phase_number": 2,
                "title": "Luyện tập",
                "duration_weeks": 2,
                "goal": "Vận dụng kiến thức vào bài tập",
                "topics": weak_topics[3:6] if len(weak_topics) > 3 else ["Bài tập thực hành"],
                "daily_plan": f"Học {minutes_per_day} phút/ngày, làm bài tập đa dạng.",
                "milestone": "Hoàn thành bộ đề luyện tập",
            },
            {
                "phase_number": 3,
                "title": "Nâng cao & Tổng ôn",
                "duration_weeks": 2,
                "goal": "Đạt mục tiêu: " + selected_goal,
                "topics": ["Ôn tập tổng hợp", "Đề thi thử", "Sửa lỗi sai"],
                "daily_plan": f"Học {minutes_per_day} phút/ngày, tập trung đề thi và bài khó.",
                "milestone": "Thi thử và đánh giá cuối lộ trình",
            },
        ],
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
        topics = phase.get("topics", [])
        if not topics:
            continue

        # Tạo query search từ chủ đề giai đoạn + môn học
        topic_str = " ".join(topics[:3])
        query = f"{subject} {topic_str}"
        search_query = _extract_search_terms(query)

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

    merged_raw = "\n\n---\n\n".join(r.get("raw_text", "") for r in valid)[:6000]
    merged_topics = list(dict.fromkeys(t for r in valid for t in r.get("topics", [])))[:10]
    merged_goals = valid[0].get("suggested_goals", []) if valid else []
    is_code = any(r.get("is_code_related") for r in valid)
    ocr_engine = valid[0].get("ocr_engine", "unknown") if valid else "unknown"
    merged_subject = subjects[0] if subjects else "Tài liệu học tập"

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
