"""
Academic Papers Tool — search Semantic Scholar for research papers.
Uses the free Semantic Scholar Graph API (no API key required).

Ported from WorkFlow/tools/academic_tool.py.
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger("workflow.academic")

_SS_API = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,authors,year,citationCount,openAccessPdf,externalIds"


def fetch_academic_papers(
    query: str, limit: int = 3,
) -> list[dict[str, Any]]:
    """
    Search Semantic Scholar for academic papers.

    Returns list of ``{title, authors, year, citation_count, pdf_url, semantic_url}``.
    """
    query = (query or "").strip()
    if not query:
        return []

    params = urllib.parse.urlencode(
        {"query": query, "limit": min(limit, 5), "fields": _FIELDS}
    )
    url = f"{_SS_API}?{params}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "NoteMind/1.0 (educational-tool)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        papers: list[dict[str, Any]] = []
        for p in data.get("data", [])[:limit]:
            authors = [a.get("name", "") for a in p.get("authors", [])[:4]]
            pdf_url = None
            oap = p.get("openAccessPdf")
            if isinstance(oap, dict):
                pdf_url = oap.get("url")

            paper_id = p.get("paperId", "")
            papers.append(
                {
                    "title": p.get("title", ""),
                    "authors": authors,
                    "year": p.get("year"),
                    "citation_count": p.get("citationCount", 0),
                    "pdf_url": pdf_url,
                    "semantic_url": (
                        f"https://www.semanticscholar.org/paper/{paper_id}"
                        if paper_id
                        else ""
                    ),
                }
            )

        logger.info("Found %d papers for query='%s'", len(papers), query)
        return papers

    except Exception as exc:
        logger.error("Exception: %s", exc)
        return []
