from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Tuple

from ai_tutor.data_models import Chunk, RetrievalHit


class VectorStore(ABC):
    """Abstract interface for vector stores used by the tutor."""

    @abstractmethod
    def add(self, chunks: Iterable[Chunk]) -> None:
        ...

    @abstractmethod
    def search(self, embedding: List[float], top_k: int) -> List[RetrievalHit]:
        ...

    @abstractmethod
    def persist(self) -> None:
        ...

    @classmethod
    @abstractmethod
    def from_path(cls, path: Path) -> "VectorStore":
        ...
