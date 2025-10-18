from __future__ import annotations

import logging
from typing import Iterable, List

import numpy as np

from ai_tutor.config.schema import EmbeddingConfig

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Wrapper around sentence-transformers style models with lazy loading."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._model = None

    def _ensure_model(self):
        if self._model is not None:
            return
        provider = self.config.provider.lower()
        if provider in {"sentence-transformers", "hf", "huggingface"}:
            self._load_sentence_transformer()
        else:
            raise ValueError(f"Unsupported embedding provider: {self.config.provider}")

    def _load_sentence_transformer(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers package is required for embeddings."
            ) from exc
        logger.info("Loading embedding model %s", self.config.model)
        self._model = SentenceTransformer(self.config.model)

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:
        self._ensure_model()
        assert self._model is not None
        embeddings = self._model.encode(
            list(texts),
            batch_size=self.config.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.config.normalize,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        self._ensure_model()
        assert self._model is not None
        embedding = self._model.encode(
            text,
            batch_size=self.config.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.config.normalize,
        )
        if isinstance(embedding, np.ndarray):
            return embedding.tolist()
        return embedding
