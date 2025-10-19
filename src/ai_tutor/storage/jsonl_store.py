from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List

from ai_tutor.data_models import Chunk


class ChunkJsonlStore:
    """Simple JSONL persistence for chunks with deterministic ordering."""

    def __init__(self, path: Path):
        """Ensure the backing directory exists and record the JSONL filepath."""
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Chunk]:
        """Read all stored chunks from disk and reconstruct them as models."""
        if not self.path.exists():
            return []
        chunks: List[Chunk] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                data = json.loads(line)
                chunks.append(Chunk.model_validate(data))
        return chunks

    def upsert(self, chunks: Iterable[Chunk]) -> None:
        """Merge chunks into storage, replacing existing entries with matching IDs."""
        existing = {chunk.metadata.chunk_id: chunk for chunk in self.load()}
        for chunk in chunks:
            existing[chunk.metadata.chunk_id] = chunk
        with self.path.open("w", encoding="utf-8") as handle:
            for chunk in existing.values():
                handle.write(chunk.model_dump_json())
                handle.write("\n")

    def delete(self, chunk_ids: Iterable[str]) -> None:
        """Remove chunks with the provided IDs and rewrite the JSONL file."""
        to_delete = set(chunk_ids)
        remaining = [
            chunk for chunk in self.load() if chunk.metadata.chunk_id not in to_delete
        ]
        with self.path.open("w", encoding="utf-8") as handle:
            for chunk in remaining:
                handle.write(chunk.model_dump_json())
                handle.write("\n")
