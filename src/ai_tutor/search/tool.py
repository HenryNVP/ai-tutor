from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str
    published_at: str | None = None


class SearchTool:
    """Interface for controlled web search."""

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        logger.warning("Search tool not configured; returning empty results.")
        return []
