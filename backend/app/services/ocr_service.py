"""
OCR Service — extract structured data from exam images / PDFs using
Gemini AI, with an OpenAI / GitHub Models fallback.

Ported from WorkFlow/app.py ``run_gemini_ocr`` + ``read_text_document``.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

logger = logging.getLogger("workflow.ocr")

# ---------------------------------------------------------------------------
# Prompt shared by both Gemini and OpenAI paths
# ---------------------------------------------------------------------------
_OCR_PROMPT = """\
Bạn là một mô hình phân tích và bóc tách tài liệu giáo dục.
Hãy phân tích hình ảnh/tài liệu để xác định xem đây là Đề thi (loại 1) hay Bảng điểm/Phiếu liên lạc (loại 2).
PHẢI TRẢ VỀ KẾT QUẢ DƯỚI DẠNG ĐỊNH DẠNG JSON.

Nếu là Đề thi (loai: 1), hãy trả về JSON theo cấu trúc sau:
{
  "loai": 1,
  "exam_content": "Trích xuất TOÀN BỘ nội dung đề thi thành Markdown kết hợp LaTeX. \
Giữ nguyên cấu trúc đề thi (Câu I, Bài 1...). \
Tất cả công thức toán học PHẢI bọc trong $...$ hoặc $$...$$. \
Đảm bảo cú pháp LaTeX chính xác."
}

Nếu là Bảng điểm / Phiếu liên lạc (loai: 2), hãy trả về JSON:
{
  "loai": 2,
  "metadata": {
    "grade": "Khối lớp (số) hoặc null",
    "semester": "Học kỳ (1 hoặc 2) hoặc null"
  },
  "columns": [
    { "key": "col_1", "label": "Chữ nguyên bản trên tiêu đề cột 1 (VD: Miệng, ĐTX, Giữa kỳ)" },
    { "key": "col_2", "label": "Tiêu đề cột 2" }
  ],
  "rows": [
    {
      "subject": "Tên môn học hoặc Họ tên học sinh",
      "col_1": "Giá trị thô dạng chuỗi hoặc chuỗi rỗng",
      "col_2": "Giá trị thô dạng chuỗi hoặc chuỗi rỗng"
    }
  ],
  "critic": "Lời nhận xét tổng quan cho toàn bộ bảng điểm"
}

