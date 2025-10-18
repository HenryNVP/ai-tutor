from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

from ai_tutor.config.schema import GuardrailConfig, SearchToolConfig
from ai_tutor.data_models import Query, RetrievalHit

logger = logging.getLogger(__name__)


@dataclass
class GuardrailResult:
    hits: List[RetrievalHit]
    should_search_web: bool
    reason: str | None = None


class GuardrailManager:
    def __init__(self, guardrail_config: GuardrailConfig, search_config: SearchToolConfig):
        self.guardrail_config = guardrail_config
        self.search_config = search_config

    def evaluate_hits(
        self, query: Query, hits: List[RetrievalHit], top_k: int
    ) -> GuardrailResult:
        filtered = [
            hit for hit in hits if hit.score >= self.guardrail_config.min_score
        ][:top_k]

        reason = None
        should_search = False

        if self._is_blocked_topic(query.text):
            reason = "Query rejected by safety filter."
            filtered = []
        elif len(filtered) < self.guardrail_config.min_hits:
            reason = (
                "Insufficient high-confidence evidence from local corpus."
            )
            should_search = self.search_config.enabled and (
                len(filtered) < self.search_config.min_hits_before_search
            )

        return GuardrailResult(
            hits=filtered,
            should_search_web=should_search,
            reason=reason,
        )

    def _is_blocked_topic(self, text: str) -> bool:
        lowered = text.lower()
        return any(topic in lowered for topic in self.guardrail_config.blocked_topics)
