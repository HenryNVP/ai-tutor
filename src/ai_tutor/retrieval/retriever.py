from __future__ import annotations

import logging
from typing import List

from ai_tutor.config.schema import RetrievalConfig
from ai_tutor.data_models import Query, RetrievalHit
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(
        self,
        config: RetrievalConfig,
        embedder: EmbeddingClient,
        vector_store: VectorStore,
    ):
        self.config = config
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve(self, query: Query) -> List[RetrievalHit]:
        embedding = self.embedder.embed_query(query.text)
        hits = self.vector_store.search(embedding, self.config.top_k)
        logger.info("Retrieved %s hits.", len(hits))
        return hits
