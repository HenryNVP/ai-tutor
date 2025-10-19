from __future__ import annotations

import logging
from dataclasses import dataclass
import re
from typing import Callable, Dict, List, Optional

from ai_tutor.config.schema import RetrievalConfig
from ai_tutor.data_models import Query, RetrievalHit
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.retrieval.retriever import Retriever
from ai_tutor.retrieval.vector_store import VectorStore
from ai_tutor.search.tool import SearchResult, SearchTool

from .context_builder import build_messages
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class TutorResponse:
    """Structured answer bundle returned to callers, including hits and formatted citations."""

    answer: str
    hits: List[RetrievalHit]
    citations: List[str]
    style: str
    next_topic: Optional[str] = None
    difficulty: Optional[str] = None


class TutorAgent:
    """Coordinates retrieval-augmented prompting to produce grounded tutoring answers."""

    MIN_CONFIDENCE = 0.2

    def __init__(
        self,
        retrieval_config: RetrievalConfig,
        embedder: EmbeddingClient,
        vector_store: VectorStore,
        llm_client: LLMClient,
        search_tool: Optional[SearchTool] = None,
    ):
        """Cache collaborating components and build a Retriever with the shared embedder."""
        self.embedder = embedder
        self.vector_store = vector_store
        self.llm = llm_client
        self.retriever = Retriever(
            retrieval_config, embedder=self.embedder, vector_store=self.vector_store
        )
        self.search_tool = search_tool

    def answer(
        self,
        question: str,
        mode: str = "learning",
        history: Optional[List[Dict[str, str]]] = None,
        style: Optional[str] = None,
        style_resolver: Optional[Callable[[List[RetrievalHit]], str]] = None,
    ) -> TutorResponse:
        """
        Retrieve supporting evidence and craft a cited answer for the learner.

        Builds a `Query`, gathers hits through the `Retriever`, filters them for confident matches,
        and if none survive, falls back to external search. Otherwise it assembles prompt messages via
        `build_messages`, optionally weaving in recent session history and a style supplied through
        `style` or lazily computed by `style_resolver`, invokes `LLMClient.generate`, and returns the
        generated answer alongside citations and the applied style.
        """
        query = Query(text=question)
        hits = self.retriever.retrieve(query)
        filtered_hits = self._filter_hits(hits)

        if not filtered_hits:
            search_results = self._run_search(question)
            selected_style = style or (style_resolver([]) if style_resolver else "scaffolded")
            if search_results:
                return self._answer_from_search(
                    question=question,
                    search_results=search_results,
                    mode=mode,
                    style=selected_style,
                    history=history,
                )
            logger.info("No retrieval hits or search results found for query.")
            message = "I could not find relevant material in the ingested corpus yet."
            return TutorResponse(
                answer=message,
                hits=[],
                citations=[],
                style=selected_style,
            )

        selected_style = style or (style_resolver(filtered_hits) if style_resolver else "stepwise")
        messages = build_messages(
            question,
            filtered_hits,
            mode=mode,
            style=selected_style,
            history=history,
        )
        self._log_prompt(messages)
        answer = self.llm.generate(messages)
        citations = self._select_citations(filtered_hits)
        if not citations:
            # No high-confidence local evidence, retry with web search path
            search_results = self._run_search(question)
            if search_results:
                return self._answer_from_search(
                    question=question,
                    search_results=search_results,
                    mode=mode,
                    style=selected_style,
                    history=history,
                )
            answer = self._strip_citation_markers(answer)
        return TutorResponse(
            answer=answer,
            hits=filtered_hits,
            citations=citations,
            style=selected_style,
        )

    @staticmethod
    def _format_citation(hit: RetrievalHit) -> str:
        """Convert a retrieval hit into a user-facing citation string with title and page."""
        metadata = hit.chunk.metadata
        page = metadata.page or "N/A"
        return f"{metadata.title} ({metadata.doc_id}) p.{page}"

    def _select_citations(self, hits: List[RetrievalHit], max_citations: int = 4) -> List[str]:
        """
        Filter, deduplicate, and cap citations based on hit score and evidence strength.

        Only keeps hits above a minimum score, merges citations that point to the same document
        (ignoring page differences), and returns the highest-scoring unique entries.
        """
        seen_docs: set[str] = set()
        filtered: List[tuple[float, str]] = []
        for hit in hits:
            if hit.score < self.MIN_CONFIDENCE:
                continue
            metadata = hit.chunk.metadata
            doc_key = metadata.doc_id.lower()
            if doc_key in seen_docs:
                continue
            seen_docs.add(doc_key)
            filtered.append((hit.score, self._format_citation(hit)))
        filtered.sort(key=lambda item: item[0], reverse=True)
        top_citations = [citation for _, citation in filtered[:max_citations]]
        return top_citations

    @staticmethod
    def _strip_citation_markers(answer: str) -> str:
        """Remove bracket-style citation markers when no supporting evidence is available."""
        cleaned = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", answer)
        return re.sub(r"\s{2,}", " ", cleaned).strip()

    @staticmethod
    def _log_prompt(messages: List[Dict[str, str]]) -> None:
        """Emit a trimmed view of the messages being sent to the LLM."""
        preview = []
        for message in messages:
            content = message.get("content", "")
            if len(content) > 500:
                content = content[:500] + "…"
            preview.append({"role": message.get("role"), "content": content})
        logger.debug("LLM prompt payload: %s", preview)

    def _run_search(self, question: str, max_results: int = 5) -> List[SearchResult]:
        """Invoke the configured search tool when local retrieval comes up empty."""
        if not self.search_tool:
            return []
        try:
            results = self.search_tool.search(question, max_results=max_results)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Search tool failed: %s", exc)
            return []
        return results or []

    def _answer_from_search(
        self,
        question: str,
        search_results: List[SearchResult],
        mode: str,
        style: str,
        history: Optional[List[Dict[str, str]]],
    ) -> TutorResponse:
        """Generate an answer grounded in external search snippets."""
        extra_context = self._format_search_context(search_results)
        messages = build_messages(
            question,
            hits=[],
            mode=mode,
            style=style,
            history=history,
            extra_context=extra_context,
        )
        self._log_prompt(messages)
        answer = self.llm.generate(messages)
        citations = self._search_citations(search_results)
        if not citations:
            answer = self._strip_citation_markers(answer)
        return TutorResponse(
            answer=answer,
            hits=[],
            citations=citations,
            style=style,
        )

    @staticmethod
    def _format_search_context(results: List[SearchResult]) -> str:
        """Format search results into a numbered context block for the LLM."""
        lines: List[str] = []
        for idx, result in enumerate(results, start=1):
            snippet = (result.snippet or "").strip()
            if len(snippet) > 400:
                snippet = snippet[:400] + "…"
            source = f"{result.title} ({result.url})"
            lines.append(f"[{idx}] {source}\n{snippet}")
        return "External search findings:\n" + "\n\n".join(lines)

    @staticmethod
    def _search_citations(results: List[SearchResult], max_citations: int = 4) -> List[str]:
        """Turn search results into compact citation strings, deduplicated by URL."""
        citations: List[str] = []
        seen_urls: set[str] = set()
        for result in results:
            url = (result.url or "").strip()
            normalized = url.lower()
            if normalized and normalized in seen_urls:
                continue
            if normalized:
                seen_urls.add(normalized)
            title = result.title or "External source"
            citation = f"{title} — {url}" if url else title
            citations.append(citation)
            if len(citations) >= max_citations:
                break
        return citations
    def _filter_hits(self, hits: List[RetrievalHit]) -> List[RetrievalHit]:
        """Keep only high-confidence hits with distinct documents for prompting."""
        filtered: List[RetrievalHit] = []
        seen_docs: set[str] = set()
        for hit in hits:
            if hit.score < self.MIN_CONFIDENCE:
                continue
            doc_key = hit.chunk.metadata.doc_id.lower()
            if doc_key in seen_docs:
                continue
            seen_docs.add(doc_key)
            filtered.append(hit)
        return filtered
