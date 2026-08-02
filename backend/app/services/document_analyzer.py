import json

from app.agents.learner.understanding_agent import (
    LearnerUnderstandingError,
    OpenAICompatibleProvider,
)
from app.schemas.content import DocumentStructure

DOCUMENT_SYSTEM_PROMPT = """Bạn là hệ thống phân tích tài liệu giáo dục.
Chỉ trả về JSON đúng schema:
{
  "title": "string",
  "summary": "string",
  "chapters": [
    {"number": 1, "title": "string", "summary": "string", "key_points": ["string"]}
  ]
}
Quy tắc:
- Chỉ dùng thông tin có trong tài liệu được cung cấp.
- Không tự bịa chương, số liệu hoặc mục tiêu không có nguồn.
- Giữ nguyên ngôn ngữ của tài liệu.
- Tối đa 30 chương, mỗi chương tối đa 5 ý chính.
- Nếu không nhận diện được chương, chia theo các phần nội dung thực tế.
"""


async def analyze_with_llm(
    provider: OpenAICompatibleProvider,
    text: str,
    title: str,
) -> DocumentStructure:
    raw = await provider.complete_json(
        system_prompt=DOCUMENT_SYSTEM_PROMPT,
        user_prompt=json.dumps(
            {"document_title": title, "document_text": text},
            ensure_ascii=False,
        ),
    )
    result = DocumentStructure.model_validate({**raw, "source": "llm"})
    if not result.chapters:
        raise LearnerUnderstandingError("LLM không trả về chapter nào.")
    return result
