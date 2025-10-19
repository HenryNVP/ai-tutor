from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Tuple

from ai_tutor.data_models import Chunk, RetrievalHit


class VectorStore(ABC):
    """Abstract interface for vector stores used by the tutor."""

    @abstractmethod
    def add(self, chunks: Iterable[Chunk]) -> None:
        """Insert or update chunk embeddings within the store."""

    @abstractmethod
    def search(self, embedding: List[float], top_k: int) -> List[RetrievalHit]:
        """Return the top-k matches for the provided embedding."""

    @abstractmethod
    def persist(self) -> None:
        """Flush any in-memory state to persistent storage."""

    @classmethod
    @abstractmethod
    def from_path(cls, path: Path) -> "VectorStore":
        """Instantiate a vector store using resources stored at the supplied path."""