QUY TẮC BẮT BUỘC ĐỐI VỚI BẢNG ĐIỂM:
1. KHÔNG tự ý gom nhóm tên cột. Giữ nguyên tiêu đề gốc vào mảng 'columns'.
2. Nếu không xác định được Lớp hoặc Học kỳ chắc chắn, hãy để giá trị là null.
3. Giữ toàn bộ giá trị điểm số dưới dạng chuỗi (string).
4. Nếu một cột có nhiều điểm nhỏ thì lấy trung bình, đảm bảo 1 cột chỉ chứa 1 điểm tại 1 ô
5. BẮT BUỘC phải viết lời nhận xét và trả về trường critic"""

_MIME_MAP: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def read_text_document(file_path: str, suffix: str) -> str:
    """Read a plain-text or Word document."""
    if suffix in (".txt", ".html", ".htm"):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
        except Exception as exc:
            return f"Lỗi đọc tệp văn bản: {exc}"
    elif suffix == ".docx":
        try:
            import docx  # python-docx

            doc = docx.Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return (
                "Vui lòng cài đặt python-docx để đọc tệp .docx "
                "hoặc dùng tệp ảnh/PDF."
            )
    return ""


# ---------------------------------------------------------------------------
# Core Gemini OCR
# ---------------------------------------------------------------------------

async def run_gemini_ocr(
    file_path: str,
    suffix: str,
    api_key: str,
) -> str:
    """
    Call Gemini API to OCR and extract LaTeX from an image or PDF.

    Falls back to an OpenAI-compatible endpoint (GitHub Models) when
    Gemini is unavailable.
    """
    from google import genai
    from google.genai import errors as genai_errors

    client = genai.Client(api_key=api_key)

    with open(file_path, "rb") as fh:
        file_bytes = fh.read()

    mime = _MIME_MAP.get(suffix, "image/jpeg")

    models_to_try = ["gemini-flash-latest"]
    last_error: Exception | None = None

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    genai.types.Part.from_bytes(
                        data=file_bytes, mime_type=mime,
                    ),
                    _OCR_PROMPT,
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            if response and response.text:
                return response.text
        except genai_errors.APIError as exc:
            last_error = exc
            msg = str(exc)
            if "API_KEY_INVALID" in msg or "API key not valid" in msg:
                raise ValueError(
                    "API Key Gemini không hợp lệ. Vui lòng kiểm tra lại "
                    "API Key Google AI Studio của bạn."
                ) from exc
            continue
        except Exception as exc:
            last_error = exc
            msg = str(exc)
            if "API key not valid" in msg or "INVALID_ARGUMENT" in msg:
                raise ValueError(
                    "API Key Gemini không hợp lệ. Vui lòng nhập đúng "
                    "Gemini API Key."
                ) from exc
            continue

    # ---- Fallback: OpenAI / GitHub Models ----
    if last_error:
        github_token = os.environ.get("GITHUB_TOKEN", "").strip()
        if github_token:
            try:
                from openai import OpenAI

                base_url = os.environ.get(
                    "GITHUB_BASE_URL",
                    "https://models.inference.ai.azure.com",
                )
                openai_client = OpenAI(
                    base_url=base_url, api_key=github_token,
                )
                b64_img = base64.b64encode(file_bytes).decode("utf-8")
                resp = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": _OCR_PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime};base64,{b64_img}",
                                    },
                                },
                            ],
                        }
                    ],
                    response_format={"type": "json_object"},
                )
                return resp.choices[0].message.content  # type: ignore[return-value]
            except Exception as ex:
                raise RuntimeError(
                    f"Gemini API error: {last_error} | "
                    f"OpenAI fallback error: {ex}"
                ) from ex
        raise last_error

    raise RuntimeError("Không nhận được phản hồi từ Gemini API.")


# ---------------------------------------------------------------------------
# AI Recommendation (question difficulty analysis)
# ---------------------------------------------------------------------------

async def get_ai_recommendation(
    questions: list[str],
    api_key: str,
) -> dict[str, Any]:
    """
    Call Gemini (or OpenAI fallback) to classify questions by difficulty
    and provide learning recommendations.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    questions_json = json.dumps(questions, ensure_ascii=False, indent=2)

    prompt = f"""\
Vai trò: Chuyên gia phân tích năng lực học tập.
Nhiệm vụ: Dưới đây là danh sách các câu hỏi mà học sinh cần khuyến nghị. \
Hãy phân loại chúng theo Mức độ khó và đưa ra lời khuyên chi tiết cho \
TỪNG CÂU HỎI một. KHÔNG ĐƯỢC BỎ SÓT BẤT KỲ CÂU NÀO. \
TUYỆT ĐỐI KHÔNG ĐƯỢC GIẢI BÀI TẬP HAY ĐƯA RA ĐÁP ÁN.

BẮT BUỘC TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON SAU:
{{
  "nhom_co_ban": {{
    "loi_khuyen_chung": "Nhận xét tổng quan…",
    "chi_tiet_tung_cau": [
      {{
        "id_cau": "[ID câu hỏi, VD: Câu 1]",
        "kien_thuc_can_hoc": "[Kiến thức cần học]",
        "loi_khuyen_ngan": "[Phân tích bẫy và cách tiếp cận tư duy]"
      }}
    ]
  }},
  "nhom_van_dung": {{
    "loi_khuyen_chung": "…",
    "chi_tiet_tung_cau": []
  }},
  "nhom_van_dung_cao": {{
    "loi_khuyen_chung": "…",
    "chi_tiet_tung_cau": []
  }}
}}

Danh sách câu hỏi cần phân tích:
{questions_json}
"""

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        if response and response.text:
            return json.loads(response.text)  # type: ignore[no-any-return]
    except Exception as exc:
        # Fallback to OpenAI / GitHub Models
        github_token = os.environ.get("GITHUB_TOKEN", "").strip()
        if github_token:
            try:
                from openai import OpenAI

                base_url = os.environ.get(
                    "GITHUB_BASE_URL",
                    "https://models.inference.ai.azure.com",
                )
                openai_client = OpenAI(
                    base_url=base_url, api_key=github_token,
                )
                resp = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                )
                return json.loads(resp.choices[0].message.content)  # type: ignore[arg-type, no-any-return]
            except Exception as ex:
                raise RuntimeError(
                    f"Gemini API error: {exc} | "
                    f"OpenAI fallback error: {ex}"
                ) from ex
        raise

    return {}
