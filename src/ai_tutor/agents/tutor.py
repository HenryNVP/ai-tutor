from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from ai_tutor.config.schema import RetrievalConfig
from ai_tutor.data_models import Query, RetrievalHit
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.retrieval.retriever import Retriever
from ai_tutor.retrieval.vector_store import VectorStore

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

    def __init__(
        self,
        retrieval_config: RetrievalConfig,
        embedder: EmbeddingClient,
        vector_store: VectorStore,
        llm_client: LLMClient,
    ):
        """Cache collaborating components and build a Retriever with the shared embedder."""
        self.embedder = embedder
        self.vector_store = vector_store
        self.llm = llm_client
        self.retriever = Retriever(
            retrieval_config, embedder=self.embedder, vector_store=self.vector_store
        )

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

        Builds a `Query`, gathers hits through the `Retriever`, and shortcuts with a helpful
        fallback if nothing is retrieved. Otherwise it assembles prompt messages via
        `build_messages`, optionally weaving in recent session history and a style supplied
        through `style` or lazily computed by `style_resolver`, invokes `LLMClient.generate`,
        and returns the generated answer alongside citations and the applied style.
        """
        query = Query(text=question)
        hits = self.retriever.retrieve(query)

        if not hits:
            logger.info("No retrieval hits found for query.")
            message = "I could not find relevant material in the ingested corpus yet."
            selected_style = style or (style_resolver([]) if style_resolver else "scaffolded")
            return TutorResponse(
                answer=message,
                hits=[],
                citations=[],
                style=selected_style,
            )

        selected_style = style or (style_resolver(hits) if style_resolver else "stepwise")
        messages = build_messages(
            question,
            hits,
            mode=mode,
            style=selected_style,
            history=history,
        )
        answer = self.llm.generate(messages)
        citations = self._select_citations(hits)
        return TutorResponse(
            answer=answer,
            hits=hits,
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
        MIN_SCORE = 0.2
        seen_docs: set[str] = set()
        filtered: List[tuple[float, str]] = []
        for hit in hits:
            if hit.score < MIN_SCORE:
                continue
            metadata = hit.chunk.metadata
            doc_key = metadata.doc_id.lower()
            if doc_key in seen_docs:
                continue
            seen_docs.add(doc_key)
            filtered.append((hit.score, self._format_citation(hit)))
        filtered.sort(key=lambda item: item[0], reverse=True)
        return [citation for _, citation in filtered[:max_citations]]
