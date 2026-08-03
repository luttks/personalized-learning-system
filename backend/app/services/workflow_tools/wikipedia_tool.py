"""
Wikipedia Tool — fetch a short summary for an academic concept.

Uses the Wikipedia REST API (no API key required).
Ported from WorkFlow/tools/wikipedia_tool.py.
"""

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger("workflow.wikipedia")


def fetch_wikipedia_summary(
    concept: str, language: str = "vi"
) -> dict[str, Any]:
    """
    Retrieve a 2-3 sentence summary from Wikipedia.

    Args:
        concept: The term or concept to look up.
        language: Wikipedia language code ("vi" or "en").

    Returns:
        {
            "title": str,
            "summary": str,
            "url": str,
            "status": "success" | "not_found" | "error"
        }
    """
    concept = (concept or "").strip()
    if not concept:
        return {"status": "error", "title": "", "summary": "", "url": ""}

    # Encode concept for URL
    encoded = urllib.parse.quote(concept, safe="")
    url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{encoded}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "NoteMind/1.0 (educational-tool; contact@notemind.app)"
                ),
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        extract = data.get("extract", "")
        # Trim to first 3 sentences
        sentences = re.split(r"(?<=[.!?])\s+", extract)
        short_summary = " ".join(sentences[:3]).strip()

        logger.info("Found Wikipedia entry: %s", data.get("title"))
        return {
            "status": "success",
            "title": data.get("title", concept),
            "summary": short_summary,
            "url": data.get("content_urls", {})
            .get("desktop", {})
            .get("page", ""),
        }

    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Fallback to English if Vietnamese not found
            if language == "vi":
                logger.info(
                    "Not found in vi, trying en for: %s", concept
                )
                return fetch_wikipedia_summary(concept, language="en")
            logger.warning("Not found: %s", concept)
            return {
                "status": "not_found",
                "title": concept,
                "summary": "",
                "url": "",
            }
        logger.error("HTTP %d for concept='%s'", e.code, concept)
        return {"status": "error", "title": concept, "summary": "", "url": ""}

    except Exception as exc:
        logger.error("Exception: %s", exc)
        return {"status": "error", "title": concept, "summary": "", "url": ""}
