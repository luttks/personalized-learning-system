"""
GitHub Repository Tool — search top-starred repositories for a topic.
Uses the public GitHub Search API. Authenticated if GITHUB_TOKEN is set.

Ported from WorkFlow/tools/github_tool.py.
"""

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger("workflow.github")

_GH_API = "https://api.github.com/search/repositories"


def search_github_repositories(
    topic: str, limit: int = 3,
) -> list[dict[str, Any]]:
    """
    Search GitHub for repositories sorted by stars.

    Returns list of ``{full_name, stars, language, description, url}``.
    """
    topic = (topic or "").strip()
    if not topic:
        return []

    params = urllib.parse.urlencode(
        {"q": topic, "sort": "stars", "order": "desc", "per_page": min(limit, 5)}
    )
    url = f"{_GH_API}?{params}"

    headers: dict[str, str] = {
        "User-Agent": "NoteMind/1.0 (educational-tool)",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Use token if available to avoid rate-limiting
    token = os.getenv("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        repos: list[dict[str, Any]] = []
        for item in data.get("items", [])[:limit]:
            repos.append(
                {
                    "full_name": item.get("full_name", ""),
                    "stars": item.get("stargazers_count", 0),
                    "language": item.get("language"),
                    "description": (item.get("description") or "")[:200],
                    "url": item.get("html_url", ""),
                }
            )

        logger.info("Found %d repos for topic='%s'", len(repos), topic)
        return repos

    except Exception as exc:
        logger.error("Exception: %s", exc)
        return []
