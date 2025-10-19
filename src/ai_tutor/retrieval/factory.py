from __future__ import annotations

from pathlib import Path

from ai_tutor.retrieval.simple_store import SimpleVectorStore
from ai_tutor.retrieval.vector_store import VectorStore


def create_vector_store(path: Path) -> VectorStore:
    """Instantiate the current vector store implementation rooted at `path`."""
    # For now we default to the simple cosine similarity store.
    return SimpleVectorStore.from_path(path)
