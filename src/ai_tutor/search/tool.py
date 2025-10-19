from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Structured result returned by a web search implementation."""

    title: str
    snippet: str
    url: str
    published_at: str | None = None


class SearchTool:
    """Interface for controlled web search."""

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Perform a web search using DuckDuckGo when available, else return fallback results."""
        try:
            from duckduckgo_search import DDGS  # type: ignore[import]
        except ImportError:
            logger.warning(
                "duckduckgo-search not installed; returning fallback search results for query '%s'.",
                query,
            )
            return self._fallback_results(query)

        try:
            results = []
            with DDGS() as ddgs:
                for item in ddgs.text(query, max_results=max_results):
                    title = item.get("title") or "DuckDuckGo Result"
                    snippet = item.get("body") or ""
                    url = item.get("href") or ""
                    results.append(SearchResult(title=title, snippet=snippet, url=url))
            if results:
                return results
        except Exception as exc:  # noqa: BLE001
            logger.warning("DuckDuckGo search failed (%s); using fallback content.", exc)
        return self._fallback_results(query)

    @staticmethod
    def _fallback_results(query: str) -> List[SearchResult]:
        """Return a deterministic placeholder result when live search is unavailable."""
        snippet = (
            f"No live web search was available. Review authoritative resources about '{query}' "
            "from academic references or well-sourced encyclopedias."
        )
        return [
            SearchResult(
                title="External reference guidance",
                snippet=snippet,
                url="https://example.com/search-guidance",
            )
        ]
