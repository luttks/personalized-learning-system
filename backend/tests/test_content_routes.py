import pytest
from app.main import app
from app.schemas.content import LearnerCourseProfileUpsert
from app.services.catalog_service import focused_concept_description
from app.services.diagnostic_service import public_question
from pydantic import ValidationError


def test_course_content_routes_are_registered() -> None:
    paths = app.openapi()["paths"]

    assert "post" in paths["/api/v1/courses"]
    assert "get" in paths["/api/v1/courses"]
    assert "delete" in paths["/api/v1/courses/{course_id}"]
    assert "post" in paths["/api/v1/courses/{course_id}/publish"]
    assert "post" in paths["/api/v1/courses/{course_id}/unpublish"]
    assert "get" in paths["/api/v1/catalog/courses"]
    assert "get" in paths["/api/v1/catalog/courses/{course_id}"]
    assert "get" in paths["/api/v1/catalog/courses/{course_id}/learner-profile"]
    assert "put" in paths["/api/v1/catalog/courses/{course_id}/learner-profile"]
    assert "post" in paths["/api/v1/catalog/courses/{course_id}/diagnostics"]
    assert "post" in paths["/api/v1/diagnostic-attempts/{attempt_id}/submit"]
    assert "post" in paths[
        "/api/v1/catalog/courses/{course_id}/learning-paths"
    ]
    assert "get" in paths[
        "/api/v1/catalog/courses/{course_id}/learning-paths/latest"
    ]
    assert "post" in paths["/api/v1/courses/{course_id}/documents"]
    assert "get" in paths["/api/v1/courses/{course_id}/documents"]
    assert "get" in paths["/api/v1/courses/{course_id}/quality-gate"]
    assert "post" in paths["/api/v1/courses/{course_id}/quality-gate/build"]
    assert "get" in paths["/api/v1/document-jobs/{job_id}"]
    assert "post" in paths["/api/v1/document-jobs/{job_id}/retry"]
    assert "get" in paths["/api/v1/courses/versions/{course_version_id}/analysis"]
    assert "patch" in paths["/api/v1/courses/versions/{course_version_id}/analysis"]
    assert "get" in paths["/api/v1/courses/versions/{course_version_id}/rag"]
    assert "post" in paths["/api/v1/courses/versions/{course_version_id}/rag/index"]
    assert "post" in paths["/api/v1/courses/versions/{course_version_id}/rag/search"]
    assert "get" in paths["/api/v1/courses/versions/{course_version_id}/catalog"]
    assert "patch" in paths["/api/v1/courses/versions/{course_version_id}/catalog"]
    assert "post" in paths["/api/v1/courses/versions/{course_version_id}/catalog/build"]
    assert "get" in paths["/api/v1/courses/versions/{course_version_id}/preview"]
    assert "patch" in paths["/api/v1/courses/versions/{course_version_id}/preview"]
    assert "delete" in paths["/api/v1/courses/versions/{course_version_id}/document"]


def test_content_routes_require_teacher_or_admin_bearer_auth() -> None:
    schema = app.openapi()

    assert schema["paths"]["/api/v1/courses"]["post"]["security"] == [
        {"HTTPBearer": []}
    ]
    assert schema["paths"]["/api/v1/courses/{course_id}/documents"]["post"][
        "security"
    ] == [{"HTTPBearer": []}]


def test_student_catalog_routes_require_bearer_auth() -> None:
    paths = app.openapi()["paths"]

    assert paths["/api/v1/catalog/courses"]["get"]["security"] == [{"HTTPBearer": []}]
    assert paths["/api/v1/catalog/courses/{course_id}"]["get"]["security"] == [
        {"HTTPBearer": []}
    ]


def test_concept_description_prefers_relevant_source_sentence() -> None:
    description = focused_concept_description(
        "Thuật luyện kim được phát minh",
        (
            "Cư dân cổ trồng lúa nước.\n"
            "Thuật luyện kim giúp con người chế tạo công cụ bằng đồng bền hơn.\n"
            "Đời sống xã hội có nhiều thay đổi."
        ),
        "Những chuyển biến trong đời sống kinh tế.",
    )

    assert description == (
        "Thuật luyện kim giúp con người chế tạo công cụ bằng đồng bền hơn."
    )


def test_course_onboarding_rejects_invalid_date_order() -> None:
    with pytest.raises(ValidationError):
        LearnerCourseProfileUpsert(
            learning_goal="Hoàn thành kiến thức lịch sử lớp 8",
            start_date="2026-08-10",
            deadline="2026-08-01",
            minutes_per_day=45,
            days_per_week=4,
            available_periods=["evening"],
            content_formats=["reading"],
        )


def test_course_onboarding_normalizes_duplicate_choices() -> None:
    payload = LearnerCourseProfileUpsert(
        learning_goal="Hoàn thành kiến thức lịch sử lớp 8",
        start_date="2026-08-01",
        deadline="2026-10-01",
        minutes_per_day=45,
        days_per_week=4,
        available_periods=["evening", " evening "],
        content_formats=["reading", "reading"],
    )

    assert payload.available_periods == ["evening"]
    assert payload.content_formats == ["reading"]


def test_diagnostic_question_does_not_leak_answer_or_internal_source() -> None:
    question = public_question(
        {
            "id": "82a1b535-7382-42f7-9040-69f80823bddd",
            "concept_id": "464c0cc3-88cc-453a-aeba-50d18bd18f3e",
            "prompt": "Chọn đáp án phù hợp",
            "lesson_title": "Bài 1",
            "options": ["A", "B"],
            "source_label": "Trang 1",
            "correct_index": 1,
            "source_chunk_id": "internal-chunk-id",
        }
    )

    assert "correct_index" not in question
    assert "source_chunk_id" not in question
