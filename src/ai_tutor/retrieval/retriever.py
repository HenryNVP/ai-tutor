from __future__ import annotations

import logging
from typing import List

from ai_tutor.config.schema import RetrievalConfig
from ai_tutor.data_models import Query, RetrievalHit
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


class Retriever:
    """Thin helper that embeds queries and searches the configured vector store."""

    def __init__(
        self,
        config: RetrievalConfig,
        embedder: EmbeddingClient,
        vector_store: VectorStore,
    ):
        """Store dependencies needed to embed queries and perform similarity search."""
        self.config = config
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve(self, query: Query) -> List[RetrievalHit]:
        """
        Embed the incoming query, run vector search, and log the number of hits found.

        Uses `EmbeddingClient.embed_query` to derive the vector, then delegates to
        `VectorStore.search` with the configured `top_k` before returning the ranked hits.
        """
        embedding = self.embedder.embed_query(query.text)
        hits = self.vector_store.search(embedding, self.config.top_k)
        logger.info("Retrieved %s hits.", len(hits))
        return hits
