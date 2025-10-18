from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from ai_tutor.config.schema import Settings
from ai_tutor.data_models import Query, RetrievalHit
from ai_tutor.guardrails import GuardrailManager
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.retrieval.retriever import Retriever
from ai_tutor.retrieval.vector_store import VectorStore
from ai_tutor.search import SearchResult, SearchTool

from .context_builder import build_messages
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class TutorResponse:
    answer: str
    hits: List[RetrievalHit]
    citations: List[str]
    guardrail_reason: Optional[str] = None
    used_search: bool = False
    search_results: List[SearchResult] | None = None


class TutorAgent:
    def __init__(
        self,
        settings: Settings,
        embedder: EmbeddingClient,
        vector_store: VectorStore,
        guardrails: GuardrailManager,
        search_tool: SearchTool | None,
        llm_client: LLMClient,
    ):
        self.settings = settings
        self.embedder = embedder
        self.vector_store = vector_store
        self.guardrails = guardrails
        self.search_tool = search_tool
        self.llm = llm_client
        self.retriever = Retriever(
            settings.retrieval, embedder=self.embedder, vector_store=self.vector_store, guardrails=self.guardrails
        )

    def answer(self, question: str, mode: str = "learning") -> TutorResponse:
        query = Query(text=question)
        guardrail_result = self.retriever.retrieve(query)

        if guardrail_result.reason and not guardrail_result.hits:
            logger.warning("Guardrail refusal for query: %s", guardrail_result.reason)
            return TutorResponse(
                answer=guardrail_result.reason,
                hits=[],
                citations=[],
                guardrail_reason=guardrail_result.reason,
            )

        hits = guardrail_result.hits
        search_results: List[SearchResult] = []
        used_search = False

        if guardrail_result.should_search_web and self.search_tool:
            logger.info("Invoking search tool for query.")
            search_results = self.search_tool.search(
                query.text, max_results=self.settings.search_tool.max_results
            )
            used_search = bool(search_results)

        if not hits and not used_search:
            message = (
                "I don't have enough evidence in your materials. "
                "I can search the web or suggest a study plan."
            )
            return TutorResponse(
                answer=message,
                hits=[],
                citations=[],
                guardrail_reason="insufficient_context",
            )

        messages = build_messages(
            question,
            hits,
            mode=mode,
            style="stepwise",
        )
        answer = self.llm.generate(messages)
        citations = [
            self._format_citation(hit)
            for hit in hits
        ]
        return TutorResponse(
            answer=answer,
            hits=hits,
            citations=citations,
            guardrail_reason=guardrail_result.reason,
            used_search=used_search,
            search_results=search_results or None,
        )

    @staticmethod
    def _format_citation(hit: RetrievalHit) -> str:
        metadata = hit.chunk.metadata
        page = metadata.page or "N/A"
        return f"{metadata.title} ({metadata.doc_id}) p.{page}"
