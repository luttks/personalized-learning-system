import json
import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.agents.learner.understanding_agent import (
    ChatCompletionProvider,
    LearnerUnderstandingError,
)

DIAGNOSTIC_SYSTEM_PROMPT = """Bạn là chuyên gia thiết kế bài kiểm tra chẩn đoán.
Chỉ trả về JSON: {"questions": [...]}.
Mỗi câu hỏi phải có đúng các trường:
- concept_id: UUID được cung cấp
- lesson_id: UUID được cung cấp
- source_chunk_id: UUID của chunk thuộc đúng bài học
- prompt: câu hỏi kiến thức rõ ràng, tự nhiên, kiểm tra một ý cụ thể
- options: đúng 4 lựa chọn ngắn gọn, cùng loại và không trùng nhau
- correct_index: vị trí đáp án đúng từ 0 đến 3
- explanation: giải thích ngắn dựa trên nguồn
Quy tắc bắt buộc:
- Chỉ dùng dữ kiện trong source_text; không bổ sung kiến thức bên ngoài.
- Phủ đều các bài học, mục tiêu 3 câu cho mỗi bài nếu nguồn cho phép.
- Hỏi về mốc thời gian, đặc điểm, nguyên nhân, kết quả, so sánh hoặc nhận diện cụ thể.
- Không dùng câu chung chung kiểu 'Nội dung nào phù hợp nhất với mô tả'.
- Không lặp prompt hoặc chỉ tráo thứ tự đáp án.
- Distractor phải hợp lý nhưng sai rõ ràng theo nguồn.
- Không nhắc đến chunk, tài liệu, đoạn văn hay đáp án trong prompt.
"""


class GeneratedDiagnosticQuestion(BaseModel):
    concept_id: UUID
    lesson_id: UUID
    source_chunk_id: UUID
    prompt: str = Field(min_length=15, max_length=1000)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=10, max_length=1500)

    @field_validator("options")
    @classmethod
    def validate_options(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if len({normalize_text(value) for value in cleaned}) != 4:
            raise ValueError("Các lựa chọn phải khác nhau.")
        return cleaned


class GeneratedDiagnosticSet(BaseModel):
    questions: list[GeneratedDiagnosticQuestion] = Field(min_length=5, max_length=50)


class DiagnosticQuestionGenerationError(Exception):
    pass


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def validate_generated_questions(
    raw: Mapping[str, Any],
    lessons: list[dict],
) -> list[dict]:
    try:
        generated = GeneratedDiagnosticSet.model_validate(raw)
    except ValidationError as error:
        raise DiagnosticQuestionGenerationError("Đề không đúng schema.") from error
    lesson_by_id = {str(item["lesson_id"]): item for item in lessons}
    seen_prompts: set[str] = set()
    counts = {lesson_id: 0 for lesson_id in lesson_by_id}
    result: list[dict] = []
    for question in generated.questions:
        lesson = lesson_by_id.get(str(question.lesson_id))
        if lesson is None:
            raise DiagnosticQuestionGenerationError("Câu hỏi trỏ sai bài học.")
        allowed_concepts = {item["id"] for item in lesson["concepts"]}
        chunks = {item["id"]: item for item in lesson["chunks"]}
        if str(question.concept_id) not in allowed_concepts:
            raise DiagnosticQuestionGenerationError("Câu hỏi trỏ sai concept.")
        chunk = chunks.get(str(question.source_chunk_id))
        if chunk is None:
            raise DiagnosticQuestionGenerationError("Câu hỏi trỏ sai chunk nguồn.")
        normalized_prompt = normalize_text(question.prompt)
        if "nội dung nào phù hợp nhất với mô tả" in normalized_prompt:
            raise DiagnosticQuestionGenerationError("Câu hỏi còn chung chung.")
        if normalized_prompt in seen_prompts:
            raise DiagnosticQuestionGenerationError("Đề có câu hỏi trùng nhau.")
        correct_answer = question.options[question.correct_index]
        if normalize_text(correct_answer) in normalized_prompt:
            raise DiagnosticQuestionGenerationError("Prompt làm lộ đáp án.")
        seen_prompts.add(normalized_prompt)
        counts[str(question.lesson_id)] += 1
        result.append(
            {
                **question.model_dump(mode="json"),
                "concept_title": next(
                    item["title"]
                    for item in lesson["concepts"]
                    if item["id"] == str(question.concept_id)
                ),
                "lesson_title": lesson["title"],
                "source_label": chunk["source_label"],
            }
        )
    if any(count < 2 for count in counts.values()):
        raise DiagnosticQuestionGenerationError("Mỗi bài học cần có ít nhất 2 câu hỏi.")
    return result


async def generate_diagnostic_questions(
    provider: ChatCompletionProvider,
    lessons: list[dict],
) -> list[dict]:
    target = min(30, max(len(lessons) * 3, len(lessons)))
    base_payload = {"target_question_count": target, "lessons": lessons}
    user_prompt = json.dumps(
        base_payload,
        ensure_ascii=False,
    )
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            raw = await provider.complete_json(
                system_prompt=DIAGNOSTIC_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            return validate_generated_questions(raw, lessons)
        except (LearnerUnderstandingError, DiagnosticQuestionGenerationError) as error:
            last_error = error
            user_prompt = json.dumps(
                {
                    **base_payload,
                    "validation_error_from_previous_attempt": str(error),
                    "instruction": "Hãy sửa toàn bộ lỗi và sinh lại một bộ đề mới.",
                },
                ensure_ascii=False,
            )
    raise DiagnosticQuestionGenerationError(
        "Không thể sinh bộ câu hỏi đạt chuẩn sau 2 lần kiểm tra."
    ) from last_error
