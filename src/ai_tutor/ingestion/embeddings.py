from __future__ import annotations

import logging
from typing import Iterable, List, Optional

import numpy as np
from ai_tutor.config.schema import EmbeddingConfig

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Wrapper around sentence-transformers models with lazy loading."""

    def __init__(self, config: EmbeddingConfig, api_key: Optional[str] = None):
        """Capture embedding configuration and defer model setup; `api_key` is ignored."""
        self.config = config
        self._model = None
        self._device: str = "cpu"

    def _ensure_model(self):
        """Instantiate the sentence-transformers model if it has not been loaded yet."""
        if self._model is not None:
            return
        provider = (self.config.provider or "sentence-transformers").lower()
        if provider in {"sentence-transformers", "hf", "huggingface"}:
            self._load_sentence_transformer()
        else:
            raise ValueError(f"Unsupported embedding provider: {self.config.provider}")

    def _load_sentence_transformer(self):
        """Load a sentence-transformers model onto the most suitable device.
        
        This is called lazily on first use to avoid blocking startup and starving
        the event loop. The model loading happens synchronously but only when needed.
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers package is required for embeddings."
            ) from exc
        device = self._select_device()
        logger.info("Loading embedding model %s on %s (lazy load)", self.config.model, device)
        try:
            self._model = SentenceTransformer(self.config.model, device=device)
            self._device = device
            logger.info("Embedding model loaded successfully on %s", device)
        except RuntimeError as exc:
            if device != "cpu":
                logger.warning(
                    "Failed to initialize embedding model on CUDA (%s); retrying on CPU.",
                    exc,
                )
                self._model = SentenceTransformer(self.config.model, device="cpu")
                self._device = "cpu"
                logger.info("Embedding model loaded on CPU fallback")
            else:
                raise

    def _select_device(self) -> str:
        """Choose CUDA when available, otherwise fall back to CPU execution."""
        try:
            import torch
        except ImportError:
            return "cpu"

        if not torch.cuda.is_available():
            return "cpu"

        try:
            torch.zeros(1, device="cuda")
        except Exception as exc:  # noqa: BLE001
            logger.warning("CUDA detected but unusable (%s); falling back to CPU.", exc)
            return "cpu"
        return "cuda"

    def _move_model_to_cpu(self) -> None:
        """Relocate the loaded model to the CPU, rebuilding it if necessary."""
        if self._model is None:
            return
        try:
            self._model = self._model.to("cpu")  # type: ignore[assignment]
        except AttributeError:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.config.model, device="cpu")
        self._device = "cpu"
        logger.info("Using CPU for embeddings.")

    def _encode_with_sentence_transformer(self, texts: List[str]) -> List[List[float]]:
        """Encode text with a local sentence-transformers model, retrying on CPU if needed."""
        self._ensure_model()
        assert self._model is not None
        try:
            embeddings = self._model.encode(
                texts,
                batch_size=self.config.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=self.config.normalize,
                device=self._device,
            )
        except RuntimeError as exc:
            if self._device != "cpu" and "cuda" in str(exc).lower():
                logger.warning(
                    "CUDA error during embedding (%s); switching to CPU.", exc
                )
                self._move_model_to_cpu()
                embeddings = self._model.encode(  # type: ignore[assignment]
                    texts,
                    batch_size=self.config.batch_size,
                    convert_to_numpy=True,
                    normalize_embeddings=self.config.normalize,
                    device=self._device,
                )
            else:
                raise
        if isinstance(embeddings, np.ndarray):
            embeddings = embeddings.tolist()
        if not embeddings:
            return []
        first_item = embeddings[0]
        if isinstance(first_item, (float, np.floating)):
            embeddings = [embeddings]  # type: ignore[list-item]
        normalized: List[List[float]] = []
        for vector in embeddings:
            if isinstance(vector, np.ndarray):
                vector = vector.tolist()
            normalized.append(list(vector))
        return normalized

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:
        """
        Embed document chunks using the configured sentence-transformers model.

        Collects the input iterable and runs `_encode_with_sentence_transformer`, returning
        the resulting batch of vectors ready for persistence in the vector store.
        """
        text_list = list(texts)
        if not text_list:
            return []
        return self._encode_with_sentence_transformer(text_list)

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a learner query so it can be compared against stored document vectors.

        Mirrors `embed_documents` but operates on a single string, producing a normalized vector
        for retrieval.
        """
        embeddings = self._encode_with_sentence_transformer([text])
        return embeddings[0]
