"""
Quiz Search Tool — search for external quizzes on a topic using DuckDuckGo HTML.

Ported from WorkFlow/tools/quiz_search_tool.py.
"""

import logging
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

logger = logging.getLogger("workflow.quiz_search")


def search_external_quizzes(
    query: str, limit: int = 5,
) -> list[dict[str, str]]:
    """
    Search DuckDuckGo for external quizzes.

    Returns list of ``{title, url, snippet}``.
    """
    query = (query or "").strip()
    if not query:
        return []

    # Append quiz keywords if missing
    lower = query.lower()
    if "quiz" not in lower and "trắc nghiệm" not in lower and "test" not in lower:
        search_query = query + " quiz test"
    else:
        search_query = query

    logger.info("Searching for: '%s'", search_query)

    encoded = urllib.parse.quote_plus(search_query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "vi,en;q=0.9",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")

        soup = BeautifulSoup(html, "html.parser")
        results: list[dict[str, str]] = []

        for result in soup.find_all("div", class_="result"):
            title_tag = result.find("h2", class_="result__title")
            snippet_tag = result.find("a", class_="result__snippet")
            url_tag = result.find("a", class_="result__url")

            if title_tag and url_tag:
                title = title_tag.get_text(separator=" ", strip=True)
                link = url_tag.get("href", "")
                if link.startswith("//duckduckgo.com/l/?uddg="):
                    link = urllib.parse.unquote(
                        link.split("uddg=")[1].split("&")[0]
                    )

                snippet = (
                    snippet_tag.get_text(separator=" ", strip=True)
                    if snippet_tag
                    else ""
                )

                results.append(
                    {"title": title, "url": link, "snippet": snippet}
                )

                if len(results) >= limit:
                    break

        logger.info("Found %d results", len(results))
        return results

    except Exception as exc:
        logger.error("Exception: %s", exc)
        return []
