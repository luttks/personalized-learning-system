import pytest
from app.main import app
from app.services.exam_parser_service import parse_exam_questions
from app.services.workflow_tools.academic_tool import fetch_academic_papers
from app.services.workflow_tools.github_tool import search_github_repositories
from app.services.workflow_tools.quiz_search_tool import search_external_quizzes
from app.services.workflow_tools.wikipedia_tool import fetch_wikipedia_summary
from app.services.workflow_tools.youtube_tool import search_youtube_tutorials


def test_exam_workflow_routes_are_registered() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/exam-workflow/process-file" in paths
    assert "/api/v1/exam-workflow/parse-markdown" in paths
    assert "/api/v1/exam-workflow/recommend" in paths
    assert "/api/v1/exam-workflow/crawl-resources" in paths


def test_exam_parser_questions() -> None:
    sample_text = """
Câu 1: Giải phương trình $x^2 - 4 = 0$.
A. $x = 2$
B. $x = -2$
C. $x = \\pm 2$
D. Phương trình vô nghiệm

Câu 2: Đơn vị của lực trong hệ SI là gì?
A. Pascal
B. Newton
C. Joule
D. Watt
"""
    result = parse_exam_questions(sample_text)
    assert result["question_count"] >= 2
    assert len(result["questions"]) >= 2


def test_workflow_tools_import_and_fail_gracefully() -> None:
    # Test empty query handling
    assert search_youtube_tutorials("", limit=2) == []
    assert search_external_quizzes("", limit=2) == []
    assert fetch_academic_papers("", limit=2) == []
    assert search_github_repositories("", limit=2) == []
    assert fetch_wikipedia_summary("")["status"] == "error"
