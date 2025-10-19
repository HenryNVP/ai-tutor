from __future__ import annotations

import logging
import os
from typing import Iterable, List, Optional

import numpy as np

from ai_tutor.config.schema import EmbeddingConfig

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Wrapper around sentence-transformers style models with lazy loading."""

    def __init__(self, config: EmbeddingConfig, api_key: Optional[str] = None):
        self.config = config
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
        self._model = None
        self._litellm = None
        self._genai = None
        self._google_configured = False
        self._device: str = "cpu"

    def _ensure_model(self):
        if self._model is not None:
            return
        provider = self.config.provider.lower()
        if provider in {"sentence-transformers", "hf", "huggingface"}:
            self._load_sentence_transformer()
        elif provider == "litellm":
            self._load_litellm()
        elif provider in {"google-genai", "google", "gemini"}:
            self._configure_google()
        else:
            raise ValueError(f"Unsupported embedding provider: {self.config.provider}")

    def _load_sentence_transformer(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers package is required for embeddings."
            ) from exc
        device = self._select_device()
        logger.info("Loading embedding model %s on %s", self.config.model, device)
        try:
            self._model = SentenceTransformer(self.config.model, device=device)
            self._device = device
        except RuntimeError as exc:
            if device != "cpu":
                logger.warning(
                    "Failed to initialize embedding model on CUDA (%s); retrying on CPU.",
                    exc,
                )
                self._model = SentenceTransformer(self.config.model, device="cpu")
                self._device = "cpu"
            else:
                raise

    def _load_litellm(self):
        if self._litellm is not None:
            return
        try:
            import litellm
        except ImportError as exc:
            raise RuntimeError("litellm package is required for embeddings provider 'litellm'.") from exc
        self._litellm = litellm

    def _configure_google(self):
        if self._google_configured:
            return
        if not self.api_key:
            raise RuntimeError("Google Generative AI embeddings require an API key.")
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise RuntimeError(
                "google-generativeai package is required for embeddings provider 'google-genai'."
            ) from exc
        genai.configure(api_key=self.api_key)
        self._genai = genai
        self._google_configured = True

    @staticmethod
    def _normalize(vector: List[float]) -> List[float]:
        array = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(array)
        if norm == 0:
            return vector
        return (array / norm).tolist()

    def _litellm_kwargs(self, texts: List[str]) -> dict:
        kwargs = {
            "model": self.config.model,
            "input": texts,
            "api_key": self.api_key,
        }
        if self.config.dimension is not None:
            # Different providers expect different field names; include both.
            kwargs["dimensions"] = self.config.dimension
            kwargs["output_dimensionality"] = self.config.dimension
        return kwargs

    def _embed_with_litellm(self, texts: List[str]) -> List[List[float]]:
        self._load_litellm()
        assert self._litellm is not None
        kwargs = self._litellm_kwargs(texts)
        response = self._litellm.embedding(**kwargs)
        data = getattr(response, "data", None)
        if not data:
            raise RuntimeError("Embedding response did not contain data.")
        embeddings: List[List[float]] = []
        for item in data:
            embedding = None
            if isinstance(item, dict):
                embedding = item.get("embedding")
            else:
                embedding = getattr(item, "embedding", None)
            if embedding is None:
                raise RuntimeError("Embedding item missing 'embedding' vector.")
            embeddings.append(list(embedding))

        if self.config.normalize:
            embeddings = [self._normalize(vector) for vector in embeddings]
        return embeddings

    def _embed_with_google(self, texts: List[str], task_type: str) -> List[List[float]]:
        self._configure_google()
        assert self._genai is not None
        embeddings: List[List[float]] = []
        for text in texts:
            kwargs = {
                "model": self.config.model,
                "content": text,
                "task_type": task_type,
            }
            if self.config.dimension is not None:
                kwargs["output_dimensionality"] = self.config.dimension
            response = self._genai.embed_content(**kwargs)
            if isinstance(response, dict):
                embedding = response.get("embedding")
            else:
                embedding = getattr(response, "embedding", None)
            if embedding is None:
                raise RuntimeError("Google Generative AI response missing 'embedding'.")
            vector = list(embedding)
            if self.config.normalize:
                vector = self._normalize(vector)
            embeddings.append(vector)
        return embeddings

    def _select_device(self) -> str:
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
        text_list = list(texts)
        if not text_list:
            return []
        provider = self.config.provider.lower()
        if provider in {"sentence-transformers", "hf", "huggingface"}:
            return self._encode_with_sentence_transformer(text_list)
        if provider == "litellm":
            return self._embed_with_litellm(text_list)
        if provider in {"google-genai", "google", "gemini"}:
            return self._embed_with_google(text_list, task_type="retrieval_document")
        raise ValueError(f"Unsupported embedding provider: {self.config.provider}")

    def embed_query(self, text: str) -> List[float]:
        provider = self.config.provider.lower()
        if provider in {"sentence-transformers", "hf", "huggingface"}:
            embeddings = self._encode_with_sentence_transformer([text])
            return embeddings[0]
        if provider == "litellm":
            embeddings = self._embed_with_litellm([text])
            return embeddings[0]
        if provider in {"google-genai", "google", "gemini"}:
            embeddings = self._embed_with_google([text], task_type="retrieval_query")
            return embeddings[0]
        raise ValueError(f"Unsupported embedding provider: {self.config.provider}")
