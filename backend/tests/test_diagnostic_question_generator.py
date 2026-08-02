import pytest
from app.services.diagnostic_question_generator import (
    DiagnosticQuestionGenerationError,
    validate_generated_questions,
)


def lesson_contexts() -> list[dict]:
    return [
        {
            "lesson_id": "10000000-0000-4000-8000-000000000001",
            "title": "Bài 1",
            "concepts": [
                {
                    "id": "20000000-0000-4000-8000-000000000001",
                    "title": "Người tối cổ",
                }
            ],
            "chunks": [
                {
                    "id": "30000000-0000-4000-8000-000000000001",
                    "source_label": "Trang 1",
                    "source_text": "Người tối cổ sử dụng công cụ đá ghè đẽo thô sơ.",
                }
            ],
        },
        {
            "lesson_id": "10000000-0000-4000-8000-000000000002",
            "title": "Bài 2",
            "concepts": [
                {
                    "id": "20000000-0000-4000-8000-000000000002",
                    "title": "Thuật luyện kim",
                }
            ],
            "chunks": [
                {
                    "id": "30000000-0000-4000-8000-000000000002",
                    "source_label": "Trang 2",
                    "source_text": "Thuật luyện kim giúp chế tạo công cụ bằng kim loại.",
                }
            ],
        },
    ]


def question(number: int, lesson: int) -> dict:
    return {
        "concept_id": f"20000000-0000-4000-8000-{lesson:012d}",
        "lesson_id": f"10000000-0000-4000-8000-{lesson:012d}",
        "source_chunk_id": f"30000000-0000-4000-8000-{lesson:012d}",
        "prompt": f"Đặc điểm cụ thể số {number} được nêu trong bài học là gì?",
        "options": [f"Phương án đúng {number}", "Nông nghiệp", "Đồ gốm", "Chăn nuôi"],
        "correct_index": 0,
        "explanation": "Đáp án được xác định trực tiếp từ nội dung nguồn.",
    }


def test_generated_diagnostic_requires_two_questions_per_lesson() -> None:
    raw = {
        "questions": [
            question(1, 1),
            question(2, 1),
            question(3, 1),
            question(4, 2),
            question(5, 2),
            question(6, 2),
        ]
    }

    assert len(validate_generated_questions(raw, lesson_contexts())) == 6


def test_generated_diagnostic_rejects_generic_prompt() -> None:
    raw = {
        "questions": [
            question(1, 1),
            question(2, 1),
            question(3, 1),
            question(4, 2),
            question(5, 2),
            {
                **question(6, 2),
                "prompt": "Nội dung nào phù hợp nhất với mô tả trong bài học?",
            },
        ]
    }

    with pytest.raises(DiagnosticQuestionGenerationError):
        validate_generated_questions(raw, lesson_contexts())
