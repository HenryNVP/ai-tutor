from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

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
    answer: str
    hits: List[RetrievalHit]
    citations: List[str]


class TutorAgent:
    def __init__(
        self,
        retrieval_config: RetrievalConfig,
        embedder: EmbeddingClient,
        vector_store: VectorStore,
        llm_client: LLMClient,
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.llm = llm_client
        self.retriever = Retriever(
            retrieval_config, embedder=self.embedder, vector_store=self.vector_store
        )

    def answer(self, question: str, mode: str = "learning") -> TutorResponse:
        query = Query(text=question)
        hits = self.retriever.retrieve(query)

        if not hits:
            logger.info("No retrieval hits found for query.")
            message = "I could not find relevant material in the ingested corpus yet."
            return TutorResponse(answer=message, hits=[], citations=[])

        messages = build_messages(
            question,
            hits,
            mode=mode,
            style="stepwise",
        )
        answer = self.llm.generate(messages)
        citations = [self._format_citation(hit) for hit in hits]
        return TutorResponse(
            answer=answer,
            hits=hits,
            citations=citations,
        )

    @staticmethod
    def _format_citation(hit: RetrievalHit) -> str:
        metadata = hit.chunk.metadata
        page = metadata.page or "N/A"
        return f"{metadata.title} ({metadata.doc_id}) p.{page}"
