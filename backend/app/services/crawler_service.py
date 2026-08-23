"""
Crawler Service — parallel resource crawling for educational content.

Crawls YouTube, DuckDuckGo quizzes, Semantic Scholar papers, and GitHub
repositories in parallel using asyncio + ThreadPoolExecutor.

Ported from WorkFlow/crawler_service.py.
"""

from __future__ import annotations

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.services.workflow_tools.academic_tool import fetch_academic_papers
from app.services.workflow_tools.github_tool import search_github_repositories
from app.services.workflow_tools.quiz_search_tool import search_external_quizzes
from app.services.workflow_tools.youtube_tool import search_youtube_tutorials

logger = logging.getLogger("workflow.crawler")

_executor = ThreadPoolExecutor(max_workers=10)


def extract_search_terms(text: str) -> str:
    """
    Normalise a question/exercise text into optimised search keywords.

    Strips raw LaTeX (``$…$``), Markdown markers, and question numbering
    to keep only the conceptual / theoretical terms.
    """
    if not text:
        return ""

    # Remove display math blocks $$ … $$
    clean = re.sub(r"\$\$[\s\S]*?\$\$", "", text)
    # Remove inline math $ … $
    clean = re.sub(r"\$[^$\n]+?\$", "", clean)
    # Remove question numbering (Câu I, Bài 1, 1., 2., …)
    clean = re.sub(
        r"^(Câu|Bài)\s+[IVXLCDM0-9]+[:\.]?", "", clean, flags=re.IGNORECASE
    )
    clean = re.sub(r"^[0-9]+[\.\)]\s*", "", clean)
    # Remove Markdown formatting chars
    clean = re.sub(r"[#\*_\`]", " ", clean)

    lines = [line.strip() for line in clean.split("\n") if line.strip()]
    search_str = " ".join(lines)
    search_str = re.sub(r"\s+", " ", search_str).strip()

    # Return at most 120 chars
    return search_str[:120] if search_str else text[:120]


async def crawl_resources_parallel(query: str) -> dict[str, Any]:
    """
    Crawl multiple educational sources in parallel.

    Sources: YouTube, DuckDuckGo quizzes, Semantic Scholar, GitHub.
    All crawlers run concurrently via ``asyncio.gather`` +
    ``ThreadPoolExecutor`` for maximum speed.
    """
    search_query = extract_search_terms(query)
    logger.info("Starting parallel crawl for: '%s'", search_query)

    loop = asyncio.get_running_loop()

    # Launch all crawl tasks in parallel
    youtube_task = loop.run_in_executor(
        _executor, search_youtube_tutorials, search_query, 3,
    )
    quiz_task = loop.run_in_executor(
        _executor, search_external_quizzes, search_query, 4,
    )
    academic_task = loop.run_in_executor(
        _executor, fetch_academic_papers, search_query, 3,
    )
    github_task = loop.run_in_executor(
        _executor, search_github_repositories, search_query, 3,
    )

    youtube_res, quiz_res, academic_res, github_res = await asyncio.gather(
        youtube_task,
        quiz_task,
        academic_task,
        github_task,
        return_exceptions=True,
    )

    # Safely unpack results (avoid crash if one source fails)
    youtube_data = youtube_res if isinstance(youtube_res, list) else []
    quiz_data = quiz_res if isinstance(quiz_res, list) else []
    academic_data = academic_res if isinstance(academic_res, list) else []
    github_data = github_res if isinstance(github_res, list) else []

    total_sources = (
        len(youtube_data)
        + len(quiz_data)
        + len(academic_data)
        + len(github_data)
    )

    logger.info("Crawl finished. Total items found: %d", total_sources)

    return {
        "search_query": search_query,
        "raw_input": query[:200],
        "total_items": total_sources,
        "youtube_tutorials": youtube_data,
        "quiz_exercises": quiz_data,
        "academic_papers": academic_data,
        "github_repos": github_data,
    }
