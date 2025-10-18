from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ai_tutor.data_models import Chunk, RetrievalHit

from .vector_store import VectorStore


class SimpleVectorStore(VectorStore):
    """Lightweight cosine-similarity vector store persisted on disk."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.embeddings_path = self.directory / "embeddings.npy"
        self.metadata_path = self.directory / "metadata.json"
        self._chunks: Dict[str, Chunk] = {}
        self._chunk_ids: List[str] = []
        self._matrix: np.ndarray | None = None
        self._load()

    def _load(self) -> None:
        if self.embedding_file_exists and self.metadata_path.exists():
            self._matrix = np.load(self.embeddings_path)
            with self.metadata_path.open("r", encoding="utf-8") as handle:
                serialized = json.load(handle)
            chunk_ids = serialized.get("chunk_ids", [])
            chunks = serialized.get("chunks", {})
            self._chunk_ids = chunk_ids
            self._chunks = {
                chunk_id: Chunk.model_validate(chunks[chunk_id])
                for chunk_id in chunk_ids
                if chunk_id in chunks
            }
            if self._matrix is not None and len(self._chunk_ids) != len(self._matrix):
                # Rebuild matrix if mismatch
                embeddings = [
                    self._chunks[chunk_id].embedding
                    for chunk_id in self._chunk_ids
                    if self._chunks[chunk_id].embedding is not None
                ]
                if embeddings:
                    self._matrix = np.array(embeddings)
                else:
                    self._matrix = None

    @property
    def embedding_file_exists(self) -> bool:
        return self.embeddings_path.exists()

    def add(self, chunks: Iterable[Chunk]) -> None:
        new_chunks = [chunk for chunk in chunks if chunk.embedding is not None]
        if not new_chunks:
            return
        to_add: List[Chunk] = []
        for chunk in new_chunks:
            chunk_id = chunk.metadata.chunk_id
            if chunk_id in self._chunk_ids:
                idx = self._chunk_ids.index(chunk_id)
                assert self._matrix is not None
                self._matrix[idx] = chunk.embedding  # type: ignore[index]
            else:
                to_add.append(chunk)

        if to_add:
            embeddings = np.array([chunk.embedding for chunk in to_add])
            if self._matrix is None:
                self._matrix = embeddings
            else:
                self._matrix = np.vstack([self._matrix, embeddings])

        for chunk in new_chunks:
            chunk_id = chunk.metadata.chunk_id
            self._chunks[chunk_id] = chunk
            if chunk_id not in self._chunk_ids:
                self._chunk_ids.append(chunk_id)

    def search(self, embedding: List[float], top_k: int) -> List[RetrievalHit]:
        if self._matrix is None or not len(self._chunks):
            return []
        query = np.array(embedding).reshape(1, -1)
        scores = cosine_similarity(query, self._matrix)[0]
        chunk_ids = self._chunk_ids
        ranked_indices = np.argsort(scores)[::-1][:top_k]
        hits: List[RetrievalHit] = []
        for idx in ranked_indices:
            score = float(scores[idx])
            chunk_id = chunk_ids[idx]
            hits.append(RetrievalHit(chunk=self._chunks[chunk_id], score=score))
        return hits

    def persist(self) -> None:
        if self._matrix is not None:
            np.save(self.embeddings_path, self._matrix)
        with self.metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "chunk_ids": self._chunk_ids,
                    "chunks": {
                        chunk_id: chunk.model_dump(mode="json")
                        for chunk_id, chunk in self._chunks.items()
                    },
                },
                handle,
            )

    @classmethod
    def from_path(cls, path: Path) -> "SimpleVectorStore":
        return cls(path)
